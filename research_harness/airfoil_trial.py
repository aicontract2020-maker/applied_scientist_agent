"""Reviewed single-intervention Airfoil study; historical A1 is audited, never rerun."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

from . import airfoil_baseline as baseline
from .airfoil_candidate import SOURCE, MECHANISM, review as feature_review
from .core import digest, number, Workspace
from .memory import read_json, _keys, _hash
from .observations import summarize, passes_gates
from .portable import ROOT
from .state_lock import research_lock
from .tabular_baseline import source_hashes, environment
from .tabular_data import write_json
from . import data_admission as admission

ADAPTER='airfoil-candidate-v1'

BASE_FILES=('airfoil_self_noise.dat','approval.json','bundle.json','holdout-targets.json','holdout.json',
    'train.json','validation-targets.json','validation.json','run/inputs/request.json','run/ledger.jsonl',
    'run/output/predictions.json','run/preflight.json','run/process.json','run/result.json','run/trusted/worker.py')
SCOPE='One Strouhal feature trial; six Extra Trees fits and one final holdout evaluation; no tuning or retry'
RECIPE={
    'kind':'airfoil-strouhal-trial','version':1,'mechanism':MECHANISM,'seeds':[11,22,33],
    'minimum_effect':.2,'max_latency_ratio':1.1,
    'hypothesis':'Append f*delta_suction/U to the five original inputs of qualified Extra Trees; every paired seed gains >=0.2 dB condition-macro MAE on unused holdout, group-bootstrap lower bound >0, latency ratio <=1.1.',
    'controls':['Original A1 training rows only; no validation refit or new split',
        'Exact A1 Extra Trees parameters; 100 trees, seeds 11/22/33, single thread',
        'Only one fixed interaction appended; no scaling, offset, logs, clipping, new objective or tuning',
        'Baseline validation predictions must reproduce saved A1 Extra Trees per seed within 1e-8 before scoring',
        'All 21 real holdout condition groups scored once; labels in controller only'],
    'metric':'Mean per-condition MAE in dB, equal condition weight; report all seeds and variability',
    'bootstrap':{'resamples':10000,'seed':20261107,'confidence':.95},
    'uncertainty':'Bootstrap complete condition groups on seed-averaged paired losses; conditional on fixed training and three paired seeds, not independent campaigns or a proof of generalization',
    'timing':'Five whole-holdout-batch passes per fit, median; candidate includes augmentation and array conversion; seed 22 candidate-first, other seeds baseline-first',
    'minimum_effect_reason':'Prospective engineering adoption margin; not a calibrated business or acoustic perceptual threshold',
    'go':'All seed gains >=0.2 AND group bootstrap lower >0 AND total median batch latency ratio <=1.1; permit a separately reviewed external replication only',
    'stop':'Any valid failed gate closes this mechanism. Do not alter the feature, constants, seeds, model, thresholds or split to rescue it',
    'invalid':'Keep full holdout reservation after worker launch or failure; no automatic retry and no scientific conclusion',
    'limits':{'attempts':1,'fits':6,'threads':1,'worker_seconds':240,'output_bytes':16777216},
    'costs':'Record all six fits, train transform, 30 timing passes, wall time, RSS and retained bytes; actual money unknown; no model API calls',
}


def qualified(folder):
    baseline.audit(folder)
    packet,parts=baseline.load_review(folder,current=False)
    result=read_json(Path(folder)/'run/result.json')
    if result['status']!='CONTINUE' or result['selected_baseline']!='extra_trees':
        raise ValueError('Qualified A1 Extra Trees reference required')
    return packet,parts,read_json(Path(folder)/'run/output/predictions.json')


def scope(packet):
    return digest({'task':'airfoil-final-holdout','source':packet['content']['source']})


def history_path(root,packet):
    base=Path(root)/'.research-memory'; parent=base/'airfoil-trial'; path=parent/scope(packet)
    if any(p.is_symlink() for p in (base,parent,path)): raise ValueError('Linked Airfoil trial history')
    return path


def assert_available(root,packet):
    admission.assert_source_allowed(packet['content']['source'], root)
    if history_path(root,packet).exists(): raise ValueError('Airfoil holdout already reserved; no alternate ID/candidate/retry')
    path=Path(root)/'tasks/airfoil_noise/trial-history.json'
    if path.exists() or path.is_symlink():
        records=read_json(path)
        if not isinstance(records,list): raise ValueError('Invalid published history')
        for r in records:
            _keys(r,('scope','mechanism','review_sha256','status'))
            for k in ('scope','review_sha256'): _hash(r[k])
            if r['status'] not in ('RESERVED','STOP','CONTINUE','INVALID') or not isinstance(r['mechanism'],str):
                raise ValueError('Invalid history state')
            if r['scope']==scope(packet) or (r['mechanism']==MECHANISM and r['status']=='STOP'):
                raise ValueError('Published consumed holdout/stopped Strouhal route')


def validate_proposal(proposal):
    _keys(proposal,('id','hypothesis','mechanism','why_new','limitations','candidate_source','evidence'))
    if not isinstance(proposal['id'],str) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}',proposal['id']): raise ValueError('Invalid proposal ID')
    if proposal['mechanism']!=MECHANISM: raise ValueError('Unsupported intervention mechanism')
    for k in ('hypothesis','why_new'):
        if not isinstance(proposal[k],str) or not 1<=len(proposal[k])<=8192: raise ValueError('Missing research rationale')
    if not isinstance(proposal['limitations'],list) or not proposal['limitations'] or any(not isinstance(x,str) or not x for x in proposal['limitations']):
        raise ValueError('Explicit limitations required')
    if not isinstance(proposal['evidence'],list) or len(proposal['evidence'])!=2: raise ValueError('Two source records required')
    for e in proposal['evidence']:
        _keys(e,('url','title','locator','claim'))
        if any(not isinstance(v,str) or not v for v in e.values()): raise ValueError('Invalid evidence')
    if {e['url'] for e in proposal['evidence']}!={'https://ntrs.nasa.gov/citations/19890016302','https://scikit-learn.org/1.7/modules/ensemble.html'}:
        raise ValueError('Unsupported source set')
    return feature_review(proposal['candidate_source'])


def prepare(base,proposal_path,output,root=ROOT,*,data_review=None,intended_use=None):
    with research_lock(root):
        packet,parts,_=qualified(base); assert_available(root,packet)
        snapshot=admission.trial_snapshot(packet,ADAPTER,baseline.FIXTURE,data_review,intended_use,root=root)
        proposal=read_json(proposal_path); gate=validate_proposal(proposal)
        c={'recipe':RECIPE,'proposal':proposal,'feature_review':gate,'baseline_sha256':packet['sha256'],
           'scope':scope(packet),'counts':baseline.counts(parts),'sources':source_hashes(),'status':'AWAITING_RESEARCH_REVIEW'}
        if snapshot is not None:
            c['data_admission']=admission.bind_trial(snapshot,ADAPTER,packet,c,intended_use)
        admission.check_packet_size(c)
        folder=Path(output).absolute(); folder.mkdir(mode=0o700,parents=True,exist_ok=False)
        files=BASE_FILES if packet['content']['source']!=baseline.FIXTURE else tuple(n for n in BASE_FILES if n!='airfoil_self_noise.dat')
        for n in files:
            p=Path(base)/n
            if p.is_symlink(): raise ValueError('Linked baseline evidence')
            for a in p.parents:
                if a==Path(base): break
                if a.is_symlink(): raise ValueError('Linked baseline evidence directory')
            target=folder/'baseline'/n; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,target)
        copied,_,_=qualified(folder/'baseline')
        if copied!=packet: raise ValueError('Baseline changed during copy')
        envelope={'content':c,'sha256':digest(c)}; write_json(folder/'trial.json',envelope)
        (folder/'candidate.py').write_text(SOURCE)
        (folder/'REVIEW.md').write_text('# A2 Strouhal candidate — AWAITING_RESEARCH_REVIEW\n\n'
            f"Exact SHA-256: `{envelope['sha256']}`\n\nNo real candidate training, prediction or final scoring performed.\n\n"
            'Read docs/AIRFOIL_CANDIDATE_REVIEW.md. Approval would consume all 285 final rows in 21 conditions once. '
            'Six paired Extra Trees fits; gain >=0.2 dB at every seed; group 95% lower bound >0; latency <=1.1. '
            'Any valid failed gate STOP; invalid attempts retain reservation. No tuning or retry.\n\n'
            '```json\n'+json.dumps({'proposal':proposal,'recipe':RECIPE,'counts':c['counts']},indent=2)+'\n```\n')
        with (folder/'REVIEW.md').open('a') as handle: handle.write(admission.review_note(c,'trial.json'))
        return {'status':c['status'],'sha256':envelope['sha256'],'review':str(folder/'REVIEW.md')}


def load_trial(folder,current=True):
    folder=Path(folder)
    if folder.is_symlink() or not folder.is_dir() or (folder/'baseline').is_symlink(): raise ValueError('Regular trial directory required')
    p=read_json(folder/'trial.json'); _keys(p,('content','sha256')); c=p['content']
    fields={'recipe','proposal','feature_review','baseline_sha256','scope','counts','sources','status'}
    if not isinstance(c,dict) or set(c) not in (fields,fields|{'data_admission'}): raise ValueError('Invalid trial fields')
    if p['sha256']!=digest(c) or c['recipe']!=RECIPE or c['status']!='AWAITING_RESEARCH_REVIEW': raise ValueError('Changed trial protocol')
    if current and c['sources']!=source_hashes(): raise ValueError('Reviewed source changed')
    if c['feature_review']!=validate_proposal(c['proposal']): raise ValueError('Feature review differs')
    candidate=folder/'candidate.py'
    if candidate.is_symlink() or candidate.read_text()!=SOURCE: raise ValueError('Candidate changed')
    base,parts,raw=qualified(folder/'baseline')
    admission.verify_trial(c,base,ADAPTER,required=current and base['content']['source']!=baseline.FIXTURE)
    if c['baseline_sha256']!=base['sha256'] or c['scope']!=scope(base) or c['counts']!=baseline.counts(parts): raise ValueError('Baseline binding differs')
    return p,base,parts,raw


def approve(folder,sha256,reviewer,root=ROOT):
    with research_lock(root):
        p,base,_,_=load_trial(folder); assert_available(root,base)
        if p['sha256']!=sha256 or not isinstance(reviewer,str) or not reviewer.strip(): raise ValueError('Exact hash and reviewer required')
        if (Path(folder)/'trial-run').exists(): raise ValueError('Attempt exists')
        write_json(Path(folder)/'trial-approval.json',{'sha256':sha256,'reviewer':reviewer.strip(),'scope':SCOPE})
    return {'status':'APPROVED_ONCE','sha256':sha256}


def evaluate(raw,parts,reference):
    _keys(raw,('results','transform_train_seconds','peak_rss_native'))
    number(raw['transform_train_seconds'],'transform cost',0); number(raw['peak_rss_native'],'RSS',0)
    ids=[r['id'] for r in parts['holdout.json']]; valids=[r['id'] for r in parts['validation.json']]
    refs={r['seed']:{p['id']:p['prediction'] for p in r['predictions']} for r in reference['results'] if r['model']=='extra_trees'}
    expected={(k,s) for k in ('baseline','candidate') for s in RECIPE['seeds']}; values={}; costs=[]
    if not isinstance(raw['results'],list) or len(raw['results'])!=6: raise ValueError('Expected six fits')
    for r in raw['results']:
        _keys(r,('kind','seed','fit_seconds','timing_seconds','batch_seconds','validation_predictions','predictions'))
        if not isinstance(r['kind'],str) or type(r['seed']) is not int: raise ValueError('Invalid fit identity')
        key=r['kind'],r['seed']
        if key not in expected or key in values: raise ValueError('Unknown/duplicate fit')
        number(r['fit_seconds'],'fit cost',0)
        if not isinstance(r['timing_seconds'],list) or len(r['timing_seconds'])!=5: raise ValueError('Expected five timing passes')
        for t in r['timing_seconds']: number(t,'timing',1e-12)
        if r['batch_seconds']!=statistics.median(r['timing_seconds']): raise ValueError('Timing aggregate differs')
        if not isinstance(r['predictions'],list) or len(r['predictions'])!=len(ids): raise ValueError('Prediction count differs')
        for p in r['predictions']: _keys(p,('id','prediction')); number(p['prediction'],'prediction')
        if [p['id'] for p in r['predictions']]!=ids: raise ValueError('Holdout identity/order differs')
        if key[0]=='baseline':
            v=r['validation_predictions']
            if not isinstance(v,list) or len(v)!=len(valids) or any(abs(number(a,'validation prediction')-refs[key[1]][i])>1e-8 for a,i in zip(v,valids)):
                raise ValueError('Historical A1 Extra Trees reproduction failed')
        elif r['validation_predictions'] is not None: raise ValueError('Candidate validation predictions forbidden')
        values[key]=r; costs.append({k:r[k] for k in ('kind','seed','fit_seconds','timing_seconds','batch_seconds')})
    # Hidden labels are first used only after all six fits and reproduction validate.
    targets=parts['holdout-targets.json']
    if [r['id'] for r in targets]!=ids: raise ValueError('Targets differ')
    groups={}
    for i,(r,f) in enumerate(zip(targets,parts['holdout.json'])):
        if r['group']!=f['group']: raise ValueError('Target groups differ')
        number(r['target'],'target'); groups.setdefault(r['group'],[]).append(i)
    if not 10<=len(groups)<=100: raise ValueError('Invalid condition count')
    losses={key:{g:statistics.mean(abs(r['predictions'][i]['prediction']-targets[i]['target']) for i in indices) for g,indices in groups.items()} for key,r in values.items()}
    scores={k:[statistics.mean(losses[k,s].values()) for s in RECIPE['seeds']] for k in ('baseline','candidate')}
    gains=[a-b for a,b in zip(scores['baseline'],scores['candidate'])]
    bt=statistics.mean(values['baseline',s]['batch_seconds'] for s in RECIPE['seeds'])
    ct=statistics.mean(values['candidate',s]['batch_seconds'] for s in RECIPE['seeds'])
    rows=[{'id':g,'baseline_score':statistics.mean(losses['baseline',s][g] for s in RECIPE['seeds']),
           'candidate_score':statistics.mean(losses['candidate',s][g] for s in RECIPE['seeds']),
           'baseline_latency_ms':bt*1000,'candidate_latency_ms':ct*1000} for g in sorted(groups)]
    policy={'primary_metric':{'direction':'lower'},'bootstrap':RECIPE['bootstrap'],'observation_ids':sorted(groups)}
    summary=summarize(policy,rows)
    # Override SR helper's description; the resampling unit here is a whole condition.
    summary['bootstrap_scope']=RECIPE['uncertainty']
    passed=min(gains)>=RECIPE['minimum_effect'] and passes_gates(RECIPE,statistics.mean(gains),summary)
    return {'status':'CONTINUE' if passed else 'STOP','measurement_valid':True,'final_holdout_scored':True,
        'per_seed_condition_mae_db':scores,'per_seed_gains_db':gains,'mean_gain_db':statistics.mean(gains),
        'gain_sample_std_db':statistics.stdev(gains),'per_model_seed_std_db':{k:statistics.stdev(v) for k,v in scores.items()},
        'summary':summary,'conditions':len(groups),'rows':len(ids),'fit_costs':costs,'fits':6,
        'transform_train_seconds':raw['transform_train_seconds'],'total_fit_seconds':sum(c['fit_seconds'] for c in costs),
        'total_timing_seconds':sum(sum(c['timing_seconds']) for c in costs),
        'conclusion':RECIPE['go'] if passed else RECIPE['stop']}


def request(parts):
    return {k:parts[k+'.json'] for k in ('train','validation','holdout')}


def _approved_trial(folder,root):
    p,base,parts,reference=load_trial(folder)
    approval=read_json(Path(folder)/'trial-approval.json'); _keys(approval,('sha256','reviewer','scope'))
    if approval['sha256']!=p['sha256'] or approval['scope']!=SCOPE or not isinstance(approval['reviewer'],str) or not approval['reviewer'].strip():
        raise ValueError('Missing/stale trial approval')
    run=Path(folder)/'trial-run'
    if run.exists() or run.is_symlink(): raise ValueError('Trial already started')
    assert_available(root,base)
    return p,base,parts,reference,approval


def preflight(folder,root=ROOT):
    p,base,_,_,_=_approved_trial(folder,root)
    return {'status':'PRECHECK_PASSED','read_only':True,'sha256':p['sha256'],
            'data_admission':admission.verify_trial(p['content'],base,ADAPTER,required=base['content']['source']!=baseline.FIXTURE),
            'execution_authorized':False,'isolation_checked':False,'memory_checked':True}


def execute(folder,root=ROOT):
    from .tabular_sandbox import isolation_probe,isolated_worker
    with research_lock(root):
        folder=Path(folder).absolute(); p,base,parts,reference,approval=_approved_trial(folder,root)
        run=folder/'trial-run'
        python=ROOT/'.venv-tabular/bin/python'
        env=environment(python); probe=isolation_probe(ROOT,python)
        if _approved_trial(folder,root)!=(p,base,parts,reference,approval):
            raise ValueError('Review or approval changed during preflight; no execution')
        history=history_path(root,base); history.mkdir(parents=True,exist_ok=False)
        write_json(history/'reservation.json',{'review_sha256':p['sha256'],'scope':scope(base),'mechanism':MECHANISM,'status':'RESERVED'})
        run.mkdir(mode=0o700); start=time.monotonic(); exposed=False
        Workspace.append(run,{'event':'REGISTER','review_sha256':p['sha256']})
        write_json(run/'preflight.json',{'environment':env,'platform':sys.platform,'isolation':probe})
        try:
            trusted,inputs,output=(run/k for k in ('trusted','inputs','output')); trusted.mkdir();inputs.mkdir()
            for n in ('airfoil_candidate.py','airfoil_trial_worker.py'): shutil.copyfile(ROOT/'research_harness'/n,trusted/n)
            write_json(inputs/'request.json',request(parts))
            if p['content']['sources']!=source_hashes(): raise ValueError('Source changed before launch')
            for n in ('airfoil_candidate.py','airfoil_trial_worker.py'):
                if hashlib.sha256((trusted/n).read_bytes()).hexdigest()!=p['content']['sources']['research_harness/'+n]:
                    raise ValueError('Staged trusted source differs from approval')
            Workspace.append(run,{'event':'HOLDOUT_EXPOSED','review_sha256':p['sha256']}); exposed=True
            process=isolated_worker(ROOT,python,folder,trusted,inputs,output,'airfoil_trial_worker.py',
                ['--input',inputs/'request.json','--output',output/'predictions.json'],timeout=240)
            write_json(run/'process.json',process)
            if process['error']: raise ValueError('Worker failed: '+process['error'])
            raw=read_json(output/'predictions.json'); result=evaluate(raw,parts,reference)
            result['peak_rss_bytes']=raw['peak_rss_native']*(1024 if sys.platform=='linux' else 1)
        except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError) as exc:
            result={'status':'STOP','measurement_valid':False,'final_holdout_scored':False,'reason':str(exc),'conclusion':RECIPE['invalid']}
        result.update(holdout_exposed=exposed,wall_seconds=time.monotonic()-start,model_calls=0,actual_local_cost_usd=None,
            retained_bytes_before_report=sum(f.stat().st_size for f in run.rglob('*') if f.is_file() and not f.is_symlink()))
        write_json(run/'result.json',result); Workspace.append(run,{'event':'DECISION','result':result})
        write_json(history/'decision.json',{'scope':scope(base),'mechanism':MECHANISM,'review_sha256':p['sha256'],
            'status':result['status'] if result['measurement_valid'] else 'INVALID','result_sha256':digest(result)})
        (run/'REPORT.md').write_text('# A2 decision\n\n```json\n'+json.dumps(result,indent=2)+'\n```\n')
        return result


def audit(folder):
    if sys.version_info[:2]!=(3,12): raise ValueError('Exact audit requires Python 3.12')
    folder=Path(folder); p,_,parts,reference=load_trial(folder,current=False); run=folder/'trial-run'
    if any((run/k).is_symlink() for k in ('.','inputs','trusted','output')): raise ValueError('Linked audit directory')
    a=read_json(folder/'trial-approval.json'); _keys(a,('sha256','reviewer','scope'))
    if a['sha256']!=p['sha256'] or a['scope']!=SCOPE or not isinstance(a['reviewer'],str) or not a['reviewer'].strip(): raise ValueError('Approval differs')
    if read_json(run/'inputs/request.json')!=request(parts): raise ValueError('Worker input differs')
    for n in ('airfoil_candidate.py','airfoil_trial_worker.py'):
        f=run/'trusted'/n
        if f.is_symlink() or hashlib.sha256(f.read_bytes()).hexdigest()!=p['content']['sources']['research_harness/'+n]: raise ValueError('Trusted source differs')
    r=read_json(run/'result.json')
    if not r['measurement_valid']: raise ValueError('No valid completed measurement')
    raw=read_json(run/'output/predictions.json'); expected=evaluate(raw,parts,reference)
    _keys(r,set(expected)|{'peak_rss_bytes','holdout_exposed','wall_seconds','model_calls','actual_local_cost_usd','retained_bytes_before_report'})
    if any(r[k]!=v for k,v in expected.items()): raise ValueError('Recomputed result differs')
    pre=read_json(run/'preflight.json'); process=read_json(run/'process.json')
    if pre['environment']!={'python':[3,12],'packages':baseline.PACKAGES} or process['error'] is not None or process['returncode']!=0: raise ValueError('Environment/process differs')
    if pre['isolation']!={'private_labels_denied':True,'repo_denied':True,'input_readonly':True,'network_denied':True,'output_writable':True}: raise ValueError('Isolation record differs')
    if pre['platform'] not in ('linux','darwin') or r['peak_rss_bytes']!=raw['peak_rss_native']*(1024 if pre['platform']=='linux' else 1): raise ValueError('RSS differs')
    if r['holdout_exposed'] is not True or r['model_calls']!=0 or r['actual_local_cost_usd'] is not None: raise ValueError('Exposure/cost record differs')
    for k in ('wall_seconds','retained_bytes_before_report'): number(r[k],k,0)
    f=run/'ledger.jsonl'
    if f.is_symlink() or f.stat().st_size>4*1024*1024: raise ValueError('Invalid ledger')
    events=[json.loads(line) for line in f.read_text().splitlines()]
    if any(not isinstance(e.get('timestamp'),str) or not e['timestamp'] for e in events): raise ValueError('Missing event timestamp')
    content=[{k:v for k,v in e.items() if k!='timestamp'} for e in events]
    if content!=[{'event':'REGISTER','review_sha256':p['sha256']},{'event':'HOLDOUT_EXPOSED','review_sha256':p['sha256']},{'event':'DECISION','result':r}]: raise ValueError('Ledger differs')
    return {'audit_ok':True,'sha256':p['sha256'],'status':r['status'],'final_holdout_scored':True,'authenticity':'UNVERIFIED'}
