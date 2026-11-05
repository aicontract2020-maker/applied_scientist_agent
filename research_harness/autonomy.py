"""Autonomous SR pilot: agent-written proposal/code -> immutable registration -> run.

The agent requests operations through files. The controller owns registration,
reference images, snapshots, evaluation and the one-experiment stopping gate.
macOS Seatbelt prevents agent tools reading the research repository/control store;
agent-authored candidate code additionally has no network or user-file access.
This is a local research prototype, not a hardened multi-tenant security product.
"""
import ast
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .core import digest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / '.venv-sr/bin/python'
PYTHON_BASE = Path(os.path.realpath(PYTHON)).parent.parent
STUDY = ROOT / 'tasks/image_super_resolution/g2'


def atomic_json(path, value):
    temp = path.with_suffix('.partial')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))
    temp.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quote(value):
    return json.dumps(str(value))


def excluding(path, exceptions):
    return '(require-all (subpath ' + quote(path) + ') ' + ' '.join('(require-not (subpath ' + quote(p) + '))' for p in exceptions) + ')'


def actor_profile(control, actor):
    # Codex's tool sandbox cannot be nested under Seatbelt. This external profile
    # supplies filesystem isolation; the CLI uses its externally-sandboxed mode.
    return '\n'.join(['(version 1)', '(allow default)',
        f'(deny file-read* (subpath {quote(ROOT)}) (subpath {quote(control)}))',
        f'(deny file-write* (subpath {quote(ROOT)}) (subpath {quote(control)}))',
        f'(deny file-write* (subpath {quote(actor / "responses")}))',
        f'(deny file-write* (require-all (require-not (subpath {quote(actor)})) (require-not (subpath {quote(Path.home() / ".codex")})) (require-not (subpath "/dev"))))'])


def candidate_profile(control, snapshot, inputs, output, trusted):
    allow_home = [ROOT / '.venv-sr', PYTHON_BASE]
    allow_control = [snapshot, inputs, output, trusted]
    return '\n'.join(['(version 1)', '(allow default)', '(deny network*)',
        f'(deny file-read* {excluding("/Users", allow_home)} {excluding(ROOT, allow_home)})',
        f'(deny file-read* {excluding(control, allow_control)})',
        f'(deny file-write* (require-all (require-not (subpath {quote(output)})) (require-not (subpath "/dev"))))'])


def bounded_process(command, cwd, output, timeout, env=None, quota=256 * 1024 * 1024):
    output.mkdir(parents=True, exist_ok=False)
    begin = time.monotonic()
    error = None
    with (output / 'stdout.log').open('wb') as stdout, (output / 'stderr.log').open('wb') as stderr:
        process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr,
                                   env=env, start_new_session=True)
        try:
            while process.poll() is None:
                if time.monotonic() - begin > timeout:
                    error = 'timeout'; break
                size = sum(p.lstat().st_size for p in output.rglob('*') if p.is_file() and not p.is_symlink())
                if size > quota:
                    error = 'output quota exceeded'; break
                time.sleep(.1)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    if error is None and process.returncode:
        error = f'exit {process.returncode}'
    return {'error': error, 'returncode': process.returncode, 'wall_seconds': time.monotonic() - begin,
            'artifact': str(output)}


class AutonomousStudy:
    def __init__(self, destination, study=None):
        self.study = Path(study or STUDY).resolve()
        self.policy = json.loads((self.study / 'policy.json').read_text())
        from .task_contracts import validate_sr_policy
        validate_sr_policy(self.policy)
        self.destination = Path(destination).resolve()
        self.destination.mkdir(parents=True, exist_ok=False)
        self.session = Path(tempfile.mkdtemp(prefix='research-harness-')).resolve()
        self.actor = self.session / 'agent'
        self.control = self.session / 'control'
        for p in (self.actor, self.control, self.actor / 'requests', self.actor / 'responses', self.control / 'trusted'):
            p.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'research_harness/autonomous_candidate.py', self.control / 'trusted/runner.py')
        self.closed = False
        self.registered = None
        self.smoke_count = 0
        self.events = self.destination / 'ledger.jsonl'
        self.start = time.monotonic()
        self.hidden = json.loads((self.study / 'inputs.lock.json').read_text())
        self.log('SESSION_CREATED', session=str(self.session), policy_sha256=digest(self.policy),
                 inputs_sha256=digest(self.hidden))

    def log(self, event, **fields):
        record = {'timestamp': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}
        labels = {'PRIMARY_READ_COMPLETED': 'Primary paper retrieved', 'REGISTER': 'Candidate and protocol frozen',
                  'EXPERIMENT_STARTED': 'One registered experiment started', 'REFERENCE_FINISHED': 'Reference inference finished',
                  'DECISION': 'Evaluator decision recorded', 'AGENT_FINISHED': 'Agent session finished'}
        if getattr(self, 'policy', {}).get('show_progress') and event in labels:
            print(labels[event], file=sys.stderr, flush=True)
        with self.events.open('a') as f:
            f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')

    def verify_inputs(self):
        for path, expected in self.hidden['files'].items():
            if sha(ROOT / path) != expected:
                raise ValueError(f'Frozen trusted input changed: {path}')

    def snapshot(self, name):
        source = self.actor / 'candidate.py'
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 100000:
            raise ValueError('Provide one regular candidate.py <=100 KB')
        text = source.read_text()
        tree = ast.parse(text)
        if not any(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == 'enhance' for x in tree.body):
            raise ValueError('candidate.py must define enhance(lr, sr)')
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(x.name.split('.')[0] not in ('numpy', 'cv2', 'math') for x in node.names):
                raise ValueError('Candidate imports are limited to numpy/cv2/math')
            if isinstance(node, ast.ImportFrom) and (not node.module or node.module.split('.')[0] not in ('numpy', 'cv2', 'math')):
                raise ValueError('Candidate imports are limited to numpy/cv2/math')
            if isinstance(node, ast.Attribute) and node.attr in ('random', 'load', 'save', 'imread', 'imwrite'):
                raise ValueError('Candidate must be deterministic array code, with no file IO')
        target = self.control / name
        target.mkdir(exist_ok=False)
        (target / 'candidate.py').write_text(text)
        return target

    def evidence_sources(self):
        return {s['url'] for s in json.loads((self.study / 'literature.json').read_text())}

    def register(self):
        if self.registered or self.closed:
            raise ValueError('Registration is single-use')
        source = self.actor / 'research.json'
        if source.is_symlink() or source.stat().st_size > 100000:
            raise ValueError('Invalid research.json')
        plan = json.loads(source.read_text())
        for field in ('hypothesis', 'mechanism', 'baseline', 'why_not_g1_retry', 'stop_route'):
            if not isinstance(plan.get(field), str) or not plan[field].strip():
                raise ValueError(f'Missing research field: {field}')
        if plan.get('controls') != self.policy['controls']:
            raise ValueError('Copy the frozen controls exactly')
        for key in ('minimum_effect', 'max_latency_ratio', 'bootstrap', 'observation_ids'):
            if plan.get(key) != self.policy[key]:
                raise ValueError(f'Cannot change fixed decision field: {key}')
        evidence = plan.get('new_evidence')
        if not isinstance(evidence, list) or not evidence:
            raise ValueError('New external evidence is required for a distinct route after G1 STOP')
        allowed = self.evidence_sources()
        for item in evidence:
            if not isinstance(item, dict) or item.get('source') not in allowed or not item.get('claim') or not item.get('why_distinct'):
                raise ValueError('Cite a supplied newly consulted primary source and explain the distinct hypothesis')
        self.verify_inputs()
        snapshot = self.snapshot('registered-candidate')
        if self.policy.get('intervention_review', {}).get('required'):
            from .intervention_review import review_intervention
            review = review_intervention(self, snapshot, plan)
            if review['decision'] != 'PASS':
                return self.reject_registration(review['reason'])
            try:
                unchanged = (not (self.actor/'candidate.py').is_symlink() and not source.is_symlink()
                             and sha(self.actor/'candidate.py') == review['candidate_sha256']
                             and json.loads(source.read_text()) == plan)
            except (OSError, ValueError):
                unchanged = False
            if not unchanged:
                return self.reject_registration('Proposal changed during immutable intervention review')
        protocol = {'plan': plan, 'policy': self.policy, 'candidate_sha256': sha(snapshot / 'candidate.py'),
                    'trusted_inputs_sha256': digest(self.hidden)}
        atomic_json(self.control / 'registered.json', protocol)
        atomic_json(self.destination / 'registered.json', protocol)
        shutil.copyfile(snapshot / 'candidate.py', self.destination / 'candidate.py')
        self.registered = protocol
        self.log('REGISTER', protocol_sha256=digest(protocol), candidate_sha256=protocol['candidate_sha256'])
        return {'status': 'REGISTERED', 'protocol_sha256': digest(protocol), 'next': 'Request run exactly once; no code changes are accepted.'}

    def reject_registration(self, reason):
        self.closed = True
        result = {'status': 'REJECTED', 'phase': 'pre_registration', 'scientific_status': 'NOT_RUN',
                  'measurement_valid': None, 'experiment_started': False, 'reason': reason,
                  'next': 'Write REPORT.md and stop. No revised candidate, registration or experiment this cycle.'}
        atomic_json(self.destination/'result.json', result)
        self.log('REGISTRATION_REJECTED', result=result)
        return result

    def candidate_run(self, snapshot, inputs, output, smoke=False, intervention_probe=False):
        profile = self.control / (output.name + ('.sb' if sys.platform=='darwin' else '.json'))
        if sys.platform=='darwin': profile.write_text(candidate_profile(self.control, snapshot, inputs, output, self.control / 'trusted'))
        argv = [str(PYTHON), '-B', str(self.control / 'trusted/runner.py'),
                   '--candidate', str(snapshot / 'candidate.py'), '--inputs', str(inputs), '--output', str(output)]
        if smoke:
            argv.append('--smoke')
        if intervention_probe:
            argv.append('--intervention-probe')
        if sys.platform == 'darwin':
            command = ['/usr/bin/sandbox-exec', '-f', str(profile), *argv]
        elif sys.platform == 'linux':
            from .linux_isolation import linux_candidate_command, write_command_manifest
            command = linux_candidate_command(argv, ROOT, PYTHON, snapshot, inputs, output, self.control/'trusted')
            write_command_manifest(profile, command)
        else:
            raise ValueError('Unsupported isolation backend; refusing unisolated execution')
        env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT')}
        env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='4', OMP_NUM_THREADS='4')
        return bounded_process(command, snapshot, output, 20 if smoke or intervention_probe else self.policy.get('limits', {}).get('candidate_seconds', 90), env)

    def smoke(self):
        if self.registered or self.closed or self.smoke_count >= 3:
            raise ValueError('At most 3 synthetic checks before registration; never tune using holdout results')
        self.smoke_count += 1
        snapshot = self.snapshot(f'smoke-{self.smoke_count}')
        inputs = self.control / 'empty-inputs'; inputs.mkdir(exist_ok=True)
        output = self.control / f'smoke-output-{self.smoke_count}'
        result = self.candidate_run(snapshot, inputs, output, smoke=True)
        stderr = (output / 'stderr.log').read_text()[-6000:]
        self.log('SYNTHETIC_CHECK', **result)
        return {'status': 'PASS' if not result['error'] else 'INVALID_IMPLEMENTATION', 'error': result['error'], 'stderr': stderr,
                'note': 'Synthetic shape/finiteness only; no real image scores and no scientific evidence.'}

    def run_experiment(self):
        if not self.registered or self.closed:
            raise ValueError('Register first; experiment can run only once')
        self.closed = True  # Consume the opportunity even on an operational failure.
        self.verify_inputs()
        if json.loads((self.actor/'research.json').read_text()) != self.registered['plan']:
            raise ValueError('Plan changed after registration; experiment cancelled')
        if sha(self.actor / 'candidate.py') != self.registered['candidate_sha256']:
            raise ValueError('Candidate changed after registration; experiment cancelled')
        begin = time.monotonic()
        limits = self.policy.get("limits", {})
        latest = limits.get("agent_session_seconds", 900) - limits.get("reference_seconds", 300) - limits.get("candidate_seconds", 90) - 60
        if begin - self.start > latest:
            return self.finish_invalid('Insufficient remaining session budget to start the one experiment', begin, {})
        self.log('EXPERIMENT_STARTED', protocol_sha256=digest(self.registered))
        # Trusted reference process owns weights and references. Agent supplies no commands.
        baseline_command = [str(PYTHON), '-B', str(ROOT / 'research_harness/autonomous_reference.py'),
                            '--control', str(self.control), '--policy', str(self.study / 'policy.json')]
        reference = bounded_process(baseline_command, ROOT, self.control / 'reference-logs', limits.get('reference_seconds', 300))
        self.log('REFERENCE_FINISHED', **reference)
        if reference['error']:
            return self.finish_invalid('Reference execution failed', begin, reference)
        generated = self.candidate_run(self.control / 'registered-candidate', self.control / 'candidate-inputs', self.control / 'candidate-output')
        self.log('CANDIDATE_FINISHED', **generated)
        if generated['error']:
            return self.finish_invalid('Agent code failed its frozen execution contract', begin, generated)
        try:
            result = self.evaluate()
        except Exception as exc:
            return self.finish_invalid(f'Output/evaluation validity failed: {type(exc).__name__}: {exc}', begin, {})
        result.update(experiment_wall_seconds=time.monotonic() - begin,
                      local_compute_proxy_usd=(time.monotonic() - begin) / 3600,
                      planner_billing_usd=None)
        atomic_json(self.destination / 'result.json', result)
        self.log('DECISION', result=result)
        return result

    def evaluate(self):
        from .sr_evaluation import evaluate_sr
        result, rows = evaluate_sr(ROOT, self.control, self.policy)
        atomic_json(self.destination / 'observations.json', rows)
        atomic_json(self.destination / 'candidate-resources.json', json.loads((self.control / 'candidate-output/resources.json').read_text()))
        return result

    def finish_invalid(self, reason, begin, details):
        result = {'status': 'STOP', 'measurement_valid': False, 'reason': reason, 'details': details,
                  'experiment_wall_seconds': time.monotonic() - begin, 'local_compute_proxy_usd': (time.monotonic() - begin) / 3600,
                  'planner_billing_usd': None, 'next': 'No retry. Record the specific validity failure before any new measurement protocol.'}
        atomic_json(self.destination / 'result.json', result)
        self.log('DECISION', result=result)
        return result

    def serve_request(self, path):
        if path.is_symlink() or path.stat().st_size > 4096:
            raise ValueError('Invalid broker request file')
        request = json.loads(path.read_text())
        operation = request.get('operation')
        self.log('AGENT_REQUEST', request_id=path.stem, operation=operation)
        if operation == 'check':
            return self.smoke()
        if operation == 'register':
            return self.register()
        if operation == 'run':
            return self.run_experiment()
        if operation == 'status':
            if (self.destination / 'result.json').exists():
                return json.loads((self.destination / 'result.json').read_text())
            return {'registered': bool(self.registered), 'closed': self.closed}
        raise ValueError('Unknown operation')

    def launch(self):
        shutil.copyfile(self.study / 'labctl.py', self.actor / 'labctl.py')
        shutil.copyfile(self.study / 'TASK.md', self.actor / 'TASK.md')
        shutil.copyfile(self.study / 'literature.json', self.actor / 'literature.json')
        atomic_json(self.actor / 'policy.json', self.policy)
        (self.actor / 'AGENTS.md').write_text('Follow TASK.md. Work only here. Use labctl.py for registered experiments. Never inspect hidden data or fetch benchmark labels.\n')
        profile = self.destination / ('actor.sb' if sys.platform=='darwin' else 'actor-isolation.json')
        if sys.platform=='darwin': profile.write_text(actor_profile(self.control, self.actor))
        command = ['codex', '-c', 'approval_policy="never"',
                   'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'danger-full-access',
                   '--json', '--output-last-message', str(self.actor / 'final.txt'),
                   'Read TASK.md and policy.json. If registration returns REJECTED, write REPORT.md and stop without revising or running. Otherwise complete the autonomous research task yourself: propose, implement, synthetic-check, preregister, request the experiment, interpret its result, and write REPORT.md. Use the file broker; do not ask the human to do your coding or execution.']
        if self.policy.get('live_web_search'):
            command.insert(command.index('codex') + 1, '--search')
        if sys.platform == 'darwin':
            command = ['/usr/bin/sandbox-exec', '-f', str(profile), *command]
        elif sys.platform == 'linux':
            from .linux_isolation import linux_actor_command, write_command_manifest
            command = linux_actor_command(command, ROOT, self.control, self.actor)
            write_command_manifest(profile, command)
        else:
            raise ValueError('Unsupported isolation backend; refusing unisolated execution')
        self.log('AGENT_STARTED', command=command, external_profile=str(profile))
        done = set()
        with (self.destination / 'agent-events.jsonl').open('wb') as stdout, (self.destination / 'agent-stderr.log').open('wb') as stderr:
            process = subprocess.Popen(command, cwd=self.actor, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            for pipe in (process.stdout, process.stderr):
                os.set_blocking(pipe.fileno(), False)
            try:
                while process.poll() is None:
                    for pipe, log in ((process.stdout, stdout), (process.stderr, stderr)):
                        try:
                            chunk = os.read(pipe.fileno(), 65536)
                            if chunk:
                                log.write(chunk); log.flush()
                        except BlockingIOError:
                            pass
                    for path in sorted((self.actor / 'requests').glob('*.json')):
                        if path.stem in done:
                            continue
                        done.add(path.stem)
                        try:
                            response = self.serve_request(path)
                        except Exception as exc:
                            response = {'status': 'ERROR', 'error': f'{type(exc).__name__}: {exc}'}
                            self.log('REQUEST_REJECTED', request_id=path.stem, error=response['error'])
                        atomic_json(self.actor / 'responses' / path.name, response)
                    if time.monotonic() - self.start > self.policy.get('limits', {}).get('agent_session_seconds', 900):
                        self.log('AGENT_TIMEOUT'); break
                    time.sleep(.2)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            for pipe, log in ((process.stdout, stdout), (process.stderr, stderr)):
                while True:
                    try:
                        chunk = os.read(pipe.fileno(), 65536)
                    except BlockingIOError:
                        break
                    if not chunk:
                        break
                    log.write(chunk)
        self.log('AGENT_FINISHED', exit_code=process.returncode, total_wall_seconds=time.monotonic() - self.start)
        for name in ('intervention-probe', 'reviewer', 'primary-papers', 'reference-logs', 'reference-timings.json', 'candidate-output'):
            source = self.session / name if name == 'reviewer' else self.control / name
            if source.is_dir():
                shutil.copytree(source, self.destination / 'artifacts' / name)
            elif source.is_file():
                (self.destination / 'artifacts').mkdir(exist_ok=True)
                shutil.copyfile(source, self.destination / 'artifacts' / name)
        isolation = self.destination / 'artifacts' / 'isolation'
        isolation.mkdir(parents=True, exist_ok=True)
        for name in ('intervention-probe', 'candidate-output', 'smoke-output-1', 'smoke-output-2', 'smoke-output-3'):
            for suffix in ('.json', '.sb'):
                source = self.control / (name+suffix)
                if source.is_file(): shutil.copyfile(source, isolation / source.name)
        sources = self.destination / 'artifacts' / 'trusted-sources'
        sources.mkdir(parents=True, exist_ok=True)
        for source in (ROOT / 'research_harness').glob('*.py'):
            shutil.copyfile(source, sources / source.name)
        for name in ('candidate.py', 'research.json', 'REPORT.md', 'final.txt'):
            source = self.actor / name
            if source.is_file() and not source.is_symlink() and source.stat().st_size < 200000:
                shutil.copyfile(source, self.destination / ('agent-' + name))
        if not (self.destination / 'result.json').exists():
            atomic_json(self.destination / 'result.json', {'status': 'INCOMPLETE', 'reason': 'Agent did not complete a registered experiment', 'exit_code': process.returncode})
        metadata = {'actor_directory': str(self.actor), 'control_directory': str(self.control),
                    'total_wall_seconds': time.monotonic() - self.start, 'local_proxy_usd': (time.monotonic() - self.start) / 3600,
                    'billing_usd': None, 'actual_model_id': None, 'candidate_execution_network': 'DENIED', 'isolation_backend': 'linux-bubblewrap' if sys.platform=='linux' else 'macos-seatbelt',
                    'agent_network': 'Model service connectivity allowed; task prohibits external benchmark access; not a fully closed egress environment'}
        atomic_json(self.destination / 'session.json', metadata)
        return json.loads((self.destination / 'result.json').read_text())


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    study = AutonomousStudy(args.out)
    result = study.launch()
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
