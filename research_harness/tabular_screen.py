"""Fixed proposal screen: no worker execution, final scoring or automatic retries."""
import json
from pathlib import Path
import re
import statistics
import time

from .core import digest, number, Workspace
from .memory import read_json
from .portable import ROOT
from .state_lock import research_lock
from .tabular_audit import validated_baseline
from .tabular_data import write_json

SCREEN_TEMPLATE = {'phase': 'proposal_screen_only',
 'hypothesis': 'One validation-fitted median residual offset improves untouched holdout MAE by >=0.05 rings '
               'over the qualified fixed HGB.',
 'mechanism': 'additive_validation_median_residual_v1',
 'calibration': 'median(y_validation - prediction_hgb_seed_11); use all original validation rows, no '
                'trimming, rescaling or tuning',
 'minimum_effect': 0.05,
 'metric': 'baseline_MAE - candidate_MAE, rings',
 'controls': ['Same HGB training and fixed baseline recipe',
              'All previously scored validation rows; not fresh confirmatory data',
              'No model retraining, alternative candidates or parameter rescue',
              'No final holdout inference or scoring during screening'],
 'prospective_bootstrap': {'resamples': 1000, 'seed': 20261105, 'confidence': 0.95},
 'prospective_max_latency_ratio': 1.1,
 'uncertainty_limit': 'Prospective interval is conditional on fixed training data and unverified row '
                      'independence. Screening uses a deterministic bound, not statistical confirmation.',
 'screening_rules': {'invalid_baseline': 'fail closed before calibration',
                     'delta_zero': 'REJECTED/NOT_RUN',
                     'abs_delta_below_minimum_effect': 'REJECTED/NOT_RUN; universal MAE gain upper bound is '
                                                       'abs(delta)',
                     'otherwise': 'AWAITING_RESEARCH_REVIEW; no scoring permission'},
 'cost_scope': {'new_training_runs': 0,
                'model_calls': 0,
                'holdout_scoring': 0,
                'actual_local_cost_usd': None},
 'sources': ['https://proceedings.mlr.press/v80/kuleshov18a.html',
             'https://proceedings.mlr.press/v162/marx22a.html']}


def load_protocol(path):
    packet = read_json(path)
    if not isinstance(packet, dict) or set(packet) != {'content','sha256'}:
        raise ValueError('Invalid screen protocol envelope')
    p = packet['content']
    if (not isinstance(p,dict) or not isinstance(p.get('id'),str)
            or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,79}',p['id'])
            or not isinstance(p.get('baseline_review_sha256'),str)
            or not re.fullmatch('[0-9a-f]{64}',p['baseline_review_sha256'])):
        raise ValueError('Invalid screen study or baseline identity')
    expected = dict(SCREEN_TEMPLATE,id=p['id'],baseline_review_sha256=p['baseline_review_sha256'])
    if digest(p) != digest(expected) or packet['sha256'] != digest(p):
        raise ValueError('Only the frozen median-residual screen is supported; no parameter rescue')
    return packet


def decision(delta, minimum_effect):
    """Necessary analytical condition only; never claim scientific acceptance."""
    number(delta,'delta'); number(minimum_effect,'minimum_effect',.05)
    if delta == 0:
        return 'REJECTED','No-op'
    if abs(delta) < minimum_effect:
        return 'REJECTED','Universal MAE gain upper bound is below the frozen minimum effect'
    return 'AWAITING_RESEARCH_REVIEW','Necessary bound passed; no evidence of actual improvement and no execution approval'


def _inputs(baseline, protocol):
    packet, parts, result, raw = validated_baseline(baseline)
    if packet['sha256'] != protocol['content']['baseline_review_sha256']:
        raise ValueError('Proposal references a different baseline review')
    if result['status'] != 'CONTINUE' or result['selected_baseline'] != 'hgb':
        raise ValueError('Screen requires a qualified HGB baseline')
    if any(value != 0 for value in result['prediction_range'].values()):
        raise ValueError('Screen requires identical baseline predictions across all frozen seeds')
    rows = next(x['predictions'] for x in raw['results'] if x['model']=='hgb' and x['seed']==11)
    scope = digest({'task':'tabular-regression','source':packet['content']['source'],'files':packet['content']['files']})
    return packet, parts['validation-targets.json'], rows, scope


def _calculate(protocol, packet, targets, rows):
    truth = {r['id']:r['target'] for r in targets}
    residuals = [number(truth[r['id']]-r['prediction'],'residual') for r in rows]
    delta = statistics.median(residuals)
    status, reason = decision(delta,protocol['content']['minimum_effect'])
    return {'status':status,'scientific_status':'NOT_RUN','delta':delta,
            'universal_mae_gain_upper_bound':abs(delta),'minimum_effect':protocol['content']['minimum_effect'],
            'reason':reason,'calibration_rows':len(rows),'baseline_review_sha256':packet['sha256'],
            'protocol_sha256':protocol['sha256'],
            'calibration_source_sha256':digest({'targets':targets,'predictions':rows}),
            'new_training_runs':0,'model_calls':0,'final_holdout_scored':False,'actual_local_cost_usd':None}


def _history_path(root, scope):
    folder = Path(root)/'.research-memory'/'tabular-screen'/scope
    for path in (Path(root)/'.research-memory',folder.parent,folder):
        if path.is_symlink(): raise ValueError('Screen history directory must not be a symlink')
    return folder/'median-residual-v1.json'


def history_records(root=ROOT):
    """Conservative published/local metadata; no raw data or candidate execution."""
    published = Path(root)/'tasks/tabular_regression/screen-history.json'
    records = read_json(published) if published.exists() or published.is_symlink() else []
    if not isinstance(records,list): raise ValueError('Invalid published screen history')
    folder = Path(root)/'.research-memory/tabular-screen'
    if folder.is_symlink() or folder.parent.is_symlink(): raise ValueError('Linked screen history')
    for path in sorted(folder.glob('*/median-residual-v1.json')):
        if path.parent.is_symlink(): raise ValueError('Linked screen history scope')
        item = read_json(path)
        if not isinstance(item,dict) or item.get('scope') != path.parent.name: raise ValueError('History scope/path mismatch')
        records.append(item)
    merged = {}
    for item in records:
        fields = {'kind','version','scope','mechanism','protocol_sha256','baseline_review_sha256','status','result_sha256'}
        if (not isinstance(item,dict) or set(item)!=fields or item['kind']!='tabular-screen-history'
                or type(item['version']) is not int or item['version']!=1
                or item['mechanism']!=SCREEN_TEMPLATE['mechanism']
                or item['status'] not in ('RESERVED','REJECTED','AWAITING_RESEARCH_REVIEW')):
            raise ValueError('Invalid screen history record')
        for key in ('scope','protocol_sha256','baseline_review_sha256','result_sha256'):
            if key=='result_sha256' and item['status']=='RESERVED' and item[key] is None: continue
            if not isinstance(item[key],str) or not re.fullmatch('[0-9a-f]{64}',item[key]): raise ValueError('Invalid history digest')
        previous = merged.get(item['scope'])
        if previous is not None and previous != item: raise ValueError('Conflicting published/local screen history')
        merged[item['scope']] = item
    return list(merged.values())


def _record(scope, protocol, result=None):
    return {'kind':'tabular-screen-history','version':1,'scope':scope,
            'mechanism':protocol['content']['mechanism'],'protocol_sha256':protocol['sha256'],
            'baseline_review_sha256':protocol['content']['baseline_review_sha256'],
            'status':result['status'] if result else 'RESERVED',
            'result_sha256':digest(result) if result else None}


def _finalize(path, record):
    pending = path.with_suffix('.pending')
    write_json(pending,record)
    pending.replace(path)


def screen(baseline, protocol_path, output, root=ROOT):
    """Fit one fixed calibration statistic on existing validation predictions only."""
    with research_lock(root):
        protocol = load_protocol(protocol_path)
        packet, targets, rows, scope = _inputs(baseline,protocol)
        output = Path(output)
        if output.exists() or output.is_symlink(): raise ValueError('Proposal output already exists')
        history = _history_path(root,scope)
        if any(item['scope']==scope for item in history_records(root)) or history.exists() or history.is_symlink():
            raise ValueError('This task/data mechanism is already screened or reserved; no retry under a new ID')
        history.parent.mkdir(parents=True,exist_ok=True)
        write_json(history,_record(scope,protocol))
        # A failure/kill retains the reservation. No automatic reclaim or alternate candidate.
        output.mkdir(parents=True,mode=0o700,exist_ok=False)
        write_json(output/'screen-protocol.json',protocol)
        Workspace.append(output,{'event':'SCREEN_REGISTERED','protocol_sha256':protocol['sha256'],
                                 'baseline_review_sha256':packet['sha256']})
        begin = time.monotonic()
        result = _calculate(protocol,packet,targets,rows)
        result['screen_wall_seconds'] = time.monotonic()-begin
        code = '# Fixed validation-median shift; no fitting or tuning here.\nOFFSET = '+repr(result['delta'])+'\ndef predict(values):\n    return [float(value) + OFFSET for value in values]\n'
        (output/'candidate.py').write_text(code)
        write_json(output/'screen-result.json',result)
        Workspace.append(output,{'event':'SCREEN_DECISION','result':result})
        _finalize(history,_record(scope,protocol,result))
        return result


def verify_screen(baseline, proposal):
    """Reanalyze saved calibration records, never rerun training or holdout scoring."""
    proposal = Path(proposal)
    if proposal.is_symlink() or not proposal.is_dir(): raise ValueError('Expected regular proposal directory')
    protocol = load_protocol(proposal/'screen-protocol.json')
    packet, targets, rows, scope = _inputs(baseline,protocol)
    result = read_json(proposal/'screen-result.json')
    expected = _calculate(protocol,packet,targets,rows)
    if not isinstance(result,dict) or set(result) != set(expected)|{'screen_wall_seconds'}:
        raise ValueError('Invalid screen result fields')
    number(result['screen_wall_seconds'],'screen_wall_seconds',0)
    if any(result[key] != value for key,value in expected.items()): raise ValueError('Screen result is inconsistent with bound calibration records')
    ledger = proposal/'ledger.jsonl'
    if ledger.is_symlink() or ledger.stat().st_size>1024*1024: raise ValueError('Invalid screen ledger')
    from .memory import _object
    def nonfinite(value): raise ValueError('Non-finite screen ledger')
    events = [json.loads(line,object_pairs_hook=_object,parse_constant=nonfinite) for line in ledger.read_text().splitlines()]
    if ([e['event'] for e in events] != ['SCREEN_REGISTERED','SCREEN_DECISION']
            or events[0].get('protocol_sha256') != protocol['sha256']
            or events[0].get('baseline_review_sha256') != packet['sha256'] or events[1].get('result') != result):
        raise ValueError('Screen ledger does not bind registration and result')
    # Candidate text is optional for coordinator-created historical screens.
    candidate = proposal/'candidate.py'
    if candidate.exists() or candidate.is_symlink():
        expected_code = '# Fixed validation-median shift; no fitting or tuning here.\nOFFSET = '+repr(result['delta'])+'\ndef predict(values):\n    return [float(value) + OFFSET for value in values]\n'
        if candidate.is_symlink() or candidate.stat().st_size>4096 or candidate.read_text()!=expected_code:
            raise ValueError('Candidate source differs from the screened fixed mechanism')
    return protocol,result,scope


def retain_screen(baseline, proposal, root=ROOT):
    """Conservatively retain an existing checked screen; original records stay untouched."""
    with research_lock(root):
        protocol,result,scope = verify_screen(baseline,proposal)
        path = _history_path(root,scope)
        record = _record(scope,protocol,result)
        if any(item['scope']==scope and item!=record for item in history_records(root)):
            raise ValueError('Conflicting published/local screen history; no overwrite')
        if path.is_symlink(): raise ValueError('Linked screen history')
        if path.exists():
            if read_json(path)!=record: raise ValueError('Conflicting screen history; no overwrite or reclaim')
            return {'status':'ALREADY_RETAINED','screen_status':result['status'],'scope':scope}
        path.parent.mkdir(parents=True,exist_ok=True)
        write_json(path,record)
        return {'status':'RETAINED','screen_status':result['status'],'scope':scope}
