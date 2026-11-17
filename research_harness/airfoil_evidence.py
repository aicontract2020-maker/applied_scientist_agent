"""Private, bounded Airfoil evidence; carried sources are text, never executed."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

from . import airfoil_baseline as baseline, airfoil_trial as trial
from .core import digest
from .data_qualification import _read, _regular_path, _object, _nonfinite
from .memory import _keys

KIND = 'research-harness-airfoil-evidence'
FILE_LIMIT = 4 * 1024 * 1024
TOTAL_LIMIT = 16 * 1024 * 1024
PACKET_LIMIT = 32 * 1024 * 1024
RAW = 'baseline/airfoil_self_noise.dat'
FILES = frozenset(['baseline/' + name for name in trial.BASE_FILES] + [
    'trial.json', 'candidate.py', 'trial-approval.json', 'trial-run/result.json',
    'trial-run/ledger.jsonl', 'trial-run/preflight.json', 'trial-run/process.json',
    'trial-run/inputs/request.json', 'trial-run/output/predictions.json',
    'trial-run/trusted/airfoil_candidate.py', 'trial-run/trusted/airfoil_trial_worker.py'])


def _runtime():
    if sys.version_info[:2] != (3, 12):
        raise ValueError('Exact Airfoil evidence audit requires Python 3.12')


def _decode(data):
    try:
        value = json.loads(data, object_pairs_hook=_object, parse_constant=_nonfinite)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Invalid evidence encoding or nesting') from exc
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise ValueError('Evidence nesting exceeds limit')
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError('Nonfinite evidence number')
        if isinstance(item, (dict, list)):
            pending.extend((child, depth + 1) for child in (item.values() if isinstance(item, dict) else item))
    return value


def _files(source):
    if source == baseline.FIXTURE:
        return FILES - {RAW}
    if source == baseline.SOURCE:
        return FILES
    raise ValueError('Unsupported Airfoil evidence source')


def _validate(value):
    _keys(value, ('payload', 'sha256'))
    payload = value['payload']; _keys(payload, ('kind', 'version', 'files'))
    if payload['kind'] != KIND or type(payload['version']) is not int or payload['version'] != 1:
        raise ValueError('Wrong evidence task/version')
    files = payload['files']
    if not isinstance(files, dict) or set(files) not in (FILES, FILES - {RAW}):
        raise ValueError('Evidence needs exactly the fixed allowlist')
    total = 0
    for item in files.values():
        _keys(item, ('content', 'sha256'))
        if not isinstance(item['content'], str):
            raise ValueError('Evidence content must be UTF-8 text')
        data = item['content'].encode('utf-8'); total += len(data)
        if len(data) > FILE_LIMIT or total > TOTAL_LIMIT:
            raise ValueError('Evidence content exceeds limit')
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Changed evidence file hash')
    # Reject ambiguous JSON even in the carried audit records.
    for name, item in files.items():
        if name.endswith('.json'):
            _decode(item['content'])
        elif name.endswith('.jsonl'):
            for line in item['content'].splitlines():
                _decode(line)
    bundle = _decode(files['baseline/bundle.json']['content'])
    if not isinstance(bundle, dict) or not isinstance(bundle.get('content'), dict):
        raise ValueError('Invalid baseline envelope')
    if set(files) != _files(bundle['content'].get('source')):
        raise ValueError('Evidence allowlist differs from baseline source')
    if value['sha256'] != digest(payload):
        raise ValueError('Changed evidence envelope')
    return value


def load_packet(path):
    return _validate(_decode(_read(path, PACKET_LIMIT)))


def _write(path, data):
    path = _regular_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _materialize(packet, folder):
    folder = Path(folder)
    for name, item in packet['payload']['files'].items():
        target = folder / name
        for parent in reversed(target.relative_to(folder).parents):
            (folder / parent).mkdir(mode=0o700, exist_ok=True)
        _write(target, item['content'].encode('utf-8'))
    marker = json.dumps({'packet_sha256': packet['sha256'],
                         'purpose': 'Read-only review; never execute imported approval'}).encode()
    for location in (folder, folder / 'baseline'):
        _write(location / 'EVIDENCE_ONLY.json', marker)


def _audit(packet):
    _runtime()
    with tempfile.TemporaryDirectory(prefix='rh-airfoil-evidence-') as tmp:
        folder = Path(tmp).resolve()  # macOS system temp may use the /var alias.
        _materialize(packet, folder)
        return trial.audit(folder)


def verify(path):
    packet = load_packet(path); audit = _audit(packet)
    return {'sha256': packet['sha256'], 'checksum_ok': True, 'audit_ok': audit['audit_ok'],
            'audit': audit, 'authenticity': 'UNVERIFIED', 'execution_permitted': False,
            'note': 'Internal consistency only; no worker/model execution or memory import'}


def export(folder, output):
    _runtime(); folder = _regular_path(folder)
    if not folder.is_dir():
        raise ValueError('Regular Airfoil trial directory required')
    # Bound and stage before invoking the auditor on untrusted source files.
    bundle = _decode(_read(folder / 'baseline/bundle.json', FILE_LIMIT))
    if not isinstance(bundle, dict) or not isinstance(bundle.get('content'), dict):
        raise ValueError('Invalid baseline envelope')
    files = {}
    for name in sorted(_files(bundle['content'].get('source'))):
        data = _read(folder / name, FILE_LIMIT)
        files[name] = {'content': data.decode('utf-8'), 'sha256': hashlib.sha256(data).hexdigest()}
    payload = {'kind': KIND, 'version': 1, 'files': files}
    packet = _validate({'payload': payload, 'sha256': digest(payload)})
    _audit(packet)
    for name, item in files.items():
        if hashlib.sha256(_read(folder / name, FILE_LIMIT)).hexdigest() != item['sha256']:
            raise ValueError('Original evidence changed during export; no retry')
    encoded = (json.dumps(packet, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()
    if len(encoded) > PACKET_LIMIT:
        raise ValueError('Encoded packet exceeds limit')
    _write(output, encoded)
    return {'status': 'EXPORTED_PRIVATE', 'sha256': packet['sha256'], 'audit_ok': True,
            'files': len(files), 'bytes': len(encoded), 'execution_permitted': False,
            'sharing_note': 'Contains data, held-out labels/predictions and approval text. Separate rights review required before sharing.'}


def unpack(path, output):
    packet = load_packet(path); _audit(packet)
    output = _regular_path(output); output.mkdir(mode=0o700, exist_ok=False)
    try:
        pending = output / '.pending'; pending.mkdir(mode=0o700)
        _materialize(packet, pending); pending.rename(output / 'review')
        _write(output / 'receipt.json', (json.dumps({'packet_sha256': packet['sha256'],
            'purpose': 'Review only; transfer exclusion memory separately; no execution approval'}, indent=2) + '\n').encode())
    except BaseException:
        shutil.rmtree(output)
        raise
    return {'status': 'UNPACKED_REVIEW_ONLY', 'review': str(output / 'review'),
            'sha256': packet['sha256'], 'audit_ok': True, 'execution_permitted': False}
