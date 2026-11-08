"""One reviewed Airfoil baseline qualification, with condition-level scoring."""
import hashlib
import json
import platform
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import time

from .airfoil_data import SOURCE, FIXTURE, GROUP_RULE, parse, split_rows, counts
from .core import digest, number, Workspace
from .memory import read_json, _keys
from .portable import ROOT
from .state_lock import research_lock
from .tabular_baseline import PACKAGES, environment, source_hashes
from .tabular_data import FILES, write_json
from . import data_admission as admission

ADAPTER = 'airfoil-baseline-v1'

SCOPE = 'One Airfoil baseline qualification only; no candidate or final holdout scoring'
RECIPE = {
    'kind':'airfoil-condition-baseline','version':1,'seeds':[11,22,33],
    'hypothesis':'A fixed learned reference reduces condition-macro validation MAE by >=1 dB versus train-median at every seed and has a positive group-bootstrap lower bound.',
    'decision_purpose':'Qualify the lowest mean error reference from a bounded fixed model set; not global SOTA or scientific novelty.',
    'models':['median','ridge','svr','hgb','extra_trees'],
    'baseline_parameters':{
        'median':'DummyRegressor(strategy=median), fitted on training rows',
        'ridge':'StandardScaler then Ridge(alpha=1, solver=svd)',
        'svr':'StandardScaler then SVR(kernel=rbf, C=10, epsilon=.1, gamma=scale, cache_size=200); no target scaling',
        'hgb':'absolute_error, learning_rate=.1, max_iter=100, max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=0, max_bins=255, max_features=1.0, categorical_features=None, early_stopping=False',
        'extra_trees':'100 trees, squared_error, unlimited depth, min_samples_split=2, min_samples_leaf=1, max_features=1.0, bootstrap=False, n_jobs=1',
        'other_parameters':'Pinned scikit-learn 1.7.2 defaults; random_state=seed where supported'},
    'controls':['Pinned raw data and fixed target-blind condition split',
        'All models train on original row-weighted training set only; scaling fitted on training rows',
        'Validation labels stay in controller; no final holdout mounted',
        'Single-thread CPU, fixed versions, no tuning/early stopping, all 15 fits charged'],
    'group_rule':GROUP_RULE,
    'primary_metric':'Mean of per-condition mean absolute errors, in dB; every condition equal weight',
    'minimum_gain_db':1.0,
    'threshold_reason':'Proposed engineering qualification margin, not an established business or perceptual threshold',
    'selection':'Lowest mean condition-macro MAE across 3 seeds among ridge, svr, hgb, extra_trees; ties use that order; never choose a different model to rescue a failed selected model',
    'bootstrap':{'resamples':10000,'seed':20261106,'confidence_per_model':.99,'lower_quantile':.005,'upper_quantile':.995},
    'uncertainty':'Resample complete validation condition groups with replacement on seed-averaged paired losses. Four 99% marginal percentile intervals mitigate selection (nominal Bonferroni family coverage >=96%, approximate bootstrap only). Seeds measure training variation, not independent data. Unknown campaign dependence remains.',
    'validity':['Pinned source/data/environment; exact identities and finite complete outputs',
        'Actual OS isolation probe passes; every condition stays in one partition',
        'Median/Ridge/SVR/HGB cross-seed prediction range <=1e-8; Extra Trees variation is reported, not invalidated'],
    'max_deterministic_prediction_range':1e-8,
    'go':'Only draft a separate candidate protocol; no automatic candidate execution or holdout scoring',
    'stop':'Close qualification; no alternate model, changed split, tuning or automatic retry',
    'invalid':'Preserve failed measurement and reservation; no automatic retry or scientific conclusion',
    'limits':{'worker_seconds':240,'output_bytes':16777216,'threads':1,'attempts':1,'fits':15},
    'costs':{'model_calls':0,'paid_cloud_jobs':0,'actual_local_cost_usd':None,
        'unpriced':['installation/downloads','electricity/depreciation','retained storage','human review']},
    'python':'3.12','packages':PACKAGES,
}


def prepare(data, output, data_review=None, intended_use=None):
    snapshot = admission.accepted_snapshot(data_review, ADAPTER, SOURCE, intended_use)
    return prepare_rows(parse(data),output,SOURCE,raw=Path(data).read_bytes(),qualification=snapshot,intended_use=intended_use)


def prepare_rows(rows, output, source=FIXTURE, raw=None, *, qualification=None, intended_use=None):
    if source not in (SOURCE,FIXTURE): raise ValueError('Unsupported Airfoil source')
    if source==SOURCE and (raw is None or hashlib.sha256(raw).hexdigest()!=SOURCE['raw_sha256']):
        raise ValueError('Real review requires pinned raw bytes')
    if source == SOURCE and qualification is None: raise ValueError('Real data requires accepted data qualification')
    parts=split_rows(rows)
    c={'recipe':RECIPE,'source':source,'files':{n:digest(parts[n]) for n in FILES},
       'counts':counts(parts),'sources':source_hashes(),'status':'AWAITING_REVIEW'}
    if qualification is not None:
        c['data_admission'] = admission.bind(qualification, ADAPTER, source, intended_use, c['files'], RECIPE)
    admission.check_packet_size(c)
    folder=Path(output).absolute(); folder.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name in FILES: write_json(folder/name,parts[name])
    if raw is not None: (folder/'airfoil_self_noise.dat').write_bytes(raw)
    packet={'content':c,'sha256':digest(c)}; write_json(folder/'bundle.json',packet)
    (folder/'REVIEW.md').write_text('# Airfoil baseline qualification — AWAITING_REVIEW\n\n'
        f"Exact SHA-256: `{packet['sha256']}`\n\n"
        'No real model fit, prediction, validation or holdout score is authorized by preparation.\n\n'
        'Review docs/AIRFOIL_BASELINE_REVIEW.md and the complete frozen recipe below. '
        'Approval covers 15 fixed baseline fits on training data and condition-level validation only. '
        'Any failed threshold closes this qualification; no tuning or retry. Final holdout remains sealed.\n\n'
        '```json\n'+json.dumps({'source':source,'counts':c['counts'],'recipe':RECIPE},indent=2)+'\n```\n')
    with (folder/'REVIEW.md').open('a') as handle: handle.write(admission.review_note(c))
    return {'status':'AWAITING_REVIEW','review':str(folder/'REVIEW.md'),'sha256':packet['sha256'],'counts':c['counts']}


def load_review(folder, current=True):
    folder=Path(folder)
    if folder.is_symlink() or not folder.is_dir(): raise ValueError('Regular Airfoil review directory required')
    packet=read_json(folder/'bundle.json'); _keys(packet,('content','sha256')); c=packet['content']
    fields = {'recipe','source','files','counts','sources','status'}
    if not isinstance(c, dict) or set(c) not in (fields, fields | {'data_admission'}):
        raise ValueError('Invalid Airfoil review fields')
    if packet['sha256']!=digest(c) or c['recipe']!=RECIPE or c['status']!='AWAITING_REVIEW':
        raise ValueError('Changed Airfoil review/recipe')
    if c['source'] not in (SOURCE,FIXTURE): raise ValueError('Unsupported Airfoil source')
    admission.verify(c, ADAPTER, required=current and c['source'] == SOURCE)
    _keys(c['files'],FILES)
    expected=source_hashes()
    if (not isinstance(c['sources'],dict) or 'research_harness/airfoil_worker.py' not in c['sources']
            or any(not isinstance(k,str) or not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for k,v in c['sources'].items())):
        raise ValueError('Invalid source inventory')
    if current and c['sources']!=expected: raise ValueError('Reviewed source changed')
    parts={name:read_json(folder/name) for name in FILES}
    if any(digest(parts[n])!=c['files'][n] for n in FILES): raise ValueError('Reviewed data changed')
    rows=[]
    for r in parts['train.json']:
        _keys(r,('id','features','target','group')); rows.append({k:r[k] for k in ('id','features','target')})
    for key in ('validation','holdout'):
        features,targets=parts[key+'.json'],parts[key+'-targets.json']
        if len(features)!=len(targets): raise ValueError('Mismatched targets')
        for f,t in zip(features,targets):
            _keys(f,('id','features','group')); _keys(t,('id','target','group'))
            if f['id']!=t['id'] or f['group']!=t['group']: raise ValueError('Mismatched target identity/group')
            rows.append({'id':f['id'],'features':f['features'],'target':t['target']})
    if split_rows(rows)!=parts or counts(parts)!=c['counts']: raise ValueError('Condition split/counts changed')
    if c['source']==SOURCE and split_rows(parse(folder/'airfoil_self_noise.dat'))!=parts:
        raise ValueError('Parts differ from pinned raw data')
    return packet,parts


def scope(packet):
    # Protocol/ID/split changes cannot free this dataset qualification reservation.
    return digest({'kind':'airfoil-baseline','source':packet['content']['source']})


def reservation(root,packet):
    base=Path(root)/'.research-memory'; parent=base/'airfoil-baseline'; path=parent/scope(packet)
    if any(p.is_symlink() for p in (base,parent,path)): raise ValueError('Linked Airfoil memory')
    return path


def approve(folder, expected_hash, reviewer, root=ROOT):
    with research_lock(root):
        packet,_=load_review(folder)
        if packet['sha256']!=expected_hash or not isinstance(reviewer,str) or not reviewer.strip():
            raise ValueError('Exact hash and reviewer required')
        if (Path(folder)/'run').exists() or reservation(root,packet).exists(): raise ValueError('Attempt already reserved; no retry')
        write_json(Path(folder)/'approval.json',{'sha256':expected_hash,'reviewer':reviewer.strip(),'scope':SCOPE})
    return {'status':'APPROVED_BASELINE_ONLY','sha256':expected_hash}


def qualify(raw, targets):
    _keys(raw,('results','peak_rss_native')); number(raw['peak_rss_native'],'RSS',0)
    if not isinstance(targets,list) or not 1<=len(targets)<=10000: raise ValueError('Invalid targets')
    truth={}; groups={}
    for r in targets:
        _keys(r,('id','target','group'))
        if not isinstance(r['id'],str) or r['id'] in truth or not isinstance(r['group'],str): raise ValueError('Invalid target identity')
        truth[r['id']]=number(r['target'],'target'); groups.setdefault(r['group'],[]).append(r['id'])
    if not 10<=len(groups)<=100: raise ValueError('Need 10..100 validation conditions for bounded bootstrap')
    expected={(m,s) for m in RECIPE['models'] for s in RECIPE['seeds']}; predictions={}; costs=[]
    if not isinstance(raw['results'],list) or len(raw['results'])!=len(expected): raise ValueError('Expected all 15 fits')
    for item in raw['results']:
        _keys(item,('model','seed','fit_seconds','predict_seconds','predictions'))
        if not isinstance(item['model'],str) or type(item['seed']) is not int: raise ValueError('Invalid model/seed')
        key=item['model'],item['seed']
        if key not in expected or key in predictions: raise ValueError('Duplicate/unknown fit')
        costs.append({k:item[k] for k in ('model','seed','fit_seconds','predict_seconds')})
        for f in ('fit_seconds','predict_seconds'): number(item[f],f,0)
        if not isinstance(item['predictions'],list): raise ValueError('Invalid predictions')
        values={}
        for r in item['predictions']:
            _keys(r,('id','prediction'))
            if not isinstance(r['id'],str) or r['id'] not in truth or r['id'] in values: raise ValueError('Invalid prediction identity')
            values[r['id']]=number(r['prediction'],'prediction')
        if set(values)!=set(truth): raise ValueError('Missing prediction')
        predictions[key]=values
    spread={m:max(max(predictions[m,s][i] for s in RECIPE['seeds'])-min(predictions[m,s][i] for s in RECIPE['seeds']) for i in truth) for m in RECIPE['models']}
    if any(spread[m]>RECIPE['max_deterministic_prediction_range'] for m in RECIPE['models'] if m!='extra_trees'):
        raise ValueError('Deterministic repeatability check failed')
    group_ids=sorted(groups)
    losses={key:[statistics.mean(abs(p[i]-truth[i]) for i in groups[g]) for g in group_ids] for key,p in predictions.items()}
    scores={m:[statistics.mean(losses[m,s]) for s in RECIPE['seeds']] for m in RECIPE['models']}
    means={m:statistics.mean(v) for m,v in scores.items()}
    learned=RECIPE['models'][1:]; selected=min(learned,key=lambda m:means[m])
    gains={m:[scores['median'][i]-scores[m][i] for i in range(3)] for m in learned}
    paired={m:[statistics.mean(losses['median',s][g]-losses[m,s][g] for s in RECIPE['seeds']) for g in range(len(group_ids))] for m in learned}
    rng=random.Random(RECIPE['bootstrap']['seed']); samples={m:[] for m in learned}
    for _ in range(RECIPE['bootstrap']['resamples']):
        indices=[rng.randrange(len(group_ids)) for _ in group_ids]
        for m in learned: samples[m].append(sum(paired[m][i] for i in indices)/len(indices))
    intervals={}
    for m in learned:
        v=sorted(samples[m]); intervals[m]=[v[int((len(v)-1)*RECIPE['bootstrap'][q])] for q in ('lower_quantile','upper_quantile')]
    passed=min(gains[selected])>=RECIPE['minimum_gain_db'] and intervals[selected][0]>0
    return {'status':'CONTINUE' if passed else 'STOP','measurement_valid':True,'selected_baseline':selected,
        'mean_condition_mae_db':means,'per_seed_condition_mae_db':scores,
        'seed_mae_sample_std_db':{m:statistics.stdev(v) for m,v in scores.items()},
        'per_seed_gains_db':gains,'mean_gains_db':{m:statistics.mean(v) for m,v in gains.items()},
        'group_bootstrap_intervals_db':intervals,'prediction_range':spread,'validation_conditions':len(group_ids),
        'fit_costs':costs,'fits':len(costs),'total_fit_seconds':sum(c['fit_seconds'] for c in costs),
        'total_predict_seconds':sum(c['predict_seconds'] for c in costs),
        'final_holdout_scored':False,'conclusion':RECIPE['go'] if passed else RECIPE['stop']}


def worker_request(parts):
    return {'train':parts['train.json'],'validation':parts['validation.json']}


def _approved_review(folder, root):
    packet, parts = load_review(folder)
    approval = read_json(Path(folder)/'approval.json'); _keys(approval, ('sha256','reviewer','scope'))
    if approval['sha256'] != packet['sha256'] or approval['scope'] != SCOPE or not isinstance(approval['reviewer'], str) or not approval['reviewer'].strip():
        raise ValueError('Missing/stale Airfoil-only approval')
    run = Path(folder)/'run'; history = reservation(root, packet)
    if run.exists() or run.is_symlink() or history.exists(): raise ValueError('Airfoil qualification already reserved; no retry')
    return packet, parts, approval


def preflight(folder, root=ROOT):
    packet, _, _ = _approved_review(folder, root)
    return {'status': 'PRECHECK_PASSED', 'read_only': True, 'sha256': packet['sha256'],
            'data_admission': admission.verify(packet['content'], ADAPTER, required=packet['content']['source'] == SOURCE),
            'execution_authorized': False, 'isolation_checked': False,
            'note': 'Execution still rechecks exact approval, reservation and environment, then probes isolation.'}


def execute(folder, root=ROOT):
    from .tabular_sandbox import isolation_probe, isolated_worker
    with research_lock(root):
        folder=Path(folder).absolute(); packet,parts,approval=_approved_review(folder, root)
        run=folder/'run'; history=reservation(root,packet)
        python=ROOT/'.venv-tabular/bin/python'; env=environment(python); probe=isolation_probe(ROOT,python)
        if _approved_review(folder, root) != (packet, parts, approval):
            raise ValueError('Review or approval changed during preflight; no execution')
        history.mkdir(parents=True,exist_ok=False)
        write_json(history/'reservation.json',{'review_sha256':packet['sha256'],'status':'RESERVED'})
        run.mkdir(mode=0o700,exist_ok=False); begin=time.monotonic()
        Workspace.append(run,{'event':'REGISTER','review_sha256':packet['sha256']})
        write_json(run/'preflight.json',{'environment':env,'platform':platform.platform(),'isolation':probe})
        try:
            trusted,inputs,output=(run/n for n in ('trusted','inputs','output')); trusted.mkdir(); inputs.mkdir()
            shutil.copyfile(ROOT/'research_harness/airfoil_worker.py',trusted/'worker.py')
            write_json(inputs/'request.json',worker_request(parts))
            if packet['content']['sources']!=source_hashes(): raise ValueError('Source changed before worker')
            Workspace.append(run,{'event':'BASELINE_STARTED','review_sha256':packet['sha256']})
            process=isolated_worker(ROOT,python,folder,trusted,inputs,output,'worker.py',
                ['--input',inputs/'request.json','--output',output/'predictions.json'],timeout=RECIPE['limits']['worker_seconds'])
            write_json(run/'process.json',process)
            if process['error']: raise ValueError('Worker failed: '+process['error'])
            raw=read_json(output/'predictions.json'); result=qualify(raw,parts['validation-targets.json'])
            result['peak_rss_bytes']=raw['peak_rss_native']*(1024 if sys.platform=='linux' else 1)
        except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:
            result={'status':'STOP','measurement_valid':False,'reason':str(exc),'conclusion':RECIPE['invalid'],'final_holdout_scored':False}
        result.update(wall_seconds=time.monotonic()-begin,model_calls=0,actual_local_cost_usd=None,
            retained_bytes_before_report=sum(p.stat().st_size for p in run.rglob('*') if p.is_file() and not p.is_symlink()),scope=SCOPE)
        write_json(run/'result.json',result); Workspace.append(run,{'event':'DECISION','result':result})
        write_json(history/'decision.json',{'review_sha256':packet['sha256'],'result_sha256':digest(result),
            'status':result['status'],'measurement_valid':result['measurement_valid']})
        (run/'REPORT.md').write_text('# Airfoil baseline decision\n\n```json\n'+json.dumps(result,indent=2)+'\n```\n')
        return result


def audit(folder):
    """Read-only recomputation; never import archived worker code."""
    if sys.version_info[:2]!=(3,12): raise ValueError('Exact audit requires Python 3.12')
    folder=Path(folder); packet,parts=load_review(folder,current=False); run=folder/'run'
    if any((run/n).is_symlink() for n in ('.','inputs','trusted','output')): raise ValueError('Linked audit directory')
    approval=read_json(folder/'approval.json'); _keys(approval,('sha256','reviewer','scope'))
    if approval['sha256']!=packet['sha256'] or approval['scope']!=SCOPE or not isinstance(approval['reviewer'],str) or not approval['reviewer'].strip():
        raise ValueError('Changed approval')
    if read_json(run/'inputs/request.json')!=worker_request(parts): raise ValueError('Worker inputs changed')
    worker=run/'trusted/worker.py'
    if worker.is_symlink() or hashlib.sha256(worker.read_bytes()).hexdigest()!=packet['content']['sources']['research_harness/airfoil_worker.py']:
        raise ValueError('Archived worker changed')
    result=read_json(run/'result.json')
    if not result['measurement_valid']: raise ValueError('No completed valid measurement to audit')
    expected=qualify(read_json(run/'output/predictions.json'),parts['validation-targets.json'])
    if any(result.get(k)!=v for k,v in expected.items()): raise ValueError('Recomputed result differs')
    _keys(result,set(expected)|{'peak_rss_bytes','wall_seconds','model_calls','actual_local_cost_usd','retained_bytes_before_report','scope'})
    preflight=read_json(run/'preflight.json'); process=read_json(run/'process.json')
    if (preflight['environment']!={'python':[3,12],'packages':PACKAGES} or process['error'] is not None
            or preflight['isolation']!={'private_labels_denied':True,'repo_denied':True,'input_readonly':True,'network_denied':True,'output_writable':True}):
        raise ValueError('Changed process/environment/isolation evidence')
    native=read_json(run/'output/predictions.json')['peak_rss_native']
    if result['peak_rss_bytes']!=native*(1024 if preflight['platform'].startswith('Linux') else 1): raise ValueError('Changed RSS conversion')
    for name in ('wall_seconds','retained_bytes_before_report'): number(result[name],name,0)
    if result['scope']!=SCOPE or result['model_calls']!=0 or result['actual_local_cost_usd'] is not None:
        raise ValueError('Changed execution scope/costs')
    ledger=run/'ledger.jsonl'
    if ledger.is_symlink() or ledger.stat().st_size>4*1024*1024: raise ValueError('Invalid ledger')
    records=[json.loads(line) for line in ledger.read_text().splitlines()]
    if ([r.get('event') for r in records]!=['REGISTER','BASELINE_STARTED','DECISION']
            or any(r.get('review_sha256')!=packet['sha256'] for r in records[:2]) or records[-1].get('result')!=result):
        raise ValueError('Ledger changed')
    return {'audit_ok':True,'review_sha256':packet['sha256'],'status':result['status'],
        'final_holdout_scored':False,'authenticity':'UNVERIFIED','limit':'Internal record consistency only'}
