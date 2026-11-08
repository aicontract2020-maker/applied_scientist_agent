"""C4 evidence bound to a closed adapter's new baseline review, never approval.

Snapshots are copied into the execution review, not fetched from mutable paths at
run time. Historical review-only loading does not grant a legacy execution path.
"""
from copy import deepcopy
import json

from . import data_qualification as dq
from .core import digest

KIND = 'research-harness-baseline-data-admission'
ADAPTERS = ('abalone-baseline-v1', 'airfoil-baseline-v1')


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


def accepted_snapshot(path, adapter, source, intended_use):
    if path is None:
        raise ValueError('Accepted data qualification is required before preparing real data')
    expected = context(adapter, source, intended_use)
    snapshot = {'packet': dq.load_packet(path), 'decision': dq._load_envelope(dq._decision_path(path))}
    validate_snapshot(snapshot, expected)
    return snapshot


def bind(snapshot, adapter, source, intended_use, files, recipe):
    expected = context(adapter, source, intended_use)
    validate_snapshot(snapshot, expected)
    return {'kind': KIND, 'version': 1, 'context': expected,
            'qualification': deepcopy(snapshot), 'data_files': deepcopy(files), 'recipe_sha256': digest(recipe)}


def verify(content, adapter, *, required):
    if 'data_admission' not in content:
        if required:
            raise ValueError('Real-data execution requires data admission; legacy bundles are audit-only')
        return None
    entry = content['data_admission']
    dq._keys(entry, ('kind', 'version', 'context', 'qualification', 'data_files', 'recipe_sha256'), 'data admission')
    if entry['kind'] != KIND or type(entry['version']) is not int or entry['version'] != 1:
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


def check_packet_size(content):
    # Match the baseline writer's ASCII-escaped encoding and reader's 4 MiB limit.
    packet = {'content': content, 'sha256': digest(content)}
    if len((json.dumps(packet, indent=2, allow_nan=False) + '\n').encode()) > dq.PACKET_LIMIT:
        raise ValueError('Combined baseline review exceeds 4 MiB; no output created')


def review_note(content):
    entry = content.get('data_admission')
    if entry is None:
        return ''
    return ('\n## Data qualification (protocol design only)\n\n'
            'The accepted evidence and decision are embedded in bundle.json. Read their full '
            'content before independently approving this execution. No raw metadata is sent to the worker.\n\n'
            '```json\n' + json.dumps({'context': entry['context'],
                'qualification_sha256': entry['qualification']['packet']['sha256'],
                'decision_sha256': entry['qualification']['decision']['sha256']}, indent=2, ensure_ascii=False) + '\n```\n')
