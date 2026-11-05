"""Portable, allowlisted run evidence. Integrity checks are not authenticity.

Source is carried as UTF-8 text and never executed. No archive paths are extracted.
"""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from .core import digest
from .memory import _object
from .study_inspection import audit_run

KIND = 'research-harness-study-evidence'
FILE_LIMIT = 4*1024*1024
TOTAL_LIMIT = 8*1024*1024
PACKET_LIMIT = 16*1024*1024
FILES = frozenset(('result.json', 'session.json', 'ledger.jsonl', 'agent-REPORT.md',
    'search-records.json', 'registered.json', 'candidate.py', 'agent-candidate.py',
    'agent-research.json', 'intervention-review.json', 'observations.json',
    'workflow.json', 'REPORT.md'))


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Expected a regular, non-symlink evidence file: {path}')
    with path.open('rb') as handle:
        data = handle.read(limit+1)
    if len(data)>limit:
        raise ValueError(f'Evidence file exceeds {limit} byte limit: {path.name}')
    return data


def _validate(value):
    if not isinstance(value,dict) or set(value)!={'payload','sha256'}:
        raise ValueError('Evidence envelope requires only payload and sha256')
    payload = value['payload']
    if not isinstance(payload,dict) or set(payload)!={'kind','version','files'}:
        raise ValueError('Evidence payload contains missing or unknown fields')
    if payload['kind']!=KIND or type(payload['version']) is not int or payload['version']!=1:
        raise ValueError('Unsupported evidence kind/version')
    files = payload['files']
    if not isinstance(files,dict) or not files or not set(files)<=FILES:
        raise ValueError('Only allowlisted flat audit filenames can be transferred')
    total = 0
    for name, item in files.items():
        if not isinstance(item,dict) or set(item)!={'sha256','content'} or not isinstance(item['content'],str):
            raise ValueError('Each evidence file needs UTF-8 content and sha256')
        data = item['content'].encode('utf-8')
        total += len(data)
        if len(data)>FILE_LIMIT or total>TOTAL_LIMIT:
            raise ValueError('Evidence exceeds per-file or total content limit')
        if item['sha256']!=_sha(data):
            raise ValueError('Evidence file checksum mismatch: '+name)
    if value['sha256']!=digest(payload):
        raise ValueError('Evidence envelope checksum mismatch')
    return value


def load_bundle(path):
    data = _read(path,PACKET_LIMIT)
    def nonfinite(value):
        raise ValueError('Non-finite evidence JSON value')
    try:
        value = json.loads(data.decode('utf-8'),object_pairs_hook=_object,parse_constant=nonfinite)
        return _validate(value)
    except RecursionError as exc:
        raise ValueError('Evidence JSON nesting is too deep') from exc


def _materialize(bundle, destination):
    destination = Path(destination)
    for name, item in bundle['payload']['files'].items():
        # Names were validated against FILES, never taken as arbitrary paths.
        with (destination/name).open('xb') as handle:
            handle.write(item['content'].encode('utf-8'))


def _audit(bundle):
    with tempfile.TemporaryDirectory(prefix='rh-evidence-verify-') as folder:
        _materialize(bundle,folder)
        result = audit_run(folder)
    result['run'] = 'evidence:'+bundle['sha256']
    return result


def verify_bundle(path):
    bundle = load_bundle(path)
    audit = _audit(bundle)
    return {'sha256':bundle['sha256'],'checksum_ok':True,'audit_ok':audit['audit_ok'],
            'audit':audit,'authenticity':'UNVERIFIED',
            'note':'Checks artifact consistency, not sender identity, code execution, scientific novelty or image scores.'}


def _signature(path):
    try:
        stat = path.lstat()
        return (stat.st_ino,stat.st_size,stat.st_mtime_ns)
    except FileNotFoundError:
        return None


def export_bundle(run, output):
    run = Path(run)
    first = audit_run(run)
    if not first['audit_ok']:
        raise ValueError('Run did not pass read-only audit; no export: '+'; '.join(first['errors']))
    signatures = {name:_signature(run/name) for name in FILES}
    files = {}
    total = 0
    for name in sorted(FILES):
        if signatures[name] is None:
            continue
        data = _read(run/name,FILE_LIMIT)
        total += len(data)
        if total>TOTAL_LIMIT:
            raise ValueError('Evidence exceeds total content limit')
        files[name] = {'sha256':_sha(data),'content':data.decode('utf-8')}
    payload = {'kind':KIND,'version':1,'files':files}
    bundle = _validate({'payload':payload,'sha256':digest(payload)})
    audit = _audit(bundle)
    if not audit['audit_ok']:
        raise ValueError('Copied evidence is not consistent; no export: '+'; '.join(audit['errors']))
    if any(_signature(run/name)!=signature for name,signature in signatures.items()):
        raise ValueError('Evidence changed while copying; no export or automatic retry')
    encoded = (json.dumps(bundle,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    if len(encoded)>PACKET_LIMIT:
        raise ValueError('Encoded evidence exceeds packet size limit')
    output = Path(output)
    # Create exclusively with private default permissions; failed writes remove
    # only the file this call created. Existing user files are never replaced.
    descriptor = os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(descriptor,'wb') as handle:
            handle.write(encoded);handle.flush();os.fsync(handle.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {'status':'EXPORTED','file':str(output.resolve()),'sha256':bundle['sha256'],
            'file_count':len(files),'audit_ok':True,
            'sharing_note':'Contains source, hypothesis, reports and ledger text. Allowlisting is NOT redaction: review before sharing. Raw model events, auth files, papers and arrays are not collected.'}


def unpack_bundle(path, output):
    bundle = load_bundle(path)
    audit = _audit(bundle)
    if not audit['audit_ok']:
        raise ValueError('Evidence did not pass independent audit; not unpacked: '+'; '.join(audit['errors']))
    output = Path(output)
    # An exclusively created container prevents replacing any existing review.
    # Only run/ is published atomically; a kill may leave an incomplete container.
    output.mkdir(mode=0o700,exist_ok=False)
    try:
        pending = output/'.pending'
        pending.mkdir(mode=0o700)
        _materialize(bundle,pending)
        receipt = {'kind':KIND,'version':1,'packet_sha256':bundle['sha256'],
                   'files':{name:item['sha256'] for name,item in bundle['payload']['files'].items()},
                   'authenticity':'UNVERIFIED','purpose':'Review copy only; no research reservation, memory import or execution'}
        (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        pending.rename(output/'run')
    except BaseException:
        shutil.rmtree(output)
        raise
    return {'status':'UNPACKED','directory':str(output.resolve()),'run':str((output/'run').resolve()),
            'sha256':bundle['sha256'],'audit_ok':True,'authenticity':'UNVERIFIED',
            'note':'Review copy only. Use study audit --run on the returned directory; memory exchange is separate.'}
