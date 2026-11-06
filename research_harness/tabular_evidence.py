"""Full, private tabular evidence packets. Never import carried Python sources.

Unlike metadata memory, these packets contain real data/labels, paper text and
approval text. Creating locally is not permission to publish them.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from .core import digest
from .memory import _object,_keys
from .tabular_audit import _AUDIT_FILES
from .tabular_trial import audit_trial

KIND='research-harness-tabular-evidence'
FILE_LIMIT=4*1024*1024
TOTAL_LIMIT=16*1024*1024
PACKET_LIMIT=32*1024*1024
FILES=frozenset(['baseline/'+name for name in _AUDIT_FILES]+[
    'trial.json','candidate.py','trial-approval.json','trial-run/result.json','trial-run/ledger.jsonl',
    'trial-run/preflight.json','trial-run/process.json','trial-run/inputs/request.json',
    'trial-run/output/predictions.json','trial-run/trusted/tabular_features.py','trial-run/trusted/tabular_trial_worker.py'])


def _runtime():
    if sys.version_info[:2]!=(3,12):
        raise ValueError('Exact tabular evidence audit requires pinned Python 3.12; use .venv-tabular/bin/python')


def _read(path,limit):
    path=Path(path)
    if path.is_symlink() or not path.is_file(): raise ValueError('Regular nonlinked evidence file required')
    with path.open('rb') as handle: data=handle.read(limit+1)
    if len(data)>limit: raise ValueError('Evidence file exceeds limit')
    return data


def _validate(value):
    _keys(value,('payload','sha256')); p=value['payload']; _keys(p,('kind','version','files'))
    if p['kind']!=KIND or type(p['version']) is not int or p['version']!=1: raise ValueError('Wrong evidence task/version')
    files=p['files']
    if not isinstance(files,dict) or set(files)!=FILES: raise ValueError('Evidence needs exactly the fixed allowlist; no arbitrary paths')
    total=0
    for item in files.values():
        _keys(item,('content','sha256'))
        if not isinstance(item['content'],str): raise ValueError('Evidence content must be UTF-8 text')
        data=item['content'].encode(); total+=len(data)
        if len(data)>FILE_LIMIT or total>TOTAL_LIMIT: raise ValueError('Evidence content exceeds limit')
        if hashlib.sha256(data).hexdigest()!=item['sha256']: raise ValueError('Changed evidence file hash')
    if value['sha256']!=digest(p): raise ValueError('Changed evidence envelope')
    return value


def load_packet(path):
    def nonfinite(value): raise ValueError('Nonfinite evidence JSON')
    try: return _validate(json.loads(_read(path,PACKET_LIMIT).decode(),object_pairs_hook=_object,parse_constant=nonfinite))
    except RecursionError as exc: raise ValueError('Evidence nesting too deep') from exc


def _materialize(packet,folder):
    folder=Path(folder)
    for name,item in packet['payload']['files'].items():
        target=folder/name; target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with target.open('xb') as handle: handle.write(item['content'].encode())
        target.chmod(0o600)
    (folder/'EVIDENCE_ONLY.json').write_text(json.dumps({'packet_sha256':packet['sha256'],'purpose':'Read-only review; never execute this imported approval'}))


def _audit(packet):
    _runtime()
    with tempfile.TemporaryDirectory(prefix='rh-tabular-evidence-') as tmp:
        _materialize(packet,tmp); result=audit_trial(tmp)
    return result


def verify(path):
    packet=load_packet(path); audit=_audit(packet)
    return {'sha256':packet['sha256'],'checksum_ok':True,'audit_ok':audit['audit_ok'],'audit':audit,
            'authenticity':'UNVERIFIED','execution_permitted':False,
            'note':'Record consistency only; no model/worker execution or memory import'}


def export(folder,output):
    _runtime(); folder=Path(folder)
    if folder.is_symlink() or not folder.is_dir(): raise ValueError('Regular trial directory required')
    audit=audit_trial(folder)
    if not audit['audit_ok']: raise ValueError('Trial audit failed; no export: '+audit['error'])
    files={}
    for name in sorted(FILES):
        path=folder/name
        for parent in path.parents:
            if parent==folder: break
            if parent.is_symlink(): raise ValueError('Linked evidence directory')
        data=_read(path,FILE_LIMIT)
        files[name]={'content':data.decode(),'sha256':hashlib.sha256(data).hexdigest()}
    p={'kind':KIND,'version':1,'files':files}; packet=_validate({'payload':p,'sha256':digest(p)})
    audit=_audit(packet)
    if not audit['audit_ok']: raise ValueError('Copied evidence audit failed: '+audit['error'])
    for name,item in files.items():
        if hashlib.sha256(_read(folder/name,FILE_LIMIT)).hexdigest()!=item['sha256']:
            raise ValueError('Original evidence changed during export; no retry')
    encoded=(json.dumps(packet,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
    if len(encoded)>PACKET_LIMIT: raise ValueError('Encoded packet exceeds limit')
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'wb') as handle: handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    except BaseException:
        Path(output).unlink(missing_ok=True); raise
    return {'status':'EXPORTED_PRIVATE','sha256':packet['sha256'],'audit_ok':True,'files':len(files),
            'bytes':len(encoded),'sharing_note':'Contains raw training data, held-out labels/predictions, paper text and approval text. Do not publish without separate data/rights review.'}


def unpack(path,output):
    packet=load_packet(path); audit=_audit(packet)
    if not audit['audit_ok']: raise ValueError('Evidence audit failed; no unpack: '+audit['error'])
    output=Path(output); output.mkdir(mode=0o700,exist_ok=False)
    try:
        pending=output/'.pending'; pending.mkdir(mode=0o700)
        _materialize(packet,pending); pending.rename(output/'review')
        (output/'receipt.json').write_text(json.dumps({'packet_sha256':packet['sha256'],
            'purpose':'Review-only; memory transfer is separate; no new approval or data availability'},indent=2)+'\n')
    except BaseException:
        shutil.rmtree(output); raise
    return {'status':'UNPACKED_REVIEW_ONLY','review':str((output/'review').resolve()),'audit_ok':True,
            'sha256':packet['sha256'],'execution_permitted':False}
