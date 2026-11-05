"""Local, trusted-code execution. This is NOT an OS sandbox.

The parent process needs its own restricted environment before running untrusted
research code. No shell expansion or automatic retries are performed here.
"""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .core import COST_FIELDS, number


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate_execution(config):
    if not isinstance(config, dict):
        raise ValueError('execution must be an object')
    cwd = Path(config.get('cwd', ''))
    if not cwd.is_absolute() or not cwd.is_dir():
        raise ValueError('execution.cwd must be an existing absolute directory')
    command = config.get('command')
    if not isinstance(command, list) or not command or any(not isinstance(x, str) or not x for x in command):
        raise ValueError('execution.command must be a nonempty argv list')
    if not any('{output}' in x for x in command) or not any('{seed}' in x for x in command):
        raise ValueError('command must include {seed} and {output}')
    for part in command:
        try:
            part.format(python=sys.executable, seed=11, output='/tmp/result.json')
        except (KeyError, ValueError, IndexError) as exc:
            raise ValueError('Only {python}, {seed}, {output} placeholders are supported') from exc
    number(config.get('timeout_seconds'), 'timeout_seconds', 0.01)
    number(config.get('compute_usd_per_hour'), 'compute_usd_per_hour', 0)
    costs = config.get('fixed_costs', {})
    if set(costs) != {'data_usd', 'storage_usd', 'tuning_usd'}:
        raise ValueError('execution.fixed_costs needs data_usd, storage_usd, tuning_usd per attempt')
    for k, v in costs.items():
        number(v, k, 0)
    inputs = config.get('inputs')
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError('execution.inputs must map relative files to SHA-256 hashes')
    for name, expected in inputs.items():
        path = (cwd / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(cwd.resolve()):
            raise ValueError('Input paths must stay inside execution.cwd')
        if not isinstance(expected, str) or file_hash(path) != expected:
            raise ValueError(f'Input changed or hash incorrect: {name}')


def run(workspace, experiment_id):
    """Run missing paired replications, returning PENDING or a final decision."""
    folder, p, events = workspace.load(experiment_id)
    current = workspace.evaluate(experiment_id)
    if current['status'] != 'PENDING':
        return current
    config = p.get('execution')
    if config is None:
        raise ValueError('Register an execution configuration before running commands')
    # An interrupted process may have spent money or produced partial artifacts.
    # Do not silently rerun it or assume its cost was zero.
    starts = {e['attempt'] for e in events if e['event'] == 'ATTEMPT_STARTED'}
    finishes = {e['attempt'] for e in events if e['event'] == 'ATTEMPT_FINISHED'}
    if starts - finishes:
        raise ValueError('Interrupted attempt needs manual cost reconciliation; automatic retry is disabled')
    finished_seeds = {e['result']['seed'] for e in events if e['event'] == 'RESULT'}
    if finishes and len(finishes) != len(finished_seeds):
        raise ValueError('Unrecorded completed attempt needs manual reconciliation; no rerun allowed')
    for seed in p['seeds']:
        if seed in finished_seeds:
            continue
        validate_execution(config)
        # Reserve the worst declared charge before starting each process.
        fixed = sum(config['fixed_costs'].values())
        reserve = fixed + config['timeout_seconds'] / 3600 * config['compute_usd_per_hour']
        current = workspace.evaluate(experiment_id)
        if current['total_usd'] + reserve > p['budget_usd']:
            workspace.append(folder, {'event': 'EXECUTION_STOP', 'reason': 'Insufficient budget for declared worst-case next attempt.'})
            return workspace.evaluate(experiment_id)
        attempt = f'seed-{seed}'
        attempt_dir = (folder / 'attempts' / attempt).resolve()
        attempt_dir.mkdir(parents=True, exist_ok=False)
        output = attempt_dir / 'result.json'
        command = [arg.format(python=sys.executable, seed=seed, output=str(output)) for arg in config['command']]
        workspace.append(folder, {'event': 'ATTEMPT_STARTED', 'attempt': attempt, 'seed': seed, 'command': command, 'cwd': config['cwd'], 'reserved_usd': reserve})
        start = time.monotonic()
        error = None
        exit_code = None
        try:
            with (attempt_dir / 'stdout.log').open('wb') as stdout, (attempt_dir / 'stderr.log').open('wb') as stderr:
                process = subprocess.Popen(command, cwd=config['cwd'], stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    exit_code = process.wait(timeout=config['timeout_seconds'])
                    if exit_code:
                        error = f'Command exited with status {exit_code}'
                except subprocess.TimeoutExpired:
                    error = 'Command timed out'
                finally:
                    # Also terminate same-process-group children left after normal exit.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
        except OSError as exc:
            error = str(exc)
        elapsed = time.monotonic() - start
        costs = dict.fromkeys(COST_FIELDS, 0)
        costs.update(config['fixed_costs'], compute_seconds=elapsed,
                     compute_usd=elapsed / 3600 * config['compute_usd_per_hour'])
        workspace.append(folder, {'event': 'ATTEMPT_FINISHED', 'attempt': attempt, 'seed': seed, 'exit_code': exit_code, 'error': error, 'costs': costs, 'artifact': str(attempt_dir)})
        if error:
            return workspace.evaluate(experiment_id)
        try:
            if output.stat().st_size > 1024 * 1024:
                raise ValueError('Result JSON exceeds 1 MiB')
            result = json.loads(output.read_text())
            if result.get('seed') != seed:
                raise ValueError('Result seed does not match scheduled seed')
            # Parent owns compute charges and fixed costs; child reports measured
            # storage usage and inference latency, not arbitrary billing totals.
            measurements = result.pop('measurements')
            if set(measurements) != {'storage_byte_hours', 'latency_ms'}:
                raise ValueError('measurements requires storage_byte_hours and latency_ms')
            for k, v in measurements.items():
                number(v, k, 0)
            result.update(artifact=str(attempt_dir), costs={**costs, **measurements}, execution_attempt=attempt)
            current = workspace.record(experiment_id, result)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            workspace.append(folder, {'event': 'EXECUTION_STOP', 'reason': f'Invalid or missing experiment output: {exc}'})
            return workspace.evaluate(experiment_id)
        if current['status'] != 'PENDING':
            return current
    return current
