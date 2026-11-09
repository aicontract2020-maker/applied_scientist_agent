"""One atomic, additive handoff of tabular exclusions and all local data pauses.

Private evidence and Airfoil/SR reservations are outside this format. Imported
state is a conservative claim, never authenticated evidence or execution approval.
"""
import json
import os
from pathlib import Path
import tempfile

from . import data_qualification as dq
from .core import digest
from .portable import ROOT
from .state_lock import research_lock

KIND = 'research-harness-tabular-state-handoff'
COMPONENT_LIMIT = 4*1024*1024
PACKET_LIMIT = 12*1024*1024


def _encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8')


def envelope(memory, blocks):
    payload = {'kind': KIND, 'version': 1, 'tabular_memory': memory, 'data_blocks': blocks}
    return {'payload': payload, 'sha256': digest(payload)}


def validate(packet):
    from . import tabular_memory as tm, data_blocks as db
    dq._keys(packet, ('payload', 'sha256'), 'combined handoff')
    dq._sha(packet['sha256'])
    p = packet['payload']
    dq._keys(p, ('kind', 'version', 'tabular_memory', 'data_blocks'), 'combined handoff payload')
    if p['kind'] != KIND or type(p['version']) is not int or p['version'] != 1:
        raise ValueError('Unsupported combined handoff kind/version')
    tm.validate_packet(p['tabular_memory'])
    db._validate(p['data_blocks'])
    for name in ('tabular_memory', 'data_blocks'):
        if len(_encoded(p[name])) > COMPONENT_LIMIT:
            raise ValueError('Combined handoff component exceeds 4 MiB')
    if packet['sha256'] != digest(p):
        raise ValueError('Changed combined handoff checksum')
    if len(_encoded(packet)) > PACKET_LIMIT:
        raise ValueError('Combined handoff exceeds 12 MiB')
    return packet


def load_packet(path):
    try:
        raw = dq._read(path, PACKET_LIMIT).decode('utf-8')
        return validate(json.loads(raw, object_pairs_hook=dq._object, parse_constant=dq._nonfinite))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Invalid combined handoff encoding/nesting') from exc


def _folder(root):
    return dq._regular_path(Path(root).resolve()/'.research-memory/tabular-state-handoff')


def packets(root):
    """Pure reader used by both legacy state readers; never calls their snapshots."""
    folder = _folder(root)
    if folder.exists() and not folder.is_dir():
        raise ValueError('Combined handoff state must be a directory')
    result = []
    for path in sorted(folder.glob('*.json')):
        packet = load_packet(path)
        if path.stem != packet['sha256']:
            raise ValueError('Stored combined handoff filename/checksum mismatch')
        result.append(packet)
    return result


def _snapshot(root):
    from . import tabular_memory as tm, data_blocks as db
    return validate(envelope(tm.envelope(tm.snapshot(root)), db._envelope(db._load(root))))


def _summary(packet):
    p = packet['payload']
    return {'sha256': packet['sha256'],
            'tabular_records': len(p['tabular_memory']['payload']['records']),
            'data_block_records': len(p['data_blocks']['content']['records']),
            'execution_authorized': False, 'authenticity': 'UNVERIFIED',
            'scope': 'Tabular exclusions and data pauses only; not Airfoil/SR reservations or private evidence'}


def status(root=ROOT):
    # No lock/file creation. This is an observation, not a concurrency guarantee.
    packet = _snapshot(root)
    return {'status': 'STATE_SNAPSHOT', 'read_only': True, 'root': str(Path(root).resolve()), **_summary(packet)}


def verify(path):
    return {'status': 'VERIFIED_FORMAT', 'read_only': True, **_summary(load_packet(path)),
            'note': 'No local merge, scientific audit, import or execution was performed.'}


def _publish(packet, target):
    """A single no-overwrite hard-link publish; readers never see partial JSON."""
    target = dq._regular_path(target)
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(_encoded(packet)); handle.flush(); os.fsync(handle.fileno())
        dq._regular_path(target)
        os.link(temporary, target)  # Atomic visibility of both components; never replace.
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def export(output, root=ROOT):
    with research_lock(root):
        packet = _snapshot(root)
        _publish(packet, output)
    return {'status': 'EXPORTED', **_summary(packet),
            'sharing_note': 'Contains route/source text, row fingerprints, reviewer names and pause reasons. Review before sharing.'}


def import_state(path, root=ROOT):
    from . import tabular_memory as tm, data_blocks as db
    packet = load_packet(path)
    with research_lock(root):
        # Complete validation/union before any new state directory or publication.
        merged_memory = tm.envelope(tm.merge(tm.snapshot(root), packet['payload']['tabular_memory']['payload']['records']))
        merged_blocks = db._envelope(db.merge(db._load(root), packet['payload']['data_blocks']['content']['records']))
        merged = validate(envelope(merged_memory, merged_blocks))
        folder = _folder(root); target = folder/(packet['sha256']+'.json')
        if target.exists() or target.is_symlink():
            if load_packet(target) != packet: raise ValueError('Stored combined handoff changed')
            state = 'ALREADY_IMPORTED'
        else:
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            _publish(packet, target)
            state = 'IMPORTED'
    return {'status': state, **_summary(packet), 'merged_state': _summary(merged),
            'note': 'Both components retained together; no prior exclusions, pauses or decisions removed.'}
