"""Actual 15-fit isolated integration on synthetic data ONLY; no public data loaded."""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_harness import airfoil_baseline as ab

root=Path(__file__).resolve().parents[1]; (root/'runs').mkdir(exist_ok=True)
rows=[{'id':f'fixture-{i:03}-{j}','features':[float(500*(j+1)),float(i),.1+.001*i,30.+i,.003],
       'target':100.+i*.2+j} for i in range(150) for j in range(3)]
with tempfile.TemporaryDirectory(prefix='airfoil fixture ',dir=root/'runs') as tmp:
    folder=Path(tmp)/'review'; memory=Path(tmp)/'checkout'
    review=ab.prepare_rows(rows,folder)
    ab.approve(folder,review['sha256'],'SOFTWARE FIXTURE ONLY; NOT USER APPROVAL',root=memory)
    result=ab.execute(folder,root=memory)
    if not result['measurement_valid']:
        err=folder/'run/output/stderr.log'
        raise RuntimeError(json.dumps(result)+'\n'+(err.read_text()[-3000:] if err.exists() else 'No stderr'))
    assert result['fits']==15 and not result['final_holdout_scored']
    assert ab.audit(folder)['audit_ok']
    try: ab.execute(folder,root=memory)
    except ValueError as exc: assert 'reserved' in str(exc)
    else: raise AssertionError('Repeat allowed')
    second=Path(tmp)/'another'; ab.prepare_rows(rows,second)
    try: ab.approve(second,review['sha256'],'fixture',root=memory)
    except ValueError as exc: assert 'reserved' in str(exc)
    else: raise AssertionError('Copied qualification allowed')
    path=folder/'run/output/predictions.json'; raw=json.loads(path.read_text())
    raw['results'][0]['predictions'][0]['prediction']+=1; path.write_text(json.dumps(raw))
    try: ab.audit(folder)
    except ValueError: pass
    else: raise AssertionError('Tampered predictions accepted')
    print(json.dumps({'synthetic_only':True,'actual_isolated_fits':15,'strict_audit_passed':True,
        'tamper_rejected':True,'repeat_and_copy_rejected':True,'model_calls':0,'real_data_scored':False},indent=2))
