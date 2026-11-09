"""Conservative offline exclusions for tabular trials; claims, not authentication.

Published, imported and local records are unioned. Reservations never release data.
Feature fingerprints detect renamed/reordered rows, not arbitrary dataset disguises.
"""
import ast
import json
import os
from pathlib import Path

from .core import digest
from .memory import read_json, _hash, _keys
from .portable import ROOT
from .state_lock import research_lock
from .tabular_data import write_json
from .tabular_features import parse

KIND='research-harness-tabular-memory'
FIELDS={'scope','trial_sha256','candidate_sha256','family_sha256','data_keys','route','state','result_sha256'}
STATES={'RESERVED','INVALID','STOP','CONTINUE'}


def data_keys(parts):
    return sorted({digest({'task':'tabular-regression','features':r['features']}) for r in parts['holdout.json']})


def family_hash(source):
    # Preserve column indices; erase scalar constants to reject numeric retuning.
    class Structure(ast.NodeTransformer):
        def visit_Subscript(self,node): return node
        def visit_Constant(self,node): return ast.copy_location(ast.Constant(value='FIXED_SCALAR'),node)
    tree=ast.List(elts=parse(source),ctx=ast.Load())
    return digest({'language':'row-arithmetic-v1','structure':ast.dump(Structure().visit(tree),include_attributes=False)})


def validate(record):
    _keys(record,FIELDS)
    for key in ('scope','trial_sha256','candidate_sha256','family_sha256','result_sha256'):
        _hash(record[key],nullable=key in ('family_sha256','result_sha256'))
    if record['state'] not in STATES: raise ValueError('Invalid tabular memory state')
    if (record['state']=='RESERVED') != (record['result_sha256'] is None):
        raise ValueError('Reservation/terminal result mismatch')
    values=record['data_keys']
    if values is not None:
        if not isinstance(values,list) or not 1<=len(values)<=10000: raise ValueError('Invalid row fingerprints')
        for value in values: _hash(value)
        if values!=sorted(set(values)): raise ValueError('Row fingerprints must be sorted and unique')
    route=record['route']
    if route is not None:
        _keys(route,('source','mechanism'))
        if not isinstance(route['mechanism'],str) or not 1<=len(route['mechanism'])<=8192: raise ValueError('Invalid mechanism text')
        expressions=parse(route['source'])
        canonical=ast.dump(ast.Expression(body=ast.List(elts=expressions,ctx=ast.Load())),include_attributes=False)
        if digest(canonical)!=record['candidate_sha256'] or family_hash(route['source'])!=record['family_sha256']:
            raise ValueError('Route text/code fingerprint mismatch')
    return record


def merge(*groups):
    records={}
    for group in groups:
        if not isinstance(group,list) or len(group)>1000: raise ValueError('Invalid tabular history size')
        for item in group:
            item=dict(validate(item)); old=records.get(item['scope'])
            if old:
                for key in ('trial_sha256','candidate_sha256','family_sha256','data_keys','route'):
                    if old[key] is not None and item[key] is not None and old[key]!=item[key]:
                        raise ValueError('Conflicting frozen tabular reservation: '+key)
                if old['state']!='RESERVED' and item['state']!='RESERVED' and (old['state'],old['result_sha256'])!=(item['state'],item['result_sha256']):
                    raise ValueError('Conflicting terminal tabular decisions')
                chosen=old if old['state']!='RESERVED' else item
                item={**chosen,**{k:old[k] if old[k] is not None else item[k] for k in ('family_sha256','data_keys','route')}}
            records[item['scope']]=item
    if len(records)>1000: raise ValueError('Too many tabular reservations')
    # Different independent experiments must not claim overlapping rows.
    claimed={}
    for record in records.values():
        for key in record['data_keys'] or []:
            if key in claimed and claimed[key]!=record['trial_sha256']:
                raise ValueError('Overlapping tabular trials; reconcile without reclaiming data')
            claimed[key]=record['trial_sha256']
    return [records[k] for k in sorted(records)]


def envelope(records):
    payload={'kind':KIND,'version':1,'records':merge(records)}
    return {'payload':payload,'sha256':digest(payload)}


def validate_packet(value):
    _keys(value,('payload','sha256'))
    p=value['payload']; _keys(p,('kind','version','records'))
    if p['kind']!=KIND or type(p['version']) is not int or p['version']!=1 or value['sha256']!=digest(p):
        raise ValueError('Invalid tabular memory envelope')
    if merge(p['records'])!=p['records']: raise ValueError('Noncanonical tabular memory')
    return value


def load_packet(path):
    return validate_packet(read_json(path))


def snapshot(root=ROOT):
    root=Path(root); groups=[]
    from .tabular_handoff import packets
    published=root/'tasks/tabular_regression/trial-history.json'
    if published.exists() or published.is_symlink(): groups.append(load_packet(published)['payload']['records'])
    memory=root/'.research-memory'
    for folder in (memory,memory/'tabular-handoff',memory/'tabular-trial'):
        if folder.is_symlink(): raise ValueError('Linked tabular memory directory')
    groups.extend(p['payload']['tabular_memory']['payload']['records'] for p in packets(root))
    for path in sorted((memory/'tabular-handoff').glob('*.json')):
        packet=load_packet(path)
        if path.stem!=packet['sha256']: raise ValueError('Imported packet filename/hash mismatch')
        groups.append(packet['payload']['records'])
    legacy=[]
    for folder in sorted((memory/'tabular-trial').glob('*')):
        if folder.is_symlink() or not folder.is_dir(): raise ValueError('Invalid local trial reservation directory')
        _hash(folder.name)
        reservation=read_json(folder/'reservation.json')
        _keys(reservation,('scope','trial_sha256','canonical_candidate_sha256','status'))
        if reservation['scope']!=folder.name or reservation['status']!='RESERVED': raise ValueError('Local reservation mismatch')
        record={'scope':folder.name,'trial_sha256':reservation['trial_sha256'],
                'candidate_sha256':reservation['canonical_candidate_sha256'],'family_sha256':None,
                'data_keys':None,'route':None,'state':'RESERVED','result_sha256':None}
        binding=folder/'exclusions.json'
        if binding.exists() or binding.is_symlink():
            detail=read_json(binding); _keys(detail,('family_sha256','data_keys','route'))
            record.update(detail)
        path=folder/'decision.json'
        if path.exists() or path.is_symlink():
            decision=read_json(path); _keys(decision,('trial_sha256','result_sha256','status','measurement_valid'))
            if (decision['trial_sha256']!=record['trial_sha256'] or decision['status'] not in ('STOP','CONTINUE')
                    or type(decision['measurement_valid']) is not bool): raise ValueError('Local decision mismatch')
            record.update(state=decision['status'] if decision['measurement_valid'] else 'INVALID',result_sha256=decision['result_sha256'])
        legacy.append(validate(record))
    return merge(*groups,legacy)


def assert_available(packet, parts, root=ROOT, candidate=None):
    from .tabular_trial import scope_for
    scope=scope_for(packet); keys=set(data_keys(parts)); family=family_hash(candidate) if candidate is not None else None
    for record in snapshot(root):
        if scope==record['scope'] or keys.intersection(record['data_keys'] or []):
            raise ValueError('Tabular holdout already reserved/consumed; no reuse under another ID, split or clone')
        if record['data_keys'] is None or (record['state']=='STOP' and record['family_sha256'] is None):
            raise ValueError('Incomplete legacy exclusions; reconcile/enrich evidence before starting new tabular research')
        if family is not None and record['state']=='STOP' and family==record['family_sha256']:
            raise ValueError('Stopped tabular feature family; changing constants or data cannot reopen it')


def record_from_trial(folder):
    from .tabular_trial import audit_trial,load_trial
    audit=audit_trial(folder)
    if not audit['audit_ok']: raise ValueError('Completed trial audit failed: '+audit['error'])
    packet,parts,_=load_trial(folder,current=False); c=packet['content']
    result=read_json(Path(folder)/'trial-run/result.json')
    return validate({'scope':c['scope'],'trial_sha256':packet['sha256'],
        'candidate_sha256':digest(c['feature_review']['canonical']),
        'family_sha256':family_hash(c['proposal']['candidate_source']),'data_keys':data_keys(parts),
        'route':{'source':c['proposal']['candidate_source'],'mechanism':c['proposal']['mechanism']},
        'state':result['status'],'result_sha256':digest(result)})


def import_memory(path, root=ROOT):
    packet=load_packet(path)
    with research_lock(root):
        merged=merge(snapshot(root),packet['payload']['records'])
        folder=Path(root)/'.research-memory/tabular-handoff'; folder.mkdir(parents=True,exist_ok=True)
        target=folder/(packet['sha256']+'.json')
        if target.exists():
            if load_packet(target)!=packet: raise ValueError('Stored memory packet changed')
            state='ALREADY_IMPORTED'
        else:
            write_json(target,packet); state='IMPORTED'
    return {'status':state,'records':len(merged),'sha256':packet['sha256'],'authenticity':'UNVERIFIED'}


def export_memory(output, root=ROOT):
    with research_lock(root):
        packet=envelope(snapshot(root))
        descriptor=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w') as handle: json.dump(packet,handle,indent=2,allow_nan=False); handle.write('\n')
    return {'status':'EXPORTED','sha256':packet['sha256'],'records':len(packet['payload']['records']),
            'note':'Exclusion claims plus mechanism/source text; review intellectual property before sharing. Hashes can reveal known-data membership. No labels, raw rows or approvals.'}


def retain_trial(folder, root=ROOT):
    packet=envelope([record_from_trial(folder)])
    with research_lock(root):
        merge(snapshot(root),packet['payload']['records'])
        target=Path(root)/'.research-memory/tabular-handoff'; target.mkdir(parents=True,exist_ok=True)
        path=target/(packet['sha256']+'.json')
        if path.exists():
            if load_packet(path)!=packet: raise ValueError('Retained packet changed')
            status='ALREADY_RETAINED'
        else: write_json(path,packet); status='RETAINED'
    return {'status':status,'sha256':packet['sha256']}
