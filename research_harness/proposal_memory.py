"""Offline tabular proposal occupancy, never scientific STOP or recovery authority.

Only reservation identity is transferred. Completion, failure and local recovery
all retain occupancy; actor output and recovery evidence remain on their origin.
"""
from pathlib import Path

from . import data_qualification as dq
from .core import digest
from .portable import ROOT

KIND = 'research-harness-tabular-proposal-memory'
LIMIT = 1000


def validate(record):
    dq._keys(record, ('scope', 'baseline_sha256'), 'Proposal occupancy')
    dq._sha(record['scope'])
    if record['baseline_sha256'] is not None: dq._sha(record['baseline_sha256'])
    return record


def merge(*groups):
    records = {}
    for group in groups:
        if not isinstance(group, list) or len(group) > LIMIT:
            raise ValueError('Invalid proposal history size')
        for value in group:
            row = dict(validate(value)); old = records.get(row['scope'])
            if old is not None and old['baseline_sha256'] is not None:
                if row['baseline_sha256'] not in (None, old['baseline_sha256']):
                    raise ValueError('Conflicting proposal baseline binding')
                row = old
            records[row['scope']] = row
    if len(records) > LIMIT: raise ValueError('Too many proposal reservations')
    return [records[key] for key in sorted(records)]


def envelope(records):
    content = {'kind': KIND, 'version': 1, 'records': merge(records)}
    return {'content': content, 'sha256': digest(content)}


def validate_packet(packet):
    dq._keys(packet, ('content', 'sha256'), 'Proposal memory envelope')
    dq._keys(packet['content'], ('kind', 'version', 'records'), 'Proposal memory')
    c = packet['content']
    if c['kind'] != KIND or type(c['version']) is not int or c['version'] != 1 or packet != envelope(c['records']):
        raise ValueError('Invalid/noncanonical proposal memory envelope')
    return packet


def _local(root):
    folder = dq._regular_path(Path(root)/'.research-memory/tabular-proposer')
    if folder.exists() and not folder.is_dir(): raise ValueError('Proposal memory must be a directory')
    rows = []
    for entry in sorted(folder.glob('*')):
        dq._regular_path(entry); dq._sha(entry.name)
        if not entry.is_dir(): raise ValueError('Proposal reservation must be a directory')
        row = {'scope': entry.name, 'baseline_sha256': None}
        path = entry/'reservation.json'
        if path.exists() or path.is_symlink():
            r = dq._json(path)
            dq._keys(r, ('scope', 'baseline_sha256', 'status'), 'Local proposal reservation')
            dq._sha(r['baseline_sha256'])
            if r['scope'] != entry.name or r['status'] != 'RESERVED':
                raise ValueError('Local proposal reservation mismatch')
            row['baseline_sha256'] = r['baseline_sha256']
        rows.append(row)
        if len(rows) > LIMIT: raise ValueError('Too many proposal reservations')
    return rows


def _imported(root):
    from .tabular_handoff import packets
    return merge(*[p['payload']['proposal_memory']['content']['records'] for p in packets(root)
                   if 'proposal_memory' in p['payload']])


def snapshot(root=ROOT):
    root = Path(root).resolve()
    return merge(_local(root), _imported(root))


def assert_available(scope, root=ROOT, *, local_recovery=False):
    root = Path(root).resolve(); dq._sha(scope)
    imported = _imported(root)
    records = merge(_local(root), imported)
    if any(row['scope'] == scope for row in imported):
        raise ValueError('Imported proposal session already reserved; no retry or transferred recovery')
    if not local_recovery and any(row['scope'] == scope for row in records):
        raise ValueError('Proposal session already reserved; preserve failure, no automatic retry')
    # local_recovery merely defers to the proposer's original evidence checks.
    # It cannot authorize a model call or create an exception for imported state.
