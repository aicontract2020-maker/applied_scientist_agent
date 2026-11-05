"""Offline, conservative exchange of SR research exclusions and decisions.

Packets are integrity-checked claims from a trusted colleague, not attestations.
No packet paths are followed, no source is imported, and no model is called.
"""
import json
import re
import tempfile
from pathlib import Path

from .core import digest
from .primary_literature import canonical_paper_url
from .state_lock import research_lock

TASK = 'swinir-s-x2-urban100-selfexsr-8f6dd8c1d20cb7e8792a7177b4f6fd677633f598'
MAX_BYTES = 4 * 1024 * 1024
STATES = {'RESERVED', 'INCOMPLETE', 'REJECTED', 'INVALID', 'STOP', 'CONTINUE', 'PROPOSAL_FAILURE'}
MEASURED_STATES = {'STOP', 'CONTINUE', 'PROPOSAL_FAILURE'}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError(f'Expected a regular JSON file <=4 MiB: {path}')
    def nonfinite(value):
        raise ValueError('Non-finite JSON value: '+value)
    try:
        return json.loads(path.read_text(), object_pairs_hook=_object, parse_constant=nonfinite)
    except RecursionError as exc:
        raise ValueError('Research-memory JSON nesting is too deep') from exc


def _hash(value, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Memory requires lowercase SHA-256 hashes')


def _text(value, limit=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Memory contains missing or oversized text')


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError('Memory object has missing or unexpected fields')


def _ids(values):
    if (not isinstance(values, list) or len(values) > 100 or values != sorted(set(values))
            or any(not isinstance(x, str) or not re.fullmatch(r'img_(?:00[1-9]|0[1-9][0-9]|100)', x) for x in values)):
        raise ValueError('Memory observations must be sorted unique Urban100 original IDs')


def paper_id(url):
    url = canonical_paper_url(url)
    return re.sub(r'v\d+$', '', url.removeprefix('https://arxiv.org/abs/'))


def _papers(values):
    if not isinstance(values, list) or len(values) > 5000 or values != sorted(set(values)):
        raise ValueError('Memory paper IDs must be sorted and unique')
    for value in values:
        if paper_id('https://arxiv.org/abs/'+value) != value:
            raise ValueError('Memory paper IDs must omit version suffixes')


def _route(label, mechanism, disposition, source=None):
    from hashlib import sha256
    if source is not None and len(source.encode()) > 100000:
        raise ValueError('Memory candidate source exceeds 100 KB')
    result = {'label': label, 'mechanism': mechanism, 'disposition': disposition,
              'source': source, 'source_sha256': sha256(source.encode()).hexdigest() if source is not None else None}
    return {'id': digest(result), **result}


def validate(payload):
    _keys(payload, ('schema_version', 'task', 'scored_ids', 'reserved_ids', 'paper_ids', 'routes', 'studies'))
    if type(payload['schema_version']) is not int or payload['schema_version'] != 1 or payload['task'] != TASK:
        raise ValueError('Incompatible research-memory version or task/dataset revision')
    _ids(payload['scored_ids']); _ids(payload['reserved_ids']); _papers(payload['paper_ids'])
    if set(payload['scored_ids']) & set(payload['reserved_ids']):
        raise ValueError('Scored and reserved IDs must be disjoint')
    if not isinstance(payload['routes'], list) or len(payload['routes']) > 5000:
        raise ValueError('Invalid memory routes')
    route_ids = set()
    for route in payload['routes']:
        _keys(route, ('id', 'label', 'mechanism', 'disposition', 'source', 'source_sha256'))
        _text(route['label'], 256); _text(route['mechanism']); _hash(route['id'])
        if route['disposition'] not in ('STOP', 'REJECTED_PROPOSAL'):
            raise ValueError('Memory route must distinguish STOP from proposal rejection')
        if route['source'] is not None:
            _text(route['source'], 100000)
        expected = _route(route['label'], route['mechanism'], route['disposition'], route['source'])
        if route != expected or route['id'] in route_ids:
            raise ValueError('Changed or repeated memory route/hash')
        route_ids.add(route['id'])
    if not isinstance(payload['studies'], list) or len(payload['studies']) > 1000:
        raise ValueError('Invalid memory studies')
    names = set()
    claimed = {}
    for study in payload['studies']:
        _keys(study, ('id', 'policy_sha256', 'state', 'observation_ids', 'plan_sha256', 'candidate_sha256'))
        if not isinstance(study['id'], str) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}', study['id']):
            raise ValueError('Unsafe memory study ID')
        if study['id'] in names or study['state'] not in STATES:
            raise ValueError('Repeated study ID or invalid memory state')
        names.add(study['id'])
        for field in ('policy_sha256', 'plan_sha256', 'candidate_sha256'):
            _hash(study[field], nullable=field != 'policy_sha256')
        _ids(study['observation_ids'])
        excluded = set(payload['scored_ids']) | set(payload['reserved_ids'])
        if not set(study['observation_ids']) <= excluded:
            raise ValueError('Memory study attempts to reclaim reserved observations')
        if study['state'] in MEASURED_STATES and not set(study['observation_ids']) <= set(payload['scored_ids']):
            raise ValueError('A measured study must retain all its scored originals')
        for image in study['observation_ids']:
            if image in claimed:
                raise ValueError(f'Overlapping independent study reservations: {claimed[image]} / {study["id"]}: {image}. Stop and reconcile; no automatic reuse.')
            claimed[image] = study['id']
    return payload


def envelope(payload):
    validate(payload)
    return {'payload': payload, 'sha256': digest(payload)}


def load_packet(path):
    value = read_json(path)
    _keys(value, ('payload', 'sha256'))
    _hash(value['sha256'])
    validate(value['payload'])
    if digest(value['payload']) != value['sha256']:
        raise ValueError('Research-memory checksum mismatch')
    return value


def merge(*payloads):
    """Union exclusions; a terminal decision or frozen identity cannot be replaced."""
    result = {'schema_version': 1, 'task': TASK, 'scored_ids': [], 'reserved_ids': [],
              'paper_ids': [], 'routes': [], 'studies': []}
    scored, reserved, papers, routes, studies = set(), set(), set(), {}, {}
    for payload in payloads:
        validate(payload)
        scored.update(payload['scored_ids']); reserved.update(payload['reserved_ids']); papers.update(payload['paper_ids'])
        for route in payload['routes']:
            routes[route['id']] = route
        for study in payload['studies']:
            old = studies.get(study['id'])
            if old:
                for field in ('policy_sha256', 'observation_ids', 'plan_sha256', 'candidate_sha256'):
                    if old[field] is not None and study[field] is not None and old[field] != study[field]:
                        raise ValueError(f'Conflicting frozen study {study["id"]}: {field}; import did not change memory')
                if old['state'] != study['state'] and 'RESERVED' not in (old['state'], study['state']):
                    raise ValueError(f'Conflicting terminal decision for study {study["id"]}; import did not change memory')
                # A previously exported reservation may be followed by its terminal result.
                chosen = study if old['state'] == 'RESERVED' else old
                studies[study['id']] = {**chosen, **{k: old[k] or study[k] for k in ('plan_sha256', 'candidate_sha256')}}
            else:
                studies[study['id']] = study
    result.update(scored_ids=sorted(scored), reserved_ids=sorted(reserved-scored), paper_ids=sorted(papers),
                  routes=sorted(routes.values(), key=lambda x: x['id']), studies=sorted(studies.values(), key=lambda x: x['id']))
    return validate(result)


def imported(root):
    packets = Path(root)/'.research-memory/packets'
    values = []
    if packets.exists():
        for path in sorted(packets.glob('*.json')):
            packet = load_packet(path)
            if path.stem != packet['sha256']:
                raise ValueError('Stored research-memory packet name/hash mismatch')
            values.append(packet['payload'])
    return merge(*values)


def _source(path):
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100000:
        raise ValueError(f'Invalid candidate source for memory: {path}')
    return path.read_text()


def snapshot(root):
    """Read published, local and explicitly imported history without rewriting any."""
    root = Path(root)
    from .intervention_review import catalog
    history = read_json(root/'templates/sr/history.json')
    policy_template = read_json(root/'templates/sr/policy.json')
    # Preserve existing operator findings without rewriting raw numeric results.
    # A published, code-bound proposal failure is not a scientific route STOP.
    proposal_failures = set()
    for audit_path in (root/'tasks/image_super_resolution').glob('*/evidence/operator-audit.json'):
        audit = read_json(audit_path)
        registration_path = audit_path.parent/'registered.json'
        if audit.get('scientific_new_intervention_requirement_met') is False and registration_path.exists():
            code_hash = read_json(registration_path).get('candidate_sha256')
            _hash(code_hash)
            proposal_failures.add(code_hash)
    routes = []
    for route in catalog(root, []):
        disposition = 'REJECTED_PROPOSAL' if route['id'] == 'G6' else 'STOP'
        routes.append(_route(route['id'], route['mechanism'], disposition, route.get('source')))
    for index, description in enumerate(history.get('rejected_noop_proposals', [])):
        routes.append(_route('NOOP-'+str(index), description, 'REJECTED_PROPOSAL'))
    local = {'schema_version': 1, 'task': TASK, 'scored_ids': sorted(history['used_urban100_ids']),
             'reserved_ids': sorted(set(history.get('reserved_urban100_ids', []))-set(history['used_urban100_ids'])),
             'paper_ids': sorted(policy_template['excluded_evidence_ids']), 'routes': routes, 'studies': []}
    scored, reserved, papers = set(local['scored_ids']), set(local['reserved_ids']), set(local['paper_ids'])
    for file in sorted((root/'local_studies').glob('*/policy.json')):
        policy = read_json(file)
        name = policy['study_id']
        if name != file.parent.name:
            raise ValueError('Local study ID does not match its reservation directory')
        run = root/'runs'/name
        registration = read_json(run/'registered.json') if (run/'registered.json').exists() else None
        result = read_json(run/'result.json') if (run/'result.json').exists() else None
        state = 'INCOMPLETE' if run.exists() else 'RESERVED'
        if result:
            if result.get('status') in ('STOP', 'CONTINUE') and result.get('measurement_valid') is True:
                state = result['status']
            elif result.get('status') == 'REJECTED':
                state = 'REJECTED'
            elif result.get('status') != 'INCOMPLETE':
                state = 'INVALID'
        plan = registration['plan'] if registration else None
        if plan is None and (run/'agent-research.json').exists():
            plan = read_json(run/'agent-research.json')
        for item in (plan or {}).get('new_evidence', []):
            papers.add(paper_id(item['source']))
        if (run/'library.json').exists():
            for paper in read_json(run/'library.json'):
                papers.add(paper_id(paper['url']))
        papers.update(policy['excluded_evidence_ids'])
        ids = policy['observation_ids']
        (scored if state in ('STOP', 'CONTINUE') else reserved).update(ids)
        source = _source(run/'candidate.py') if registration else _source(run/'agent-candidate.py')
        from hashlib import sha256
        code_hash = registration.get('candidate_sha256') if registration else None
        if source is not None:
            actual_hash = sha256(source.encode()).hexdigest()
            if code_hash is not None and actual_hash != code_hash:
                raise ValueError(f'Frozen candidate changed for study {name}')
            code_hash = actual_hash
        if state in ('STOP', 'CONTINUE') and code_hash in proposal_failures:
            state = 'PROPOSAL_FAILURE'
        local['studies'].append({'id': name, 'policy_sha256': digest(policy), 'state': state, 'observation_ids': sorted(ids),
                                 'plan_sha256': digest(plan) if plan is not None else None, 'candidate_sha256': code_hash})
        if plan and state in ('STOP', 'REJECTED', 'PROPOSAL_FAILURE'):
            description = plan.get('hypothesis', 'Rejected proposal')+'; '+(plan.get('stop_route') or (result or {}).get('reason', 'No automatic retry'))
            if state == 'PROPOSAL_FAILURE':
                description = 'Previously published code-bound operator finding: measured proposal failure, not a new scientific intervention: '+description
            if state == 'REJECTED':
                description = 'Proposal rejected before scoring, not scientific falsification: '+description
            local['routes'].append(_route('study:'+name, description, 'STOP' if state == 'STOP' else 'REJECTED_PROPOSAL', source))
    local.update(scored_ids=sorted(scored), reserved_ids=sorted(reserved-scored), paper_ids=sorted(papers))
    return merge(local, imported(root))


def review_catalog(payload):
    return [{'id': 'MEMORY-'+x['id'], 'mechanism': '['+x['disposition']+'; '+x['label']+'] '+x['mechanism'],
             **({'source': x['source'], 'sha256': x['source_sha256']} if x['source'] is not None else {})}
            for x in payload['routes']]


def status(root):
    with research_lock(root):
        value = snapshot(root)
    remaining = 100-len(set(value['scored_ids']) | set(value['reserved_ids']))
    return {'task': TASK, 'memory_sha256': digest(value), 'scored_originals': len(value['scored_ids']),
            'reserved_unscored_originals': len(value['reserved_ids']), 'unused_originals': remaining,
            'full_12_image_cycles_remaining': remaining//12, 'read_papers': len(value['paper_ids']),
            'stopped_route_records': sum(x['disposition'] == 'STOP' for x in value['routes']),
            'rejected_proposal_records': sum(x['disposition'] == 'REJECTED_PROPOSAL' for x in value['routes']),
            'studies': value['studies'], 'coordination': 'Host-local lock and explicit snapshot exchange; no distributed live registry'}


def export_memory(root, output):
    with research_lock(root):
        packet = envelope(snapshot(root))
        encoded = json.dumps(packet, indent=2, ensure_ascii=False, allow_nan=False)+'\n'
        if len(encoded.encode()) > MAX_BYTES:
            raise ValueError('Research memory exceeds 4 MiB exchange limit; no partial export written')
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as handle:
            handle.write(encoded)
    return {'status': 'EXPORTED', 'file': str(path.resolve()), 'sha256': packet['sha256'],
            'sharing_note': 'Contains hypothesis/STOP text and candidate code; review for proprietary material before sharing. No papers, arrays, events or credentials.'}


def import_memory(root, source):
    # Validate an entire external packet before creating the store or mutating exclusions.
    packet = load_packet(source)
    with research_lock(root):
        current = snapshot(root)
        combined = merge(current, packet['payload'])
        store = Path(root)/'.research-memory/packets'
        destination = store/(packet['sha256']+'.json')
        if destination.exists():
            if load_packet(destination) != packet:
                raise ValueError('Existing memory packet content changed')
            return {'status': 'ALREADY_IMPORTED', 'sha256': packet['sha256']}
        store.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=store, prefix='.import-', delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(packet, handle, indent=2, ensure_ascii=False, allow_nan=False)
                handle.write('\n'); handle.flush()
                import os
                os.fsync(handle.fileno())
            temporary.replace(destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {'status': 'IMPORTED', 'sha256': packet['sha256'],
            'scored_originals': len(combined['scored_ids']), 'reserved_unscored_originals': len(combined['reserved_ids']),
            'note': 'Exclusions only grow. Imported claims are trusted, not authenticated or independently revalidated.'}
