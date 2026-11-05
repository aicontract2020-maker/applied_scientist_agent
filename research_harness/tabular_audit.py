"""Read-only audit of completed baseline evidence, even after a checkout upgrade.

Historical sources are compared as data, never imported or executed. New execution
still uses load_review's strict default current-source check.
"""
import hashlib
import json
from pathlib import Path

from .core import number
from .memory import _object, read_json
from .tabular_baseline import load_review, qualify, source_hashes
from .tabular_data import FILES

_AUDIT_FILES = ('bundle.json', 'approval.json', *FILES, 'run/result.json', 'run/ledger.jsonl',
                'run/inputs/request.json', 'run/output/predictions.json', 'run/preflight.json',
                'run/process.json', 'run/trusted/worker.py')


def _signature(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4*1024*1024:
        raise ValueError('Missing, linked or oversized baseline artifact: '+str(path))
    stat = path.stat()
    return stat.st_ino, stat.st_size, stat.st_mtime_ns


def validated_baseline(folder):
    """Return checked frozen records for trusted proposal preparation only."""
    folder = Path(folder)
    for name in ('run', 'run/inputs', 'run/output', 'run/trusted'):
        path = folder/name
        if path.is_symlink() or not path.is_dir(): raise ValueError('Baseline artifact directory is missing/linked')
    before = {name: _signature(folder/name) for name in _AUDIT_FILES}
    packet, parts = load_review(folder, require_current_sources=False)
    approval = read_json(folder/'approval.json')
    if (not isinstance(approval, dict) or set(approval) != {'sha256','reviewer','scope'}
            or approval['sha256'] != packet['sha256'] or not isinstance(approval['reviewer'],str) or not approval['reviewer'].strip()
            or approval['scope'] != 'One baseline qualification only; no candidate study or final holdout scoring'):
        raise ValueError('Baseline approval is missing or mismatched')
    def nonfinite(value): raise ValueError('Non-finite ledger value')
    events = [json.loads(line, object_pairs_hook=_object, parse_constant=nonfinite)
              for line in (folder/'run/ledger.jsonl').read_text().splitlines()]
    if [e['event'] for e in events] != ['REGISTER','BASELINE_STARTED','DECISION']:
        raise ValueError('Expected exactly one completed baseline attempt')
    if any(e.get('review_sha256') != packet['sha256'] for e in events[:2]):
        raise ValueError('Baseline ledger does not bind the reviewed protocol')
    result = read_json(folder/'run/result.json')
    if events[-1].get('result') != result or result.get('measurement_valid') is not True or result.get('final_holdout_scored') is not False:
        raise ValueError('Baseline result/ledger is inconsistent or measurement invalid')
    worker = (folder/'run/trusted/worker.py').read_bytes()
    if hashlib.sha256(worker).hexdigest() != packet['content']['sources'].get('research_harness/tabular_worker.py'):
        raise ValueError('Executed worker does not match frozen worker hash')
    request = read_json(folder/'run/inputs/request.json')
    if request != {'recipe': packet['content']['recipe'], 'train': parts['train.json'], 'validation': parts['validation.json']}:
        raise ValueError('Worker inputs differ from review or include unexpected data')
    held = {r['id'] for r in parts['holdout.json']}
    if not held.isdisjoint(r['id'] for key in ('train','validation') for r in request[key]):
        raise ValueError('Final holdout entered worker inputs')
    process = read_json(folder/'run/process.json')
    if process.get('error') is not None or process.get('returncode') != 0:
        raise ValueError('Baseline process did not finish successfully')
    preflight = read_json(folder/'run/preflight.json')
    env = {'python': [3,12], 'packages': packet['content']['recipe']['packages']}
    probes = {'private_labels_denied','repo_denied','input_readonly','network_denied','output_writable'}
    if (preflight.get('environment') != env or not isinstance(preflight.get('isolation'),dict)
            or set(preflight['isolation']) != probes or any(v is not True for v in preflight['isolation'].values())):
        raise ValueError('Missing/mismatched environment or isolation evidence')
    raw = read_json(folder/'run/output/predictions.json')
    recomputed = qualify(raw, parts['validation-targets.json'])
    if any(result.get(k) != v for k,v in recomputed.items()):
        raise ValueError('Stored validation predictions do not reproduce the baseline decision')
    number(result['wall_seconds'], 'wall_seconds', 0)
    if before != {name: _signature(folder/name) for name in _AUDIT_FILES}:
        raise ValueError('Baseline evidence changed during audit')
    return packet, parts, result, raw


def audit_baseline(folder):
    try:
        packet, parts, result, _ = validated_baseline(folder)
        return {'audit_ok': True, 'read_only': True, 'review_sha256': packet['sha256'],
                'current_sources_match': packet['content']['sources'] == source_hashes(),
                'status': result['status'], 'selected_baseline': result['selected_baseline'],
                'validation_rows': len(parts['validation.json']), 'holdout_rows': len(parts['holdout.json']),
                'final_holdout_scored': False,
                'limit': 'Recorded evidence consistency only; not process authenticity, independent execution or generalization. Historical code is not executed.'}
    except (ValueError, OSError, KeyError, TypeError, AttributeError, IndexError, OverflowError, ZeroDivisionError) as exc:
        return {'audit_ok': False, 'read_only': True, 'error': str(exc)}
