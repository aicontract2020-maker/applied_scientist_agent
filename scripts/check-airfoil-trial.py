"""Actual isolated A2 boundary check using synthetic data ONLY, no real A1/A2 files."""
import json
import math
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_harness import airfoil_baseline as ab, airfoil_trial as at
from examples.data_qualification.baseline import qualification as data_qualification,USE

root=Path(__file__).resolve().parents[1];(root/'runs').mkdir(exist_ok=True)
rows=[{'id':f'fixture-{i:03}-{j}','features':[500.+500*j,float(i),.1+i*.001,30.+i,.003],
       'target':100.+15*math.sin(i/9)+j*j} for i in range(150) for j in range(3)]
with tempfile.TemporaryDirectory(prefix='airfoil trial fixture ',dir=root/'runs') as tmp:
    folder=Path(tmp); base=folder/'baseline'; memory=folder/'checkout'; trial=folder/'trial'
    bp=ab.prepare_rows(rows,base);ab.approve(base,bp['sha256'],'SOFTWARE FIXTURE ONLY',root=memory)
    qualification=ab.execute(base,root=memory)
    if not qualification['measurement_valid'] or qualification['selected_baseline']!='extra_trees' or qualification['status']!='CONTINUE':
        raise RuntimeError('Synthetic reference construction failed: '+json.dumps(qualification))
    data_qualification(folder/'qualification',at.ADAPTER,ab.FIXTURE)
    prepared=at.prepare(base,root/'tasks/airfoil_noise/a2/proposal.json',trial,root=memory,
                        data_review=folder/'qualification/packet.json',intended_use=USE)
    assert not (trial/'trial-approval.json').exists() and not (trial/'trial-run').exists()
    at.approve(trial,prepared['sha256'],'SOFTWARE FIXTURE ONLY',root=memory)
    assert at.preflight(trial,root=memory)['data_admission']['execution_authorized'] is False
    result=at.execute(trial,root=memory)
    if not result['measurement_valid']:
        stderr=trial/'trial-run/output/stderr.log'
        raise RuntimeError(json.dumps(result)+'\n'+(stderr.read_text()[-3000:] if stderr.exists() else 'No stderr'))
    assert at.audit(trial)['audit_ok']
    saved=json.loads((trial/'trial-run/output/predictions.json').read_text())
    predictions={(r['kind'],r['seed']):r['predictions'] for r in saved['results']}
    assert any(predictions['baseline',s]!=predictions['candidate',s] for s in (11,22,33)), 'Synthetic model effect is a no-op'
    try: at.execute(trial,root=memory)
    except ValueError: pass
    else: raise AssertionError('Repeat execution allowed')
    try: at.prepare(base,root/'tasks/airfoil_noise/a2/proposal.json',folder/'copy',root=memory,
                    data_review=folder/'qualification/packet.json',intended_use=USE)
    except ValueError as e: assert 'reserved' in str(e)
    else: raise AssertionError('Copied holdout allowed')
    p=trial/'trial-run/output/predictions.json';raw=json.loads(p.read_text())
    raw['results'][0]['validation_predictions'][0]+=1;p.write_text(json.dumps(raw))
    try: at.audit(trial)
    except ValueError: pass
    else: raise AssertionError('Tampered reproduction accepted')
    print(json.dumps({'synthetic_only':True,'isolated_candidate_fits':6,'baseline_reproduction_passed':True,
        'strict_audit_passed':True,'tampering_rejected':True,'repeat_and_copy_rejected':True,
        'synthetic_model_predictions_changed':True,'candidate_data_admission_checked':True,
        'real_data_scored':False,'model_calls':0},indent=2))
