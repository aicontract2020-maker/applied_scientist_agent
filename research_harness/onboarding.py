"""One-command independent research cycle with explicit workflow validation."""
import json
import sys
from pathlib import Path

from .portable import ROOT, _new_study, sha


def validate_workflow(destination, *, require_integrity=False):
    destination=Path(destination)
    result=json.loads((destination/'result.json').read_text())
    session=json.loads((destination/'session.json').read_text())
    events=[json.loads(s) for s in (destination/'ledger.jsonl').read_text().splitlines()]
    types=[e['event'] for e in events]
    operations=[e['operation'] for e in events if e['event']=='AGENT_REQUEST']
    errors=[]
    rejected=result.get('status')=='REJECTED' and result.get('scientific_status')=='NOT_RUN'
    required=['REGISTER','EXPERIMENT_STARTED','DECISION','AGENT_FINISHED']
    if rejected:
        if types.count('REGISTRATION_REJECTED')!=1 or any(x in types for x in ('REGISTER','EXPERIMENT_STARTED','DECISION')) or operations.count('register')!=1 or 'run' in operations:
            errors.append('Rejected proposal did not stop before registration/inference')
    elif not all(types.count(event)==1 for event in required):errors.append('Missing or repeated registration/experiment/decision/session finish')
    elif not all(types.index(a)<types.index(b) for a,b in zip(required,required[1:])):errors.append('Lifecycle order incorrect')
    finished=[e for e in events if e['event']=='AGENT_FINISHED']
    if not finished or finished[-1].get('exit_code')!=0:errors.append('Agent did not exit successfully')
    if not rejected and (operations.count('run')!=1 or operations.count('register')!=1):errors.append('Not exactly one agent-triggered registration/run')
    if not rejected and not result.get('measurement_valid'):errors.append('Experiment measurement invalid/incomplete')
    registered=destination/'registered.json'
    if registered.exists():
        protocol=json.loads(registered.read_text())
        if protocol.get('policy',{}).get('intervention_review',{}).get('required'):
            review_path=destination/'intervention-review.json'
            review=json.loads(review_path.read_text()) if review_path.exists() else {}
            from .core import digest
            if review.get('decision')!='PASS' or review.get('candidate_sha256')!=protocol['candidate_sha256'] or review.get('plan_sha256')!=digest(protocol['plan']):
                errors.append('Missing or mismatched intervention review PASS')
        if not (destination/'agent-candidate.py').exists() or sha(destination/'agent-candidate.py')!=protocol['candidate_sha256']:
            errors.append('Final agent code differs from preregistered code')
        plan=destination/'agent-research.json'
        if not plan.exists() or json.loads(plan.read_text())!=protocol['plan']:errors.append('Final agent plan differs from preregistration')
    report=destination/'agent-REPORT.md'
    if not report.exists() or result.get('status','INCOMPLETE') not in report.read_text():errors.append('Missing or inconsistent agent report')
    completed=[e for e in events if e['event']=='PRIMARY_READ_COMPLETED']
    if len(completed)<2 or not any(e['full'] for e in completed):errors.append('Required primary-source reading not completed')
    search=destination/'search-records.json'
    if not search.exists() or not json.loads(search.read_text()):errors.append('Missing native live-search evidence')
    raw_events=[json.loads(s) for s in (destination/'agent-events.jsonl').read_text().splitlines()]
    usage=[e['usage'] for e in raw_events if e.get('type')=='turn.completed']
    reviewer_events=destination/'artifacts/reviewer/logs/stdout.log'
    reviewer_usage=[]
    if reviewer_events.exists():
        for line in reviewer_events.read_text().splitlines():
            try: item=json.loads(line)
            except ValueError: continue
            if item.get('type')=='turn.completed': reviewer_usage.append(item.get('usage'))
    completion_audit=None
    if require_integrity:
        from .study_inspection import audit_run
        completion_audit=audit_run(destination)
        errors.extend('Completion audit: '+message for message in completion_audit['errors'])
    verdict={'completion_audit':completion_audit,'workflow_completed':not errors, 'experiment_started': 'EXPERIMENT_STARTED' in types, 'proposal_rejected':rejected, 'reviewer_model_usage':reviewer_usage,'errors':errors,'scientific_status':result.get('scientific_status',result.get('status')),
             'measurement_valid':result.get('measurement_valid',False),'operations':operations,'isolation_backend':session.get('isolation_backend','historical-unspecified'),
             'primary_reads_completed':len(completed),'full_text_extractions':sum(e['full'] for e in completed),
             'session_seconds':session['total_wall_seconds'],'session_machine_hour_proxy_usd':session['local_proxy_usd'],
             'model_usage':usage,'actual_model_billing_usd':None,
             'network_scope':'Candidate network denied; actor egress is not domain-hard-isolated',
             'interpretation':'One bounded feasibility cycle, not scientific reliability or commercial validation'}
    (destination/'workflow.json').write_text(json.dumps(verdict,indent=2)+'\n')
    (destination/'REPORT.md').write_text('# Autonomous cycle outcome\n\n'+
        f"Workflow completed: {verdict['workflow_completed']}\n\nScientific decision: {result.get('status')}\n\n"+
        'Trusted evaluator result:\n\n```json\n'+json.dumps(result,indent=2)+'\n```\n\n'+
        'Workflow/cost audit:\n\n```json\n'+json.dumps(verdict,indent=2)+'\n```\n\n'+
        'The model invoice, reference peak memory, setup and long-term storage costs are not fully metered. '
        'Experiment machine-hour cost is a subset of session cost; do not add them. '
        'See agent-REPORT.md for the agent interpretation, observations.json for paired results, '
        'artifacts/ for retrieved papers and candidate arrays, and registered.json for immutable criteria. '
        'Paper text may be truncated; library.json declares this. All local run artifacts may contain sensitive text.\n')
    return verdict


def research(name, task='swinir-s-x2', *, stage=None, baseline=None, review=None, data_review=None, intended_use=None):
    if task=='tabular-regression' and stage is not None:
        from .tabular_workflow import research as tabular_research
        return tabular_research(name,stage,baseline,review,data_review=data_review,intended_use=intended_use)
    if stage is not None or baseline is not None or review is not None or data_review is not None or intended_use is not None:
        raise ValueError('Staged workflow arguments require the tabular-regression task')
    from .task_contracts import require_autonomous
    require_autonomous(task)
    from .state_lock import research_lock
    with research_lock(ROOT):
        return _research_locked(name)


def _research_locked(name):
    from .doctor import doctor
    from .literature_study import LiteratureStudy
    print("[1/3] Checking environment and isolation (no model call)...", file=sys.stderr, flush=True)
    health=doctor()
    if not health['ok']:
        failed=[f"{c['name']}: {c['detail']} — {c.get('fix','')}" for c in health['checks'] if not c['ok']]
        raise ValueError('Preflight failed before reserving data or calling a model:\n'+'\n'.join(failed))
    output=ROOT/'runs'/name
    if output.exists():raise ValueError('Run already exists. Read its report; no automatic repeat or overwrite')
    print("[2/3] Freezing a fresh study and holdout...", file=sys.stderr, flush=True)
    study=_new_study(name, ROOT)
    (study/'preflight.json').write_text(json.dumps(health,indent=2)+'\n')
    # preflight.json is diagnostic, not an experimental input; frozen inputs are explicit.
    print(f"[3/3] Running one live agent cycle. Evidence: {output}", file=sys.stderr, flush=True)
    result=LiteratureStudy(output,study).launch()
    verdict=validate_workflow(output, require_integrity=True)
    if not verdict['workflow_completed']:
        raise ValueError(f'Cycle incomplete; no automatic retry. Inspect {output}/workflow.json: {verdict["errors"]}')
    return {'workflow_completed':True,'scientific_decision':result.get('scientific_status',result['status']),'proposal_decision':result['status'],'report':str(output/'REPORT.md'),'study':str(study),'run':str(output)}
