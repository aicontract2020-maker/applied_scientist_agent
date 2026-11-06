"""Read-only evidence and exclusion acceptance. No model, training or inference."""
import argparse
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_harness.tabular_evidence import verify,unpack
from research_harness.tabular_memory import import_memory,snapshot,record_from_trial,assert_available
from research_harness.tabular_trial import load_trial
from research_harness.memory import read_json


def check(packet,memory,output):
    verification=verify(packet)
    if not verification['audit_ok']: raise ValueError('Evidence audit failed')
    output=Path(output); output.mkdir(mode=0o700,parents=True,exist_ok=False)
    review=Path(unpack(packet,output/'evidence')['review'])
    receipt=import_memory(memory,root=output)
    expected=record_from_trial(review)
    records=snapshot(output)
    if expected not in records: raise ValueError('Memory does not contain the audited trial exclusion')
    _,parts,_=load_trial(review,current=False)
    try: assert_available(read_json(review/'baseline/bundle.json'),parts,root=output)
    except ValueError as exc:
        if 'already reserved' not in str(exc): raise
    else: raise ValueError('Copied holdout was not blocked')
    try: load_trial(review,current=True)
    except ValueError as exc:
        if 'review-only' not in str(exc): raise
    else: raise ValueError('Imported approval became executable')
    result={'read_only_handoff_passed':True,'platform':platform.system(),'python':platform.python_version(),
            'packet_sha256':verification['sha256'],'memory_sha256':receipt['sha256'],
            'trial_sha256':expected['trial_sha256'],'decision':expected['state'],
            'excluded_feature_groups':len(expected['data_keys']),
            'imported_approval_not_executable':True,'consumed_data_blocked':True,
            'model_calls':0,'training_runs':0,'new_prediction_runs':0,
            'limit':'Record consistency and local fresh-directory acceptance; not independent human usability or authenticated execution'}
    (output/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--packet',required=True); parser.add_argument('--memory',required=True); parser.add_argument('--out',required=True)
    args=parser.parse_args(); print(json.dumps(check(args.packet,args.memory,args.out),indent=2))
