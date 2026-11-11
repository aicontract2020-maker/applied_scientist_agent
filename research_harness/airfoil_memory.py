"""Conservative Airfoil baseline/candidate exclusions; no scientific evaluation.

Read published metadata, local reservations and unified imports. Missing terminal
details never free a reservation. Hashes are claims, not authenticated execution.
"""
from pathlib import Path

from . import data_qualification as dq
from .core import digest
from .portable import ROOT

KIND = 'research-harness-airfoil-memory'
FIELDS = ('phase', 'scope', 'review_sha256', 'mechanism', 'state', 'result_sha256')
STATES = ('RESERVED', 'STOP', 'CONTINUE', 'INVALID')


def validate(record):
    dq._keys(record, FIELDS, 'Airfoil memory record')
    if record['phase'] not in ('baseline', 'candidate') or record['state'] not in STATES:
        raise ValueError('Invalid Airfoil memory phase/state')
    dq._sha(record['scope'])
    for name in ('review_sha256', 'result_sha256'):
        if record[name] is not None: dq._sha(record[name])
    if record['state'] == 'RESERVED' and record['result_sha256'] is not None:
        raise ValueError('Reserved Airfoil state cannot carry a terminal result')
    if record['state'] != 'RESERVED' and record['review_sha256'] is None:
        raise ValueError('Terminal Airfoil state requires a review binding')
    if record['phase'] == 'baseline':
        if record['mechanism'] is not None: raise ValueError('Baseline memory cannot assert a candidate mechanism')
    else:
        dq._text(record['mechanism'], 'Airfoil mechanism')
    return record


def merge(*groups):
    records = {}
    for group in groups:
        if not isinstance(group, list) or len(group) > 1000: raise ValueError('Invalid Airfoil history size')
        for value in group:
            item = dict(validate(value)); key = (item['phase'], item['scope']); old = records.get(key)
            if old is not None:
                for field in ('review_sha256', 'mechanism', 'result_sha256'):
                    if old[field] is not None and item[field] is not None and old[field] != item[field]:
                        raise ValueError('Conflicting Airfoil memory binding: '+field)
                if old['state'] != 'RESERVED' and item['state'] != 'RESERVED' and old['state'] != item['state']:
                    raise ValueError('Conflicting Airfoil terminal decisions')
                chosen = old if old['state'] != 'RESERVED' else item
                item = {**chosen, **{k: old[k] if old[k] is not None else item[k]
                                    for k in ('review_sha256', 'mechanism', 'result_sha256')}}
            records[key] = validate(item)
    if len(records) > 1000: raise ValueError('Too many Airfoil reservations')
    return [records[k] for k in sorted(records)]


def envelope(records):
    content = {'kind': KIND, 'version': 1, 'records': merge(records)}
    return {'content': content, 'sha256': digest(content)}


def validate_packet(packet):
    dq._keys(packet, ('content', 'sha256'), 'Airfoil memory envelope')
    dq._keys(packet['content'], ('kind', 'version', 'records'), 'Airfoil memory')
    c = packet['content']
    if c['kind'] != KIND or type(c['version']) is not int or c['version'] != 1 or packet != envelope(c['records']):
        raise ValueError('Invalid/noncanonical Airfoil memory envelope')
    return packet


def _baseline_decision(value, review_sha):
    dq._keys(value, ('review_sha256', 'result_sha256', 'status', 'measurement_valid'), 'Airfoil baseline decision')
    dq._sha(value['result_sha256'])
    if (value['review_sha256'] != review_sha or value['status'] not in ('STOP', 'CONTINUE')
            or type(value['measurement_valid']) is not bool
            or (not value['measurement_valid'] and value['status'] != 'STOP')):
        raise ValueError('Invalid Airfoil baseline terminal binding')
    return value['status'] if value['measurement_valid'] else 'INVALID'


def _published(root):
    from .airfoil_baseline import scope
    from .airfoil_data import SOURCE
    records = []
    base = root/'tasks/airfoil_noise/a1'
    manifest, decision = base/'review-manifest.json', base/'reservation-decision.json'
    if any(p.exists() or p.is_symlink() for p in (manifest, decision)):
        packet, result = dq._json(manifest), dq._json(decision)
        dq._keys(packet, ('content', 'sha256'), 'Published Airfoil baseline')
        if packet['sha256'] != digest(packet['content']) or packet['content']['source'] != SOURCE:
            raise ValueError('Published Airfoil baseline metadata changed')
        state = _baseline_decision(result, packet['sha256'])
        records.append({'phase': 'baseline', 'scope': scope(packet), 'review_sha256': packet['sha256'],
                        'mechanism': None, 'state': state, 'result_sha256': result['result_sha256']})
    path = root/'tasks/airfoil_noise/trial-history.json'
    if path.exists() or path.is_symlink():
        rows = dq._json(path)
        if not isinstance(rows, list) or len(rows) > 1000: raise ValueError('Invalid published Airfoil history')
        for r in rows:
            dq._keys(r, ('scope', 'mechanism', 'review_sha256', 'status'), 'Published Airfoil candidate')
            records.append({'phase': 'candidate', 'scope': r['scope'], 'review_sha256': r['review_sha256'],
                            'mechanism': r['mechanism'], 'state': r['status'], 'result_sha256': None})
    return merge(records)


def _local(root, phase):
    from .airfoil_trial import MECHANISM
    folder = dq._regular_path(root/'.research-memory'/('airfoil-baseline' if phase == 'baseline' else 'airfoil-trial'))
    if folder.exists() and not folder.is_dir(): raise ValueError('Airfoil memory must be a directory')
    records = []
    for entry in sorted(folder.glob('*')):
        dq._regular_path(entry); dq._sha(entry.name)
        if not entry.is_dir(): raise ValueError('Airfoil reservation must be a directory')
        row = {'phase': phase, 'scope': entry.name, 'review_sha256': None,
               'mechanism': None if phase == 'baseline' else MECHANISM, 'state': 'RESERVED', 'result_sha256': None}
        reservation, decision = entry/'reservation.json', entry/'decision.json'
        if reservation.exists() or reservation.is_symlink():
            r = dq._json(reservation)
            fields = ('review_sha256', 'status') if phase == 'baseline' else ('review_sha256', 'scope', 'mechanism', 'status')
            dq._keys(r, fields, 'Local Airfoil reservation'); dq._sha(r['review_sha256'])
            if r['status'] != 'RESERVED': raise ValueError('Invalid Airfoil reservation state')
            if phase == 'candidate' and (r['scope'] != entry.name or r['mechanism'] != MECHANISM):
                raise ValueError('Airfoil reservation scope/mechanism differs')
            row['review_sha256'] = r['review_sha256']
        if decision.exists() or decision.is_symlink():
            if row['review_sha256'] is None: raise ValueError('Airfoil decision without reservation binding')
            d = dq._json(decision)
            if phase == 'baseline': row['state'] = _baseline_decision(d, row['review_sha256'])
            else:
                dq._keys(d, ('scope', 'mechanism', 'review_sha256', 'status', 'result_sha256'), 'Local Airfoil decision')
                if any(d[k] != row[k] for k in ('scope', 'mechanism', 'review_sha256')) or d['status'] not in STATES[1:]:
                    raise ValueError('Airfoil terminal decision binding differs')
                row['state'] = d['status']
            dq._sha(d['result_sha256']); row['result_sha256'] = d['result_sha256']
        records.append(validate(row))
    return records


def snapshot(root=ROOT):
    from .tabular_handoff import packets
    root = Path(root).resolve()
    imported = [p['payload']['airfoil_memory']['content']['records'] for p in packets(root)
                if 'airfoil_memory' in p['payload']]
    return merge(_published(root), _local(root, 'baseline'), _local(root, 'candidate'), *imported)


def assert_available(phase, scope, root=ROOT, mechanism=None):
    for row in snapshot(root):
        if row['phase'] != phase: continue
        if row['scope'] == scope:
            raise ValueError('Airfoil data already reserved/consumed in retained memory; no retry')
        if phase == 'candidate' and row['state'] == 'STOP' and row['mechanism'] == mechanism:
            raise ValueError('Stopped Airfoil mechanism in retained memory; no new-data rescue')
