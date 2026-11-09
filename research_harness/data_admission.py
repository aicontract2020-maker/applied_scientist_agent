"""C4 evidence bound to a closed adapter's baseline or candidate, never approval.

Snapshots are copied into the execution review, not fetched from mutable paths at
run time. Historical review-only loading does not grant a legacy execution path.
"""
from copy import deepcopy
import json

from . import data_qualification as dq
from .core import digest
from .portable import ROOT

KIND = 'research-harness-baseline-data-admission'
TRIAL_KIND = 'research-harness-candidate-data-admission'
TRIAL_ADAPTERS = ('abalone-candidate-v1', 'airfoil-candidate-v1')
ADAPTERS = ('abalone-baseline-v1', 'airfoil-baseline-v1', *TRIAL_ADAPTERS)


def _kind(adapter):
    return TRIAL_KIND if adapter in TRIAL_ADAPTERS else KIND


def context(adapter, source, intended_use):
    if adapter not in ADAPTERS:
        raise ValueError('Unknown data admission adapter; no generic execution fallback')
    dq._text(intended_use, 'Explicit intended use')
    return {'task': adapter, 'dataset': {'id': source['id'], 'version': '1',
            'source': source.get('url', source['id'])}, 'intended_use': intended_use}


def validate_snapshot(snapshot, expected):
    dq._keys(snapshot, ('packet', 'decision'), 'accepted qualification snapshot')
    packet, decision = snapshot['packet'], snapshot['decision']
    for envelope in (packet, decision):
        dq._keys(envelope, ('content', 'sha256'), 'qualification envelope')
        dq._sha(envelope['sha256'])
        if digest(envelope['content']) != envelope['sha256']:
            raise ValueError('Data qualification snapshot checksum mismatch')
    dq._validate(packet['content'], embedded=True)
    dq._validate_decision(decision, packet)
    if decision['content']['decision'] != 'accept':
        raise ValueError('Data qualification has not been accepted')
    content = packet['content']
    if {key: content[key] for key in expected} != expected:
        raise ValueError('Data qualification task, dataset/version or intended use differs')


def assert_source_allowed(source, root=ROOT):
    from .data_blocks import assert_allowed
    assert_allowed({'id': source['id'], 'version': '1',
                    'source': source.get('url', source['id'])}, root)


def accepted_snapshot(path, adapter, source, intended_use, *, root=ROOT):
    if path is None:
        raise ValueError('Accepted data qualification is required before preparing real data')
    expected = context(adapter, source, intended_use)
    assert_source_allowed(source, root)
    snapshot = {'packet': dq.load_packet(path), 'decision': dq._load_envelope(dq._decision_path(path))}
    validate_snapshot(snapshot, expected)
    return snapshot


def bind(snapshot, adapter, source, intended_use, files, recipe):
    expected = context(adapter, source, intended_use)
    validate_snapshot(snapshot, expected)
    return {'kind': _kind(adapter), 'version': 1, 'context': expected,
            'qualification': deepcopy(snapshot), 'data_files': deepcopy(files), 'recipe_sha256': digest(recipe)}


def verify(content, adapter, *, required):
    if 'data_admission' not in content:
        if required:
            raise ValueError('Real-data execution requires data admission; legacy bundles are audit-only')
        return None
    entry = content['data_admission']
    dq._keys(entry, ('kind', 'version', 'context', 'qualification', 'data_files', 'recipe_sha256'), 'data admission')
    if entry['kind'] != _kind(adapter) or type(entry['version']) is not int or entry['version'] != 1:
        raise ValueError('Unknown data admission version')
    dq._keys(entry['context'], ('task', 'dataset', 'intended_use'), 'admission context')
    expected = context(adapter, content['source'], entry['context']['intended_use'])
    if entry['context'] != expected:
        raise ValueError('Data admission adapter or source differs from review')
    validate_snapshot(entry['qualification'], expected)
    if entry['data_files'] != content['files'] or entry['recipe_sha256'] != digest(content['recipe']):
        raise ValueError('Data admission partition or recipe binding changed')
    return {'qualification_sha256': entry['qualification']['packet']['sha256'],
            'data_decision_sha256': entry['qualification']['decision']['sha256'],
            'adapter': adapter, 'execution_authorized': False}


def trial_snapshot(baseline, adapter, fixture, path, intended_use, *, root=ROOT):
    if adapter not in TRIAL_ADAPTERS:
        raise ValueError('Candidate qualification requires a candidate adapter')
    source = baseline['content']['source']
    assert_source_allowed(source, root)
    if source == fixture and path is None and intended_use is None:
        return None  # Internal software fixtures only; never public raw-data intake.
    return accepted_snapshot(path, adapter, source, intended_use, root=root)


def _trial_recipe(content, baseline):
    return {'recipe': content['recipe'], 'proposal': content['proposal'],
            'baseline_sha256': baseline['sha256']}


def bind_trial(snapshot, adapter, baseline, content, intended_use):
    if adapter not in TRIAL_ADAPTERS:
        raise ValueError('Candidate qualification requires a candidate adapter')
    return bind(snapshot, adapter, baseline['content']['source'], intended_use,
                baseline['content']['files'], _trial_recipe(content, baseline))


def verify_trial(content, baseline, adapter, *, required):
    if adapter not in TRIAL_ADAPTERS:
        raise ValueError('Candidate qualification requires a candidate adapter')
    if 'data_admission' not in content:
        if required: raise ValueError('Real candidate execution requires data admission; legacy trials are audit-only')
        return None
    return verify({'data_admission': content['data_admission'], 'source': baseline['content']['source'],
                   'files': baseline['content']['files'], 'recipe': _trial_recipe(content, baseline)},
                  adapter, required=True)


def check_packet_size(content):
    # Match the baseline writer's ASCII-escaped encoding and reader's 4 MiB limit.
    packet = {'content': content, 'sha256': digest(content)}
    if len((json.dumps(packet, indent=2, allow_nan=False) + '\n').encode()) > dq.PACKET_LIMIT:
        raise ValueError('Combined baseline review exceeds 4 MiB; no output created')


def review_note(content, filename='bundle.json'):
    entry = content.get('data_admission')
    if entry is None:
        return ''
    return ('\n## Data qualification (protocol design only)\n\n'
            f'The accepted evidence and decision are embedded in {filename}. Read their full '
            'content before independently approving this execution. No raw metadata is sent to the worker.\n\n'
            '```json\n' + json.dumps({'context': entry['context'],
                'qualification_sha256': entry['qualification']['packet']['sha256'],
                'decision_sha256': entry['qualification']['decision']['sha256']}, indent=2, ensure_ascii=False) + '\n```\n')
