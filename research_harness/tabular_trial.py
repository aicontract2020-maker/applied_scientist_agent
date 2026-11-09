"""Human-reviewed, one-attempt feature study. No automatic approval or retuning."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import sys
import time

from .core import digest, number, Workspace
from .memory import read_json
from .observations import summarize, passes_gates
from .portable import ROOT
from .state_lock import research_lock
from .tabular_audit import validated_baseline, _AUDIT_FILES
from .tabular_baseline import environment, source_hashes
from .tabular_data import write_json
from .tabular_features import review as review_features
from .tabular_screen import history_records
from . import data_admission as admission
from .tabular_baseline import FIXTURE

ADAPTER = 'abalone-candidate-v1'

RECIPE = {
    'kind':'tabular-feature-study','version':1,'minimum_effect':.05,'max_latency_ratio':1.1,
    'seeds':[11,22,33],'bootstrap':{'resamples':1000,'seed':20261105,'confidence':.95},
    'primary_metric':{'name':'MAE','direction':'lower','unit':'rings'},
    'controls':['Same frozen training rows and original ten columns; append one to three arithmetic interactions only',
                'Same qualified fixed HGB parameters for baseline and candidate; no model selection or tuning',
                'Validation predictions reproduce the historical HGB within 1e-8 before final scoring',
                'All three paired seeds must have prediction range <=1e-8; repeatability, not independent training evidence',
                'All frozen holdout rows once; no reuse after failure, success or interruption'],
    'timing':'Median of five whole-batch predictions per seed; candidate includes feature transform; report all times',
    'go':'Every seed gain >=0.05 AND mean gain >=0.05 AND paired-row bootstrap lower bound >0 AND latency ratio <=1.1',
    'stop':'Any valid below-threshold result closes this mechanism; no tuning or complexity rescue',
    'invalid':'Close and retain data reservation; no scientific conclusion and no automatic retry',
    'uncertainty':'Conditional on fixed training set; row independence unverified; three seeds check repeatability only',
    'limits':{'worker_seconds':240,'output_bytes':16777216,'fits':6,'attempts':1,'threads':1},
    'costs':'Report six fits, transformation, five timing passes, wall time, RSS and bytes; actual money unknown, not zero',
}
SCOPE = 'One frozen feature study, six fixed HGB fits and one final holdout evaluation; no retries or tuning'


def validate_proposal(proposal):
    fields={'id','hypothesis','mechanism','why_new','feature_rationale','evidence','limitations','candidate_source'}
    if not isinstance(proposal,dict) or set(proposal)!=fields: raise ValueError('Invalid proposal fields')
    if not isinstance(proposal['id'],str) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}',proposal['id']):
        raise ValueError('Invalid proposal ID')
    for key in fields-{'evidence','limitations'}:
        if not isinstance(proposal[key],str) or not proposal[key].strip() or len(proposal[key])>8192:
            raise ValueError('Invalid proposal text: '+key)
    if not isinstance(proposal['limitations'],list) or not proposal['limitations'] or any(not isinstance(x,str) or not x.strip() for x in proposal['limitations']):
        raise ValueError('Explicit limitations required')
    from .primary_literature import canonical_paper_url
    evidence=proposal['evidence']
    if not isinstance(evidence,list) or not 2<=len(evidence)<=3: raise ValueError('Two or three primary papers required')
    urls=[]
    for item in evidence:
        if not isinstance(item,dict) or set(item)!={'url','claim'} or not isinstance(item['claim'],str) or not item['claim'].strip():
            raise ValueError('Evidence requires URL and attributable claim')
        urls.append(canonical_paper_url(item['url']))
    identities={re.sub(r'v\d+$','',url) for url in urls}
    if len(identities)!=len(urls): raise ValueError('Distinct primary papers required')
    return review_features(proposal['candidate_source'])


def scope_for(packet):
    return digest({'task':'tabular-regression','source':packet['content']['source'],'files':packet['content']['files']})


def prepare(baseline, proposal_path, output, literature, root=ROOT, *, data_review=None, intended_use=None):
    """Freeze a concrete review. Only syntax/synthetic probes; no real feature evaluation."""
    packet,parts,result,_=validated_baseline(baseline)
    if result['status']!='CONTINUE' or result['selected_baseline']!='hgb': raise ValueError('Qualified HGB required')
    snapshot=admission.trial_snapshot(packet,ADAPTER,FIXTURE,data_review,intended_use)
    proposal=read_json(proposal_path); gate=validate_proposal(proposal)
    from .tabular_memory import assert_available
    assert_available(packet,parts,root,candidate=proposal['candidate_source'])
    papers=read_json(literature)
    if not isinstance(papers,list) or {p['url'] for p in papers}!={e['url'] for e in proposal['evidence']}:
        raise ValueError('Retrieved primary papers must match all proposal references')
    for paper in papers:
        if not paper.get('title') or not paper.get('full_text') or not re.fullmatch('[0-9a-f]{64}',paper.get('pdf_sha256','')):
            raise ValueError('Each reference requires independently retrieved primary full text')
    scope=scope_for(packet)
    prior=[r for r in history_records() if r['scope']==scope]
    content={'recipe':RECIPE,'proposal':proposal,'feature_review':gate,'literature':papers,
             'baseline_sha256':packet['sha256'],'scope':scope,'counts':packet['content']['counts'],
             'prior_screens':prior,'sources':source_hashes(),'status':'AWAITING_RESEARCH_REVIEW'}
    if snapshot is not None:
        content['data_admission']=admission.bind_trial(snapshot,ADAPTER,packet,content,intended_use)
    admission.check_packet_size(content)
    folder=Path(output).absolute()
    folder.mkdir(parents=True,mode=0o700,exist_ok=False)
    for name in _AUDIT_FILES:
        target=folder/'baseline'/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(Path(baseline)/name,target)
    if validated_baseline(folder/'baseline')[0]!=packet: raise ValueError('Baseline changed during copy')
    envelope={'content':content,'sha256':digest(content)}
    write_json(folder/'trial.json',envelope)
    (folder/'candidate.py').write_text(proposal['candidate_source'])
    (folder/'REVIEW.md').write_text('# 回归候选研究审核\n\n状态：AWAITING_RESEARCH_REVIEW；未执行真实候选训练或留出评分。\n\n'
        +f'审核摘要：`{envelope["sha256"]}`\n\n'
        +f'假设：{proposal["hypothesis"]}\n\n机制：{proposal["mechanism"]}\n\n区别：{proposal["why_new"]}\n\n'
        +'候选仅追加固定跨列算术特征；源码被解析解释，不作为 Python 导入。原十列保持不变。\n\n'
        +f'分区：{json.dumps(content["counts"])}。固定 HGB 基线/候选各训练三个 seeds，共六次拟合；这是一项新研究，不重跑基线资格选择。\n\n'
        +'每个 seed 的 MAE 改善均至少 0.05 ring，配对行 bootstrap 95% 下界大于零，含特征构造的预测时延比不超过 1.1，才 CONTINUE。\n\n'
        +'任何有效失败 STOP；无效测量也保留整组留出预留，不自动重试。240 秒 CPU worker，输出监测 16 MiB；无硬内存保证，费用未知。\n\n'
        +'本地审批记录不是身份认证；单机锁不提供跨服务器协调。独立性、基线充分性和文献解释仍须人工判断。\n\n'
        +'候选、文献全文、历史基线摘要和当前执行源码全部冻结。请审核是否批准这一个具体候选消耗全部最终留出；未批准不能执行。\n\n'
        +'```python\n'+proposal['candidate_source']+'\n```\n\n'
        +'风险：\n'+''.join('- '+x+'\n' for x in proposal['limitations']))
    with (folder/'REVIEW.md').open('a') as handle: handle.write(admission.review_note(content,'trial.json'))
    return {'status':'AWAITING_RESEARCH_REVIEW','sha256':envelope['sha256'],'review':str(folder/'REVIEW.md')}


def load_trial(folder, current=True):
    folder=Path(folder)
    if folder.is_symlink() or not folder.is_dir(): raise ValueError('Regular trial folder required')
    if current and ((folder/'EVIDENCE_ONLY.json').exists() or (folder/'EVIDENCE_ONLY.json').is_symlink()):
        raise ValueError('Imported evidence is review-only, never an executable approval')
    envelope=read_json(folder/'trial.json'); c=envelope['content']
    fields={'recipe','proposal','feature_review','literature','baseline_sha256','scope','counts','prior_screens','sources','status'}
    if not isinstance(c,dict) or set(c) not in (fields,fields|{'data_admission'}): raise ValueError('Invalid trial fields')
    if set(envelope)!={'content','sha256'} or digest(c)!=envelope['sha256'] or c['recipe']!=RECIPE or c['status']!='AWAITING_RESEARCH_REVIEW':
        raise ValueError('Changed trial protocol')
    if current and c['sources']!=source_hashes(): raise ValueError('Trial source changed; approval cannot cover changed code')
    if validate_proposal(c['proposal'])!=c['feature_review']: raise ValueError('Feature gate differs')
    candidate=folder/'candidate.py'
    if candidate.is_symlink() or candidate.read_text()!=c['proposal']['candidate_source']: raise ValueError('Candidate changed')
    packet,parts,result,raw=validated_baseline(folder/'baseline')
    admission.verify_trial(c,packet,ADAPTER,required=current and packet['content']['source']!=FIXTURE)
    if packet['sha256']!=c['baseline_sha256'] or scope_for(packet)!=c['scope'] or packet['content']['counts']!=c['counts']:
        raise ValueError('Trial baseline binding differs')
    return envelope,parts,raw


def approve_trial(folder, sha256, reviewer, root=ROOT):
    with research_lock(root):
        envelope,parts,_=load_trial(folder)
        _available(folder,envelope,parts,root)
        if envelope['sha256']!=sha256 or not isinstance(reviewer,str) or not reviewer.strip(): raise ValueError('Exact hash and reviewer required')
        write_json(Path(folder)/'trial-approval.json',{'sha256':sha256,'reviewer':reviewer,'scope':SCOPE})
    return {'status':'APPROVED','sha256':sha256,'scope':SCOPE}


def evaluate_trial(raw, parts, qualified):
    """Independent controller: validate all predictions and reproduction BEFORE scoring."""
    expected={(kind,seed) for kind in ('baseline','candidate') for seed in RECIPE['seeds']}
    values={}; ids=[r['id'] for r in parts['holdout.json']]
    references={r['seed']:{p['id']:p['prediction'] for p in r['predictions']} for r in qualified['results'] if r['model']=='hgb'}
    for result in raw['results']:
        key=(result['kind'],result['seed'])
        if type(result['seed']) is not int or key not in expected or key in values: raise ValueError('Unexpected model/seed')
        records=result['predictions']
        if [r['id'] for r in records]!=ids: raise ValueError('Holdout identities changed')
        pred=[number(r['prediction'],'prediction') for r in records]
        times=result['timing_seconds']
        if len(times)!=5: raise ValueError('Missing frozen timing repetitions')
        for value in times: number(value,'batch time',1e-12)
        if result['batch_seconds']!=statistics.median(times): raise ValueError('Timing aggregate changed')
        number(result['fit_seconds'],'fit time',0)
        if key[0]=='baseline':
            val=result['validation_predictions']
            target=[references[key[1]][r['id']] for r in parts['validation.json']]
            if len(val)!=len(target) or any(abs(number(a,'validation prediction')-b)>1e-8 for a,b in zip(val,target)):
                raise ValueError('Historical baseline reproduction failed')
        elif result['validation_predictions'] is not None: raise ValueError('Candidate validation scoring is outside protocol')
        values[key]=(pred,result['batch_seconds'])
    if set(values)!=expected: raise ValueError('Incomplete six-fit results')
    for kind in ('baseline','candidate'):
        if any(max(values[kind,s][0][i] for s in RECIPE['seeds'])-min(values[kind,s][0][i] for s in RECIPE['seeds'])>1e-8 for i in range(len(ids))):
            raise ValueError('Frozen seed repeatability validity check failed')
    truth={r['id']:r['target'] for r in parts['holdout-targets.json']}
    rows=[]; gains=[]
    for seed in RECIPE['seeds']:
        gains.append(statistics.mean(abs(values['baseline',seed][0][i]-truth[id])-abs(values['candidate',seed][0][i]-truth[id]) for i,id in enumerate(ids)))
    for i,id in enumerate(ids):
        rows.append({'id':id,
            **{kind+'_score':statistics.mean(abs(values[kind,s][0][i]-truth[id]) for s in RECIPE['seeds']) for kind in ('baseline','candidate')},
            **{kind+'_latency_ms':1000*statistics.mean(values[kind,s][1] for s in RECIPE['seeds'])/len(ids) for kind in ('baseline','candidate')}})
    policy={**RECIPE,'observation_ids':ids,'task':{'id':'tabular-regression'}}
    summary=summarize(policy,rows); effect=statistics.mean(gains)
    passed=passes_gates(RECIPE,effect,summary) and min(gains)>=RECIPE['minimum_effect']
    return {'status':'CONTINUE' if passed else 'STOP','measurement_valid':True,'mean_effect':effect,
        'per_seed_effects':gains,'seed_effect_std':statistics.stdev(gains),'summary':summary,
        'observations':rows,'final_holdout_scored':True,'conclusion':RECIPE['go'] if passed else RECIPE['stop']}


def _available(folder,envelope,parts,root):
    folder=Path(folder)
    history=Path(root)/'.research-memory/tabular-trial'/envelope['content']['scope']
    if any(p.is_symlink() for p in (history,history.parent,history.parent.parent)): raise ValueError('Linked trial memory')
    run=folder/'trial-run'
    if run.exists() or run.is_symlink() or history.exists(): raise ValueError('Final holdout already reserved; no retry or alternate candidate')
    from .tabular_memory import assert_available
    base=read_json(folder/'baseline/bundle.json')
    if base['sha256']!=envelope['content']['baseline_sha256'] or digest(base['content'])!=base['sha256']:
        raise ValueError('Baseline changed during availability check')
    assert_available(base,parts,root,candidate=envelope['content']['proposal']['candidate_source'])
    return base


def _approved_trial(folder,root):
    envelope,parts,qualified=load_trial(folder)
    approval=read_json(Path(folder)/'trial-approval.json')
    if (set(approval)!={'sha256','reviewer','scope'} or approval['sha256']!=envelope['sha256'] or approval['scope']!=SCOPE
            or not isinstance(approval['reviewer'],str) or not approval['reviewer'].strip()):
        raise ValueError('Exact candidate-study approval required; baseline approval is insufficient')
    base=_available(folder,envelope,parts,root)
    return envelope,parts,qualified,base,approval


def preflight_trial(folder,root=ROOT):
    envelope,_,_,base,_=_approved_trial(folder,root)
    return {'status':'PRECHECK_PASSED','read_only':True,'sha256':envelope['sha256'],
            'data_admission':admission.verify_trial(envelope['content'],base,ADAPTER,required=base['content']['source']!=FIXTURE),
            'execution_authorized':False,'isolation_checked':False,'memory_checked':True}


def execute_trial(folder, root=ROOT):
    from .tabular_sandbox import isolation_probe, isolated_worker
    with research_lock(root):
        folder=Path(folder).absolute(); envelope,parts,qualified,baseline_packet,approval=_approved_trial(folder,root)
        run=folder/'trial-run'; history=Path(root)/'.research-memory/tabular-trial'/envelope['content']['scope']
        from .tabular_memory import data_keys,family_hash
        python=ROOT/'.venv-tabular/bin/python'
        env=environment(python); probe=isolation_probe(ROOT,python)
        if _approved_trial(folder,root)!=(envelope,parts,qualified,baseline_packet,approval):
            raise ValueError('Review or approval changed during preflight; no execution')
        history.mkdir(parents=True,exist_ok=False)
        write_json(history/'reservation.json',{'scope':envelope['content']['scope'],'trial_sha256':envelope['sha256'],
            'canonical_candidate_sha256':digest(envelope['content']['feature_review']['canonical']),'status':'RESERVED'})
        write_json(history/'exclusions.json',{'data_keys':data_keys(parts),
            'family_sha256':family_hash(envelope['content']['proposal']['candidate_source']),
            'route':{'source':envelope['content']['proposal']['candidate_source'],
                     'mechanism':envelope['content']['proposal']['mechanism']}})
        run.mkdir(mode=0o700,exist_ok=False); begin=time.monotonic()
        Workspace.append(run,{'event':'REGISTER','trial_sha256':envelope['sha256']})
        exposed=False
        try:
            write_json(run/'preflight.json',{'environment':env,'isolation':probe,'platform':sys.platform})
            trusted=run/'trusted'; inputs=run/'inputs'; output=run/'output'; trusted.mkdir(); inputs.mkdir()
            for name in ('tabular_features.py','tabular_trial_worker.py'):
                shutil.copyfile(ROOT/'research_harness'/name,trusted/name)
                if hashlib.sha256((trusted/name).read_bytes()).hexdigest()!=envelope['content']['sources']['research_harness/'+name]:
                    raise ValueError('Staged worker differs from reviewed source')
            write_json(inputs/'request.json',{'train':parts['train.json'],'validation':parts['validation.json'],
                       'holdout':parts['holdout.json'],'candidate':envelope['content']['proposal']['candidate_source']})
            if source_hashes()!=envelope['content']['sources']: raise ValueError('Source changed before worker start')
            Workspace.append(run,{'event':'EXPERIMENT_STARTED','trial_sha256':envelope['sha256']}); exposed=True
            process=isolated_worker(ROOT,python,folder,trusted,inputs,output,'tabular_trial_worker.py',
                                   ['--input',inputs/'request.json','--output',output/'predictions.json'],timeout=240)
            write_json(run/'process.json',process)
            if process['error'] or process['returncode']!=0: raise ValueError('Trial worker failed: '+str(process['error']))
            raw=read_json(output/'predictions.json'); result=evaluate_trial(raw,parts,qualified)
            result['peak_rss_bytes']=number(raw['peak_rss_native'],'peak RSS',0)*(1024 if sys.platform=='linux' else 1)
            result['fit_seconds']=sum(r['fit_seconds'] for r in raw['results'])
            result['transform_train_seconds']=number(raw['transform_train_seconds'],'feature construction time',0)
        except (ValueError,OSError,KeyError,TypeError,IndexError) as exc:
            result={'status':'STOP','measurement_valid':False,'reason':str(exc),'final_holdout_scored':False,'conclusion':RECIPE['invalid']}
        result.update(wall_seconds=time.monotonic()-begin,holdout_exposed_to_worker=exposed,
            actual_local_cost_usd=None,model_calls=0,retained_bytes_before_report=sum(p.stat().st_size for p in run.rglob('*') if p.is_file() and not p.is_symlink()))
        write_json(run/'result.json',result); Workspace.append(run,{'event':'DECISION','result':result})
        write_json(history/'decision.json',{'trial_sha256':envelope['sha256'],'result_sha256':digest(result),
                    'status':result['status'],'measurement_valid':result['measurement_valid']})
        (run/'REPORT.md').write_text('# Frozen feature study\n\n```json\n'+json.dumps(result,indent=2)+'\n```\n')
        return result


def audit_trial(folder):
    """Read-only consistency audit. Historical source is compared as bytes, never executed."""
    try:
        folder=Path(folder); envelope,parts,qualified=load_trial(folder,current=False)
        run=folder/'trial-run'
        for relative in ('','trusted','inputs','output'):
            path=run/relative
            if path.is_symlink() or not path.is_dir(): raise ValueError('Missing/linked trial artifact directory')
        approval=read_json(folder/'trial-approval.json')
        if (set(approval)!={'sha256','reviewer','scope'} or approval['sha256']!=envelope['sha256'] or approval['scope']!=SCOPE
                or not isinstance(approval['reviewer'],str) or not approval['reviewer'].strip()): raise ValueError('Trial approval differs')
        for name in ('tabular_features.py','tabular_trial_worker.py'):
            path=run/'trusted'/name
            if path.is_symlink() or not path.is_file() or path.stat().st_size>65536: raise ValueError('Invalid archived worker')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=envelope['content']['sources']['research_harness/'+name]:
                raise ValueError('Executed worker hash differs')
        expected={'train':parts['train.json'],'validation':parts['validation.json'],'holdout':parts['holdout.json'],
                  'candidate':envelope['content']['proposal']['candidate_source']}
        if read_json(run/'inputs/request.json')!=expected: raise ValueError('Worker inputs differ from reviewed inputs')
        preflight=read_json(run/'preflight.json')
        from .tabular_baseline import PACKAGES
        probes={'private_labels_denied','repo_denied','input_readonly','network_denied','output_writable'}
        if preflight['environment']!={'python':[3,12],'packages':PACKAGES} or set(preflight['isolation'])!=probes or any(v is not True for v in preflight['isolation'].values()):
            raise ValueError('Environment/isolation evidence differs')
        process=read_json(run/'process.json')
        if process['error'] is not None or process['returncode']!=0: raise ValueError('No successfully completed worker')
        raw=read_json(run/'output/predictions.json'); expected_result=evaluate_trial(raw,parts,qualified)
        result=read_json(run/'result.json')
        if any(result.get(k)!=v for k,v in expected_result.items()): raise ValueError('Stored trial decision differs from independent evaluation')
        extra={'peak_rss_bytes','fit_seconds','transform_train_seconds','wall_seconds','holdout_exposed_to_worker',
               'actual_local_cost_usd','model_calls','retained_bytes_before_report'}
        if set(result)!=set(expected_result)|extra: raise ValueError('Unexpected completed trial result fields')
        if preflight.get('platform') not in ('linux','darwin'): raise ValueError('Missing execution platform')
        if (result['holdout_exposed_to_worker'] is not True or result['actual_local_cost_usd'] is not None
                or type(result['model_calls']) is not int or result['model_calls']!=0
                or result['fit_seconds']!=sum(r['fit_seconds'] for r in raw['results'])
                or result['transform_train_seconds']!=raw['transform_train_seconds']
                or result['peak_rss_bytes']!=raw['peak_rss_native']*(1024 if preflight['platform']=='linux' else 1)):
            raise ValueError('Cost/exposure records differ from worker evidence')
        for key in ('peak_rss_bytes','fit_seconds','transform_train_seconds','wall_seconds','retained_bytes_before_report'):
            number(result[key],key,0)
        if result['wall_seconds']<number(process['wall_seconds'],'worker wall seconds',0):
            raise ValueError('Total wall time cannot exclude worker time')
        path=run/'ledger.jsonl'
        if path.is_symlink() or path.stat().st_size>4*1024*1024: raise ValueError('Invalid ledger')
        from .memory import _object
        def nonfinite(value): raise ValueError('Invalid ledger number')
        events=[json.loads(line,object_pairs_hook=_object,parse_constant=nonfinite) for line in path.read_text().splitlines()]
        if ([e['event'] for e in events]!=['REGISTER','EXPERIMENT_STARTED','DECISION']
                or any(e.get('trial_sha256')!=envelope['sha256'] for e in events[:2]) or events[-1].get('result')!=result):
            raise ValueError('Trial ledger does not bind reviewed execution and decision')
        return {'audit_ok':True,'read_only':True,'status':result['status'],'measurement_valid':True,
                'trial_sha256':envelope['sha256'],'final_holdout_scored':True,
                'limit':'Record consistency, not authenticated execution, independence or scientific novelty'}
    except (ValueError,OSError,KeyError,TypeError,AttributeError,IndexError) as exc:
        return {'audit_ok':False,'read_only':True,'error':str(exc)}
