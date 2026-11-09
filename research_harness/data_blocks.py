"""Monotonic local data-use blocks; integrity is not reviewer authentication.

No unblock, network, dataset reads, or scientific decisions. Copies must exchange
this state explicitly; the checkout lock does not coordinate different machines.
"""
import json
import os
from pathlib import Path
import tempfile

from . import data_qualification as dq
from .core import digest
from .portable import ROOT
from .state_lock import research_lock

KIND = 'research-harness-data-use-blocks'
LIMIT = 256


def _dataset(value):
    dq._keys(value, ('id', 'version', 'source'), 'blocked dataset')
    for key, text in value.items():
        dq._text(text, 'dataset.' + key)


def _envelope(records):
    content = {'kind': KIND, 'version': 1, 'records': sorted(records, key=digest)}
    return {'content': content, 'sha256': digest(content)}


def _validate(packet):
    dq._keys(packet, ('content', 'sha256'), 'data-use blocks envelope')
    dq._sha(packet['sha256'])
    c = packet['content']
    dq._keys(c, ('kind', 'version', 'records'), 'data-use blocks')
    if c['kind'] != KIND or type(c['version']) is not int or c['version'] != 1:
        raise ValueError('Unsupported data-use blocks version')
    rows = c['records']
    if not isinstance(rows, list) or len(rows) > LIMIT:
        raise ValueError('Too many data-use block records')
    for row in rows:
        dq._keys(row, ('dataset', 'qualification_sha256', 'reviewer', 'reason'), 'data-use block')
        _dataset(row['dataset'])
        dq._sha(row['qualification_sha256'])
        dq._text(row['reviewer'], 'reviewer')
        dq._text(row['reason'], 'reason')
    if len({digest(row) for row in rows}) != len(rows) or packet != _envelope(rows):
        raise ValueError('Changed, duplicate or unordered data-use blocks')
    return rows


def _path(root):
    # Canonicalize the caller-selected checkout (macOS /var and /tmp are aliases).
    # Never resolve away links within the state directory or state file.
    checkout = Path(root).resolve()
    if checkout.exists() and not checkout.is_dir():
        raise ValueError('Data-use state root must be a directory')
    return dq._regular_path(checkout/'.research-memory/data-blocks.json')


def _load(root):
    path = _path(root)
    # Only absence means empty. A malformed or nonregular file fails closed.
    if not path.exists():
        return []
    return _validate(dq._json(path))


def _save(root, records):
    packet = _envelope(records)
    _validate(packet)
    encoded = (json.dumps(packet, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8')
    if len(encoded) > dq.PACKET_LIMIT:
        raise ValueError('Data-use blocks exceed packet size limit')
    path = _path(root)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.data-blocks-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        dq._regular_path(path)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def assert_allowed(dataset, root=ROOT):
    _dataset(dataset)
    records = _load(root)
    if any(row['dataset'] == dataset for row in records):
        raise ValueError('DATA_USE_BLOCKED: this dataset version is paused in this checkout; '
                         'old approvals or new qualification packets cannot override it')


def status(root=ROOT):
    packet = _envelope(_load(root))
    return {'status': 'DATA_USE_BLOCKS', 'read_only': True,
            'root': str(Path(root).resolve()),
            'execution_authorized': False, **packet,
            'note': 'Exact dataset identity, local snapshot only; absence of a block is not permission.'}


def block(packet_path, expected_hash, reviewer, reason, root=ROOT):
    packet = dq.load_packet(packet_path)
    if packet['sha256'] != expected_hash:
        raise ValueError('Data-use block requires the exact qualification hash')
    row = {'dataset': packet['content']['dataset'], 'qualification_sha256': packet['sha256'],
           'reviewer': reviewer, 'reason': reason}
    _validate(_envelope([row]))
    with research_lock(root):
        records = _load(root)
        added = row not in records
        if added:
            _save(root, [*records, row])
    return {'status': 'DATA_USE_BLOCKED', 'added': added, 'dataset': row['dataset'],
            'execution_authorized': False, 'scientific_decision_changed': False}


def export(output, root=ROOT):
    with research_lock(root):
        packet = _envelope(_load(root))
        dq._write(output, packet)
    return {'status': 'EXPORTED', 'sha256': packet['sha256'],
            'records': len(packet['content']['records']), 'execution_authorized': False}


def import_blocks(path, root=ROOT):
    incoming = _validate(dq._json(path))
    with research_lock(root):
        existing = _load(root)
        union = {digest(row): row for row in [*existing, *incoming]}
        merged = list(union.values())
        added = len(merged)-len(existing)
        if added:
            _save(root, merged)
    return {'status': 'IMPORTED', 'added': added, 'records': len(merged),
            'execution_authorized': False, 'note': 'Blocks only added; no approvals or consumed data restored.'}
