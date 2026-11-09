"""Actual isolation, six-fit candidate worker, STOP/go and audit; SYNTHETIC ONLY."""
import json
import argparse
from pathlib import Path
import random
import sys
import tempfile
import shutil

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_harness.tabular_baseline import prepare_rows,approve,execute
from research_harness.tabular_trial import prepare,approve_trial,execute_trial,audit_trial,preflight_trial,ADAPTER,FIXTURE
from examples.data_qualification.baseline import qualification,USE
from research_harness.tabular_data import write_json

root=Path(__file__).resolve().parents[1]; (root/'runs').mkdir(exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--export-fixture',help='Keep a new synthetic-only handoff folder for independent installation acceptance')
args=parser.parse_args()
rng=random.Random(21); rows=[]
for i in range(350):
    x=[rng.random() for _ in range(10)]
    rows.append({'id':f'fixture-{i}','features':x,'target':30*x[3]*x[4]+x[5]})
with tempfile.TemporaryDirectory(prefix='tabular trial fixture ',dir=root/'runs') as tmp:
    work=Path(tmp); baseline=work/'baseline'
    packet=prepare_rows(rows,baseline,{'id':'synthetic-software-fixture'})
    approve(baseline,packet['sha256'],'SOFTWARE FIXTURE ONLY')
    qualified=execute(baseline)
    if not qualified.get('measurement_valid') or qualified.get('selected_baseline')!='hgb':
        raise RuntimeError('Software fixture baseline failed: '+json.dumps(qualified))
    source='def augment(row):\n    return [row[3] * row[4]]\n'
    proposal={'id':'synthetic-feature-trial','hypothesis':'Synthetic software exercise only',
        'mechanism':'Product feature fixture','why_new':'Arithmetic input interaction, not prediction calibration',
        'feature_rationale':'Fixed product without fitted parameters','candidate_source':source,
        'evidence':[{'url':'https://arxiv.org/abs/2207.08815','claim':'SOFTWARE FIXTURE, NOT A LITERATURE CLAIM'},
                    {'url':'https://arxiv.org/abs/2106.11959','claim':'SOFTWARE FIXTURE, NOT A LITERATURE CLAIM'}],
        'limitations':['Synthetic deterministic targets; no empirical or scientific claim']}
    write_json(work/'proposal.json',proposal)
    write_json(work/'library.json',[{'url':item['url'],'title':'SOFTWARE FIXTURE','full_text':'NOT REAL PAPER CONTENT',
                                   'pdf_sha256':'a'*64} for item in proposal['evidence']])
    qualification(work/'qualification',ADAPTER,FIXTURE)
    trial=work/'trial'; review=prepare(baseline,work/'proposal.json',trial,work/'library.json',root=work,
                                      data_review=work/'qualification/packet.json',intended_use=USE)
    # Fixtures never create approval or reservation in the user's real data scope.
    approve_trial(trial,review['sha256'],'SOFTWARE FIXTURE ONLY',root=work)
    assert preflight_trial(trial,root=work)['data_admission']['execution_authorized'] is False
    result=execute_trial(trial,root=work)
    if not result['measurement_valid']: raise RuntimeError(json.dumps(result))
    checked=audit_trial(trial)
    if not checked['audit_ok']: raise RuntimeError(json.dumps(checked))
    request=json.loads((trial/'trial-run/inputs/request.json').read_text())
    assert set(request)=={'train','validation','holdout','candidate'}
    assert all(set(row)=={'id','features'} for key in ('validation','holdout') for row in request[key])
    try: execute_trial(trial,root=work)
    except ValueError as exc: assert 'already reserved' in str(exc)
    else: raise AssertionError('Repeated holdout execution allowed')
    from research_harness.tabular_evidence import export,verify,unpack
    from research_harness.tabular_memory import export_memory,import_memory,assert_available
    from research_harness.tabular_trial import load_trial
    evidence=work/'private-evidence.json'; export(trial,evidence)
    assert verify(evidence)['audit_ok']
    memory=work/'memory.json'; export_memory(memory,root=work)
    clone=work/'fresh-clone'; clone.mkdir(); import_memory(memory,root=clone)
    copied=Path(unpack(evidence,clone/'evidence')['review'])
    assert audit_trial(copied)['audit_ok']
    _,parts,_=load_trial(copied,current=False)
    try: assert_available(json.loads((copied/'baseline/bundle.json').read_text()),parts,root=clone)
    except ValueError as exc: assert 'already reserved' in str(exc)
    else: raise AssertionError('Imported memory did not block reuse')
    try: load_trial(copied)
    except ValueError as exc: assert 'review-only' in str(exc)
    else: raise AssertionError('Evidence copy is executable')
    if args.export_fixture:
        target=Path(args.export_fixture); target.mkdir(mode=0o700,parents=True,exist_ok=False)
        shutil.copyfile(evidence,target/'synthetic-evidence.json'); (target/'synthetic-evidence.json').chmod(0o600)
        shutil.copyfile(memory,target/'synthetic-memory.json'); (target/'synthetic-memory.json').chmod(0o600)
        (target/'README.md').write_text('# SYNTHETIC SOFTWARE FIXTURE ONLY\n\n'
            'No real research data, human approval, model account or paper full text. '
            'Paper URLs are schema fixtures, not evidence claims. STOP/CONTINUE is a software output, not scientific performance.\n\n'
            'Use scripts/check-tabular-handoff.py with these two packets in a fresh destination.\n')
    path=trial/'trial-run/result.json'; value=json.loads(path.read_text()); value['mean_effect']+=1
    path.write_text(json.dumps(value)); assert not audit_trial(trial)['audit_ok']
    print(json.dumps({'synthetic_only':True,'actual_isolated_six_fit_trial':True,'strict_audit_passed':True,
                      'tampering_rejected':True,'repeat_execution_rejected':True,'private_evidence_and_memory_handoff':True,
                      'candidate_data_admission_checked':True,'real_data_scored':False,'model_calls':0},indent=2))
