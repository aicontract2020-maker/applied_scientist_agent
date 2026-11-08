"""Offline metadata evidence and human review; never an execution authorization.

Integrity is not authenticity. Assertions about data require human verification.
No dataset parsing, URL fetching, model calls or executable adapters live here.
"""
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

from .core import digest

KIND = 'research-harness-data-qualification'
DECISION_KIND = 'research-harness-data-review-decision'
FILE_LIMIT = 256 * 1024
TOTAL_LIMIT = 1024 * 1024
PACKET_LIMIT = 4 * 1024 * 1024
CRITERIA = {
    'provenance': 'Identify source, dataset version and independence from existing sources.',
    'permission': 'Document permission for the exact intended use and publication scope.',
    'features': 'Resolve input definitions, units and label-independent transformations.',
    'target': 'Resolve target definition, units and any deterministic conversion.',
    'independence': 'Specify observation units, dependence groups and split rules.',
    'validity': 'Fix quality masks, exclusions and minimum eligible units before scores.',
    'holdout_history': 'Check prior exposure, reservations and consumed data across known history.',
    'access_boundary': 'Specify label access and an available isolated execution boundary.',
}


def _keys(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f'{name}: missing or unknown fields')


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 16000:
        raise ValueError(f'{name}: expected nonempty text of at most 16000 characters')


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', value):
        raise ValueError('Expected a safe lowercase identifier')


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
        raise ValueError('Expected SHA-256 in lowercase hexadecimal')


def _regular_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symbolic links are not accepted in input paths')
    return path


def _read(path, limit):
    path = _regular_path(path)
    # NONBLOCK avoids a FIFO substituted between validation and open hanging us.
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Expected a regular metadata file')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Metadata file exceeds size limit')
    return data


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError('Non-finite JSON value: ' + value)


def _json(path):
    try:
        return json.loads(_read(path, PACKET_LIMIT).decode('utf-8'),
                          object_pairs_hook=_object, parse_constant=_nonfinite)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Invalid UTF-8 or excessive JSON nesting') from exc


def _write(path, value):
    encoded = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    if len(encoded) > PACKET_LIMIT:
        raise ValueError('Encoded packet exceeds size limit')
    path = _regular_path(path)
    # Parents must already exist. Never overwrite an earlier packet or decision.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def template(output):
    draft = {
        'kind': KIND, 'version': 1, 'id': '', 'task': '',
        'dataset': {'id': '', 'version': '', 'source': ''}, 'intended_use': '',
        'criteria': {key: {'state': 'unresolved', 'rationale': question, 'evidence': []}
                     for key, question in CRITERIA.items()},
        'evidence': {},
    }
    _write(output, draft)
    return {'status': 'TEMPLATE_ONLY', 'execution_authorized': False}


def _validate(content, *, embedded):
    _keys(content, ('kind', 'version', 'id', 'task', 'dataset', 'intended_use', 'criteria', 'evidence'), 'qualification')
    if content['kind'] != KIND or type(content['version']) is not int or content['version'] != 1:
        raise ValueError('Unsupported data qualification kind/version')
    _identifier(content['id'])
    _text(content['task'], 'task')
    _text(content['intended_use'], 'intended_use')
    _keys(content['dataset'], ('id', 'version', 'source'), 'dataset')
    for name, value in content['dataset'].items():
        _text(value, 'dataset.' + name)
    evidence = content['evidence']
    if not isinstance(evidence, dict) or len(evidence) > 64:
        raise ValueError('Evidence must be an object with at most 64 records')
    total = 0
    for key, item in evidence.items():
        _identifier(key)
        _keys(item, ('source', 'locator', 'sha256', 'content' if embedded else 'path'), 'evidence')
        _text(item['source'], 'evidence source')
        _text(item['locator'], 'evidence locator')
        _sha(item['sha256'])
        if embedded:
            if not isinstance(item['content'], str) or not item['content'].strip():
                raise ValueError('Evidence content must be nonempty UTF-8 text')
            data = item['content'].encode('utf-8')
            total += len(data)
            if len(data) > FILE_LIMIT or total > TOTAL_LIMIT:
                raise ValueError('Evidence exceeds content size limit')
            if hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError('Evidence checksum mismatch: ' + key)
        else:
            value = item['path']
            if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value
                    or PurePosixPath(value).is_absolute()
                    or any(part in ('', '.', '..') for part in value.split('/'))):
                raise ValueError('Evidence path must be a relative path without traversal')
    _keys(content['criteria'], CRITERIA, 'criteria')
    used = set()
    for key, item in content['criteria'].items():
        _keys(item, ('state', 'rationale', 'evidence'), key)
        if item['state'] not in ('unresolved', 'supported', 'incompatible'):
            raise ValueError('Unknown criterion state: ' + key)
        _text(item['rationale'], key + ' rationale')
        refs = item['evidence']
        if (not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs)
                or len(set(refs)) != len(refs) or not set(refs) <= set(evidence)):
            raise ValueError('Missing, duplicate or unknown evidence references: ' + key)
        if item['state'] != 'unresolved' and not refs:
            raise ValueError('A resolved criterion requires evidence: ' + key)
        used.update(refs)
    if used != set(evidence):
        raise ValueError('Unreferenced evidence is not accepted')


def _status(content):
    criteria = content['criteria']
    if any(item['state'] == 'incompatible' for item in criteria.values()):
        return 'STOP_DATA_QUALIFICATION'
    if any(item['state'] == 'unresolved' for item in criteria.values()):
        return 'BLOCKED_DATA_QUALIFICATION'
    return 'AWAITING_DATA_REVIEW'


def _envelope(content):
    return {'content': content, 'sha256': digest(content)}


def _load_envelope(path):
    packet = _json(path)
    _keys(packet, ('content', 'sha256'), 'envelope')
    _sha(packet['sha256'])
    if packet['sha256'] != digest(packet['content']):
        raise ValueError('Frozen content checksum mismatch')
    return packet


def load_packet(path):
    packet = _load_envelope(path)
    _validate(packet['content'], embedded=True)
    return packet


def prepare(draft_path, output):
    content = _json(draft_path)
    _validate(content, embedded=False)
    root = _regular_path(draft_path).parent
    total = 0
    for item in content['evidence'].values():
        data = _read(root / item.pop('path'), FILE_LIMIT)
        total += len(data)
        if total > TOTAL_LIMIT:
            raise ValueError('Evidence exceeds total size limit')
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Source evidence differs from declared checksum')
        try:
            item['content'] = data.decode('utf-8')
        except UnicodeError as exc:
            raise ValueError('Evidence must be UTF-8 metadata text') from exc
    _validate(content, embedded=True)
    packet = _envelope(content)
    _write(output, packet)
    return _summary(packet)


def _summary(packet):
    content = packet['content']
    return {'id': content['id'], 'sha256': packet['sha256'], 'status': _status(content),
            'unresolved': [k for k, v in content['criteria'].items() if v['state'] == 'unresolved'],
            'incompatible': [k for k, v in content['criteria'].items() if v['state'] == 'incompatible'],
            'integrity_ok': True, 'authenticity': 'UNVERIFIED', 'execution_authorized': False}


def _validate_decision(receipt, packet):
    item = receipt['content']
    _keys(item, ('kind', 'version', 'packet_sha256', 'decision', 'reviewer', 'reason', 'scope'), 'decision')
    if item['kind'] != DECISION_KIND or type(item['version']) is not int or item['version'] != 1:
        raise ValueError('Unsupported decision kind/version')
    if item['packet_sha256'] != packet['sha256']:
        raise ValueError('Decision belongs to a different frozen packet')
    if item['decision'] not in ('accept', 'reject') or item['scope'] != 'protocol_design_only':
        raise ValueError('Unknown decision or execution scope')
    _text(item['reviewer'], 'reviewer')
    _text(item['reason'], 'reason')
    if item['decision'] == 'accept' and _status(packet['content']) != 'AWAITING_DATA_REVIEW':
        raise ValueError('Cannot accept unresolved or incompatible data qualification')


def _decision_path(packet_path):
    return Path(str(packet_path) + '.decision.json')


def inspect(packet_path):
    packet = load_packet(packet_path)
    result = _summary(packet)
    decision_path = _decision_path(packet_path)
    if decision_path.exists() or decision_path.is_symlink():
        receipt = _load_envelope(decision_path)
        _validate_decision(receipt, packet)
        result.update(decision_sha256=receipt['sha256'],
                      status=('QUALIFIED_FOR_PROTOCOL_DESIGN' if receipt['content']['decision'] == 'accept'
                              else 'STOP_DATA_QUALIFICATION'))
    return result


def decide(packet_path, expected_hash, reviewer, decision, reason):
    packet = load_packet(packet_path)
    if packet['sha256'] != expected_hash:
        raise ValueError('Review requires the exact frozen packet hash')
    receipt = _envelope({'kind': DECISION_KIND, 'version': 1, 'packet_sha256': expected_hash,
                         'decision': decision, 'reviewer': reviewer, 'reason': reason,
                         'scope': 'protocol_design_only'})
    _validate_decision(receipt, packet)
    _write(_decision_path(packet_path), receipt)
    return inspect(packet_path)
