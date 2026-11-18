"""Bounded local SR intake for unified handoff; scientific merge stays in memory."""
from pathlib import Path

from . import memory
from .data_qualification import _regular_path, _read


def snapshot(root):
    """Empty receiving roots are allowed, but incomplete SR histories are not empty."""
    root = Path(root).resolve()
    from .intervention_review import HISTORICAL
    template = _regular_path(root/'templates/sr')
    local = _regular_path(root/'local_studies')
    published = _regular_path(root/'tasks/image_super_resolution')
    for folder in (template, local, published):
        if folder.exists() and not folder.is_dir():
            raise ValueError('SR metadata location must be a directory')
    historical = [root/path for _, _, path in HISTORICAL]
    if not template.exists():
        if (published.exists() or (local.exists() and any(local.iterdir()))
                or any(p.exists() or p.is_symlink() for p in historical)):
            raise ValueError('Incomplete SR history: required templates missing')
        return memory.imported(root)
    # Validate every file the legacy snapshot will read before interpreting it.
    required = [template/'history.json', template/'policy.json']
    optional = list(historical)
    for entry in sorted(local.glob('*')):
        _regular_path(entry)
        if not entry.is_dir(): raise ValueError('SR reservation must be a directory')
        required.append(entry/'policy.json')  # An empty reservation never means free data.
        run = _regular_path(root/'runs'/entry.name)
        if run.exists() and not run.is_dir(): raise ValueError('SR run must be a directory')
        optional.extend(run/name for name in ('registered.json', 'result.json', 'agent-research.json',
                                              'library.json', 'candidate.py', 'agent-candidate.py'))
    for entry in sorted(published.glob('*')):
        _regular_path(entry)
        if entry.is_dir():
            optional.extend(entry/name for name in ('candidate.py', 'research.json',
                'evidence/operator-audit.json', 'evidence/registered.json', 'evidence/result.json'))
    for path in required:
        _read(path, memory.MAX_BYTES)
    for path in optional:
        _regular_path(path)
        if path.exists(): _read(path, memory.MAX_BYTES)
    return memory.snapshot(root)


def records(payload):
    """Stable comparison rows for preview, including individual image exclusions."""
    return ([{'scope': 'study:'+r['id'], 'value': r} for r in payload['studies']]
            + [{'scope': 'route:'+r['id'], 'value': r} for r in payload['routes']]
            + [{'scope': 'paper:'+p, 'value': p} for p in payload['paper_ids']]
            + [{'scope': 'image:'+i, 'value': state}
               for field, state in (('scored_ids', 'SCORED'), ('reserved_ids', 'RESERVED'))
               for i in payload[field]])
