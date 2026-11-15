"""One atomic, additive handoff of tabular exclusions and all local data pauses.

Version 3 also carries proposal occupancy; private evidence and SR stay separate. Imported
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
PACKET_LIMIT = 20*1024*1024
VERSION_LIMITS = {1: 12*1024*1024, 2: 16*1024*1024, 3: PACKET_LIMIT}


def _encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8')


def envelope(memory, blocks, airfoil=None, proposals=None):
    payload = {'kind': KIND, 'version': 1, 'tabular_memory': memory, 'data_blocks': blocks}
    if airfoil is not None:
        payload.update(version=2, airfoil_memory=airfoil)
    if proposals is not None:
        if airfoil is None: raise ValueError('v3 requires Airfoil and proposal components')
        payload.update(version=3, proposal_memory=proposals)
    return {'payload': payload, 'sha256': digest(payload)}


def validate(packet):
    from . import tabular_memory as tm, data_blocks as db, airfoil_memory as am, proposal_memory as pm
    dq._keys(packet, ('payload', 'sha256'), 'combined handoff')
    dq._sha(packet['sha256'])
    p = packet['payload']
    if not isinstance(p, dict) or type(p.get('version')) is not int or p['version'] not in VERSION_LIMITS:
        raise ValueError('Unsupported combined handoff kind/version')
    components = ('tabular_memory', 'data_blocks') + (('airfoil_memory',) if p['version'] >= 2 else ()) + (('proposal_memory',) if p['version'] == 3 else ())
    dq._keys(p, ('kind', 'version', *components), 'combined handoff payload')
    if p['kind'] != KIND:
        raise ValueError('Unsupported combined handoff kind/version')
    tm.validate_packet(p['tabular_memory'])
    db._validate(p['data_blocks'])
    if p['version'] >= 2: am.validate_packet(p['airfoil_memory'])
    if p['version'] == 3: pm.validate_packet(p['proposal_memory'])
    for name in components:
        if len(_encoded(p[name])) > COMPONENT_LIMIT:
            raise ValueError('Combined handoff component exceeds 4 MiB')
    if packet['sha256'] != digest(p):
        raise ValueError('Changed combined handoff checksum')
    if len(_encoded(packet)) > VERSION_LIMITS[p['version']]:
        raise ValueError('Combined handoff exceeds version size limit')
    return packet


def load_packet(path):
    try:
        raw = dq._read(path, PACKET_LIMIT)
        packet = validate(json.loads(raw.decode('utf-8'), object_pairs_hook=dq._object, parse_constant=dq._nonfinite))
        version = packet['payload']['version']
        if len(raw) > VERSION_LIMITS[version]:
            raise ValueError(f'Legacy v{version} handoff exceeds {VERSION_LIMITS[version]//(1024*1024)} MiB size limit')
        return packet
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
    from . import tabular_memory as tm, data_blocks as db, airfoil_memory as am, proposal_memory as pm
    return validate(envelope(tm.envelope(tm.snapshot(root)), db._envelope(db._load(root)),
                             am.envelope(am.snapshot(root)), pm.envelope(pm.snapshot(root))))


def _summary(packet):
    p = packet['payload']
    return {'sha256': packet['sha256'],
            'version': p['version'],
            'tabular_records': len(p['tabular_memory']['payload']['records']),
            'data_block_records': len(p['data_blocks']['content']['records']),
            'airfoil_records': len(p['airfoil_memory']['content']['records']) if p['version'] >= 2 else None,
            'proposal_records': len(p['proposal_memory']['content']['records']) if p['version'] == 3 else None,
            'execution_authorized': False, 'authenticity': 'UNVERIFIED',
            'scope': 'Tabular exclusions, data pauses'+(' and Airfoil exclusions' if p['version'] >= 2 else '; Airfoil NOT_INCLUDED')
                     + ('; tabular proposal occupancy' if p['version'] == 3 else '; proposer NOT_INCLUDED')
                     + '; no SR reservations, recovery authority or private evidence'}


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
        os.link(temporary, target)  # Atomic visibility of all components; never replace.
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def export(output, root=ROOT):
    with research_lock(root):
        packet = _snapshot(root)
        _publish(packet, output)
    return {'status': 'EXPORTED', **_summary(packet),
            'sharing_note': 'Contains route/source text, row fingerprints, reviewer names and pause reasons. Review before sharing.'}


def import_state(path, root=ROOT):
    from . import tabular_memory as tm, data_blocks as db, airfoil_memory as am, proposal_memory as pm
    packet = load_packet(path)
    with research_lock(root):
        # Complete validation/union of every component before publication.
        merged_memory = tm.envelope(tm.merge(tm.snapshot(root), packet['payload']['tabular_memory']['payload']['records']))
        merged_blocks = db._envelope(db.merge(db._load(root), packet['payload']['data_blocks']['content']['records']))
        incoming_airfoil = packet['payload'].get('airfoil_memory', am.envelope([]))['content']['records']
        merged_airfoil = am.envelope(am.merge(am.snapshot(root), incoming_airfoil))
        incoming_proposals = packet['payload'].get('proposal_memory', pm.envelope([]))['content']['records']
        merged_proposals = pm.envelope(pm.merge(pm.snapshot(root), incoming_proposals))
        merged = validate(envelope(merged_memory, merged_blocks, merged_airfoil, merged_proposals))
        folder = _folder(root); target = folder/(packet['sha256']+'.json')
        if target.exists() or target.is_symlink():
            if load_packet(target) != packet: raise ValueError('Stored combined handoff changed')
            state = 'ALREADY_IMPORTED'
        else:
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            _publish(packet, target)
            state = 'IMPORTED'
    return {'status': state, **_summary(packet), 'merged_state': _summary(merged),
            'note': 'All supplied components retained together; absent legacy components never clear local records.'}
