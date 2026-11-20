"""Read-only SR launch admission and supported command entry points.

This is an integrity/state gate, not authentication or a scientific approval.
Low-level controller objects remain trusted Python software primitives.
"""
import hashlib
from pathlib import Path, PurePosixPath

from . import memory, sr_handoff
from .core import digest
from .data_qualification import _json, _keys, _read, _regular_path, _sha
from .portable import ROOT
from .state_lock import research_lock


def preflight(study, destination=None, *, root=ROOT):
    root = Path(root).resolve()
    study = _regular_path(study)
    if study.parent != root/'local_studies' or not study.is_dir():
        raise ValueError('SR launch requires a local_studies/ID reservation in this checkout; historical/evidence copies are read-only')
    policy = _json(study/'policy.json')
    if not isinstance(policy, dict) or policy.get('study_id') != study.name:
        raise ValueError('SR reservation identity differs from policy')
    from .task_contracts import validate_sr_policy, binding, SR_TASK
    validate_sr_policy(policy)
    if policy.get('task') != binding(SR_TASK):
        raise ValueError('SR launch requires the current explicit task binding')
    output = _regular_path(destination if destination is not None else root/'runs'/study.name)
    if output != root/'runs'/study.name:
        raise ValueError('SR output must be this checkout runs/ID; alternate destinations cannot bypass one attempt')
    if output.exists():
        raise ValueError('SR attempt already exists; no overwrite or retry')
    if (study/'EVIDENCE_ONLY.json').exists() or (study/'EVIDENCE_ONLY.json').is_symlink():
        raise ValueError('Imported SR evidence is read-only')
    frozen = _json(study/'inputs.lock.json')
    _keys(frozen, ('files', 'runtime'), 'SR input lock')
    if not isinstance(frozen['runtime'], dict) or frozen['runtime'].get('checkout') != str(root):
        raise ValueError('SR preparation belongs to another checkout or lacks launch provenance; no imported execution authority')
    files = frozen['files']
    if not isinstance(files, dict) or not files or len(files) > 10000:
        raise ValueError('Invalid frozen SR file inventory')
    required = {str((study/name).relative_to(root)) for name in
                ('policy.json', 'memory.json', 'selection.json', 'intervention-catalog.json', 'TASK.md', 'literature.json', 'labctl.py')}
    sources = {str(p.relative_to(root)) for p in (root/'research_harness').glob('*.py')}
    if not required <= set(files) or {p for p in files if p.startswith('research_harness/')} != sources:
        raise ValueError('Incomplete or stale SR frozen file inventory')
    for name, expected in files.items():
        path = PurePosixPath(name)
        if path.is_absolute() or str(path) != name or '..' in path.parts or '\\' in name:
            raise ValueError('Unsafe frozen SR path')
        _sha(expected)
        # Fixed task artifacts only; bound reads also reject FIFOs and linked parents.
        if hashlib.sha256(_read(root/name, 256*1024*1024)).hexdigest() != expected:
            raise ValueError('Frozen trusted input changed: '+name)
    frozen_memory = memory.validate_packet(_json(study/'memory.json'))['payload']
    ids = policy.get('observation_ids')
    memory._ids(ids)
    if len(ids) != 12 or set(ids) & set(frozen_memory['scored_ids']+frozen_memory['reserved_ids']):
        raise ValueError('SR reservation must contain twelve previously unused originals')
    selection = _json(study/'selection.json')
    _keys(selection, ('selected_ids', 'excluded_ids', 'rule'), 'SR selection')
    if (selection.get('selected_ids') != ids or selection.get('excluded_ids') !=
            sorted(set(frozen_memory['scored_ids']+frozen_memory['reserved_ids']))):
        raise ValueError('SR selection differs from frozen exclusions')
    current = sr_handoff.snapshot(root)
    own = [r for r in current['studies'] if r['id'] == study.name]
    expected = {'id': study.name, 'policy_sha256': digest(policy), 'state': 'RESERVED',
                'observation_ids': ids, 'plan_sha256': None, 'candidate_sha256': None}
    if own != [expected] or set(ids) & set(current['scored_ids']):
        raise ValueError('SR reservation is no longer unexecuted or has changed binding')
    prior = {**current, 'studies': [r for r in current['studies'] if r['id'] != study.name],
             'reserved_ids': sorted(set(current['reserved_ids'])-set(ids))}
    if memory.merge(prior) != memory.merge(frozen_memory):
        raise ValueError('SR constraints changed since preparation; no refresh, release or automatic retry')
    details = {'study_id': study.name, 'study': str(study), 'destination': str(output),
               'policy_sha256': digest(policy), 'input_lock_sha256': digest(frozen),
               'frozen_memory_sha256': digest(frozen_memory), 'current_memory_sha256': digest(current)}
    return {'status': 'READY_FOR_LAUNCH_CHECKS', 'read_only': True, 'execution_authorized': False,
            **details, 'preflight_sha256': digest(details),
            'note': 'No environment/credential/isolation probe, model call or experiment; startup checks remain required'}


def _launch_locked(destination, study, *, literature=False, root=ROOT, checked_health=None):
    """Caller holds the checkout lock through the entire controller session."""
    before = preflight(study, destination, root=root)
    if checked_health is None:
        from .doctor import doctor
        checked_health = doctor()
    if not checked_health['ok']:
        raise ValueError('SR environment/isolation preflight failed; no model call or run created')
    after = preflight(study, destination, root=root)
    if before != after:
        raise ValueError('SR launch state changed during environment checks')
    from .autonomy import AutonomousStudy
    from .literature_study import LiteratureStudy
    controller = LiteratureStudy if literature else AutonomousStudy
    return controller(destination, study).launch()


def launch(destination, study=None, *, literature=False):
    if study is None:
        raise ValueError('Explicit prepared --study is required; historical default tasks cannot be restarted')
    with research_lock(ROOT):
        return _launch_locked(destination, study, literature=literature, root=ROOT)
