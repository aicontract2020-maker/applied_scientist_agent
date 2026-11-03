"""Autonomous SR pilot: agent-written proposal/code -> immutable registration -> run.

The agent requests operations through files. The controller owns registration,
reference images, snapshots, evaluation and the one-experiment stopping gate.
macOS Seatbelt prevents agent tools reading the research repository/control store;
agent-authored candidate code additionally has no network or user-file access.
This is a local research prototype, not a hardened multi-tenant security product.
"""
import ast
import hashlib
import importlib.util
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
from .observations import summarize

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
        f'(deny file-read* {excluding("/Users", allow_home)})',
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
    def __init__(self, destination):
        self.destination = Path(destination).resolve()
        self.destination.mkdir(parents=True, exist_ok=False)
        self.session = Path(tempfile.mkdtemp(prefix='research-harness-g2-')).resolve()
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
        self.policy = json.loads((STUDY / 'policy.json').read_text())
        self.hidden = json.loads((STUDY / 'inputs.lock.json').read_text())
        self.log('SESSION_CREATED', session=str(self.session), policy_sha256=digest(self.policy),
                 inputs_sha256=digest(self.hidden))

    def log(self, event, **fields):
        record = {'timestamp': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}
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
        allowed = {s['url'] for s in json.loads((STUDY / 'literature.json').read_text())}
        for item in evidence:
            if not isinstance(item, dict) or item.get('source') not in allowed or not item.get('claim') or not item.get('why_distinct'):
                raise ValueError('Cite a supplied newly consulted primary source and explain the distinct hypothesis')
        self.verify_inputs()
        snapshot = self.snapshot('registered-candidate')
        protocol = {'plan': plan, 'policy': self.policy, 'candidate_sha256': sha(snapshot / 'candidate.py'),
                    'trusted_inputs_sha256': digest(self.hidden)}
        atomic_json(self.control / 'registered.json', protocol)
        atomic_json(self.destination / 'registered.json', protocol)
        shutil.copyfile(snapshot / 'candidate.py', self.destination / 'candidate.py')
        self.registered = protocol
        self.log('REGISTER', protocol_sha256=digest(protocol), candidate_sha256=protocol['candidate_sha256'])
        return {'status': 'REGISTERED', 'protocol_sha256': digest(protocol), 'next': 'Request run exactly once; no code changes are accepted.'}

    def candidate_run(self, snapshot, inputs, output, smoke=False):
        profile = self.control / f'{output.name}.sb'
        profile.write_text(candidate_profile(self.control, snapshot, inputs, output, self.control / 'trusted'))
        command = ['/usr/bin/sandbox-exec', '-f', str(profile), str(PYTHON), '-B', str(self.control / 'trusted/runner.py'),
                   '--candidate', str(snapshot / 'candidate.py'), '--inputs', str(inputs), '--output', str(output)]
        if smoke:
            command.append('--smoke')
        env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT')}
        env.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='4', OMP_NUM_THREADS='4')
        return bounded_process(command, snapshot, output, 20 if smoke else 90, env)

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
        if sha(self.actor / 'candidate.py') != self.registered['candidate_sha256']:
            raise ValueError('Candidate changed after registration; experiment cancelled')
        begin = time.monotonic()
        if begin - self.start > 450:
            return self.finish_invalid('Insufficient remaining session budget to start the one experiment', begin, {})
        self.log('EXPERIMENT_STARTED', protocol_sha256=digest(self.registered))
        # Trusted reference process owns weights and references. Agent supplies no commands.
        baseline_command = [str(PYTHON), '-B', str(ROOT / 'research_harness/autonomous_reference.py'),
                            '--control', str(self.control), '--policy', str(STUDY / 'policy.json')]
        reference = bounded_process(baseline_command, ROOT, self.control / 'reference-logs', 300)
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
        import cv2
        import numpy as np
        spec = importlib.util.spec_from_file_location('fixed_metrics', ROOT / 'external/SwinIR/utils/util_calculate_psnr_ssim.py')
        metric = importlib.util.module_from_spec(spec); spec.loader.exec_module(metric)
        output = self.control / 'candidate-output'
        expected = set(self.policy['observation_ids'])
        files = list(output.glob('*.npy'))
        if {x.stem for x in files} != expected or any(x.is_symlink() or x.stat().st_nlink != 1 for x in files):
            raise ValueError('Candidate output identities or file types changed')
        timings = {r['id']: r for r in json.loads((output / 'timings.json').read_text())}
        baseline = json.loads((self.control / 'reference-timings.json').read_text())
        rows = []
        for name in self.policy['observation_ids']:
            value = np.load(output / f'{name}.npy', allow_pickle=False)
            gt = cv2.imread(str(ROOT / f'external/SelfExSR/data/Set14/image_SRF_2/{name}_SRF_2_HR.png'), cv2.IMREAD_COLOR)
            ref = cv2.imread(str(self.control / 'reference-png' / f'{name}.png'), cv2.IMREAD_COLOR)
            if value.shape != gt.shape or not np.isfinite(value).all():
                raise ValueError(f'Invalid candidate shape/value: {name}')
            pred = (np.clip(value[:, :, ::-1], 0, 1) * 255.).round().astype(np.uint8)
            rows.append({'id': name,
                         'baseline_score': metric.calculate_psnr(ref, gt, crop_border=2, test_y_channel=True),
                         'candidate_score': metric.calculate_psnr(pred, gt, crop_border=2, test_y_channel=True),
                         'baseline_latency_ms': baseline[name]['strong_baseline_seconds'] * 1000,
                         'candidate_latency_ms': (baseline[name]['plain_seconds'] + timings[name]['postprocess_seconds']) * 1000})
        summary = summarize(self.policy, rows)
        mean = sum(r['candidate_score'] - r['baseline_score'] for r in rows) / len(rows)
        passed = mean >= self.policy['minimum_effect'] and summary['bootstrap_interval'][0] > 0 and summary['latency_ratio'] <= self.policy['max_latency_ratio']
        result = {'status': 'CONTINUE' if passed else 'STOP', 'measurement_valid': True, 'mean_gain_db': mean,
                  'baseline_psnr_y': sum(r['baseline_score'] for r in rows) / len(rows),
                  'candidate_psnr_y': sum(r['candidate_score'] for r in rows) / len(rows),
                  'reason': 'All frozen thresholds met.' if passed else 'Effect, interval, or latency did not meet the frozen adoption threshold.',
                  **summary}
        atomic_json(self.destination / 'observations.json', rows)
        atomic_json(self.destination / 'candidate-resources.json', json.loads((output / 'resources.json').read_text()))
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
        shutil.copyfile(STUDY / 'labctl.py', self.actor / 'labctl.py')
        shutil.copyfile(STUDY / 'TASK.md', self.actor / 'TASK.md')
        shutil.copyfile(STUDY / 'literature.json', self.actor / 'literature.json')
        atomic_json(self.actor / 'policy.json', self.policy)
        (self.actor / 'AGENTS.md').write_text('Follow TASK.md. Work only here. Use labctl.py for registered experiments. Never inspect hidden data or fetch benchmark labels.\n')
        profile = self.destination / 'actor.sb'; profile.write_text(actor_profile(self.control, self.actor))
        command = ['/usr/bin/sandbox-exec', '-f', str(profile), 'codex', '-c', 'approval_policy="never"',
                   'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'danger-full-access',
                   '--json', '--output-last-message', str(self.actor / 'final.txt'),
                   'Read TASK.md and policy.json. Complete the autonomous research task yourself: propose, implement, synthetic-check, preregister, request the experiment, interpret its result, and write REPORT.md. Use the file broker; do not ask the human to do your coding or execution.']
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
                    if time.monotonic() - self.start > 900:
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
        for name in ('candidate.py', 'research.json', 'REPORT.md', 'final.txt'):
            source = self.actor / name
            if source.is_file() and not source.is_symlink() and source.stat().st_size < 200000:
                shutil.copyfile(source, self.destination / ('agent-' + name))
        if not (self.destination / 'result.json').exists():
            atomic_json(self.destination / 'result.json', {'status': 'INCOMPLETE', 'reason': 'Agent did not complete a registered experiment', 'exit_code': process.returncode})
        metadata = {'actor_directory': str(self.actor), 'control_directory': str(self.control),
                    'total_wall_seconds': time.monotonic() - self.start, 'local_proxy_usd': (time.monotonic() - self.start) / 3600,
                    'billing_usd': None, 'actual_model_id': None, 'candidate_execution_network': 'DENIED',
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
