"""Unified dispatch for a proposal -> human review -> one execution workflow.

The immutable evaluation-only v1 task binding is not silently redefined as an
autonomous executor. These are explicit workflow modes with a human boundary.
"""
from pathlib import Path
import re

from .portable import ROOT
from .tabular_audit import validated_baseline
from .tabular_data import write_json
from .tabular_memory import assert_available


def research(name,stage,baseline=None,review=None,root=ROOT,*,data_review=None,intended_use=None):
    if not isinstance(name,str) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}',name): raise ValueError('Invalid workflow ID')
    if stage=='propose':
        if baseline is None or review is not None: raise ValueError('Proposal mode requires --baseline and no --review')
        packet,parts,_,_=validated_baseline(baseline)
        from .data_admission import trial_snapshot
        from .tabular_trial import ADAPTER,FIXTURE
        trial_snapshot(packet,ADAPTER,FIXTURE,data_review,intended_use)
        assert_available(packet,parts,root)  # Before any output, preflight or model call.
        output=Path(root)/'runs'/name
        output.mkdir(mode=0o700,parents=True,exist_ok=False)
        write_json(output/'workflow-start.json',{'kind':'tabular-reviewed-workflow','version':1,
            'id':name,'stage':'propose','baseline_sha256':packet['sha256']})
        from .tabular_proposer import propose
        from .tabular_trial import prepare
        try:
            outcome=propose(baseline,output/'proposal',root=root,data_review=data_review,intended_use=intended_use)
            if outcome['status']=='AWAITING_RESEARCH_REVIEW':
                prepared=prepare(baseline,output/'proposal/proposal.json',output/'review',output/'proposal/literature.json',root=root,
                                 data_review=data_review,intended_use=intended_use)
                result={'status':'AWAITING_RESEARCH_REVIEW','review':prepared['review'],'sha256':prepared['sha256'],
                        'final_holdout_scored':False,'human_approval_required':True}
            else: result={'status':outcome['status'],'final_holdout_scored':False,'proposal_result':outcome}
        except (OSError,ValueError,KeyError,TypeError) as exc:
            result={'status':'INCOMPLETE','final_holdout_scored':False,'reason':str(exc),'automatic_retry':False}
        write_json(output/'workflow-result.json',result)
        return result
    if stage=='execute':
        if data_review is not None or intended_use is not None: raise ValueError('Execution uses frozen qualification; no runtime override')
        if review is None or baseline is not None: raise ValueError('Execution mode requires --review and no --baseline')
        from .tabular_trial import load_trial,execute_trial,audit_trial
        packet,_,_=load_trial(review)
        if name!=packet['content']['proposal']['id']: raise ValueError('--id must match the frozen candidate proposal ID')
        result=execute_trial(review,root=root)  # Its own exact human-approval and exclusion gates.
        audit=audit_trial(review) if result['measurement_valid'] else None
        return {'status':result['status'],'measurement_valid':result['measurement_valid'],
                'final_holdout_scored':result['final_holdout_scored'],'audit':audit,
                'report':str(Path(review)/'trial-run/REPORT.md'),'automatic_retry':False}
    raise ValueError('Tabular workflow requires explicit --stage propose or execute')
