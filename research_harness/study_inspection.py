"""Read-only run inspection. Never resume a process, score an image or edit evidence."""
import hashlib
import json
import math
from pathlib import Path

from .core import digest, number
from .memory import read_json, _object
from .observations import summarize, validate_result, passes_gates


class Evidence:
    def __init__(self, root):
        self.root = Path(root)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError('Run must be an existing regular directory')
        self.errors = []
        self.fingerprints = {}

    def signature(self, path):
        try:
            stat = path.lstat()
            return (stat.st_ino, stat.st_size, stat.st_mtime_ns)
        except FileNotFoundError:
            return None

    def path(self, name, required=True):
        path = self.root/name
        self.fingerprints.setdefault(name, self.signature(path))
        if path.is_symlink() or not path.is_file():
            if required or path.is_symlink():
                self.errors.append(f'{name}: missing or not a regular file')
            return None
        return path

    def json(self, name, required=True):
        path = self.path(name, required)
        if path is None:
            return None
        try:
            return read_json(path)
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            self.errors.append(f'{name}: {type(exc).__name__}: {exc}')
            return None

    def text(self, name, required=True):
        path = self.path(name, required)
        if path is None:
            return None
        try:
            if path.stat().st_size > 4*1024*1024:
                raise ValueError('File exceeds 4 MiB inspection limit')
            return path.read_text()
        except (OSError, ValueError) as exc:
            self.errors.append(f'{name}: {exc}')
            return None

    def ledger(self):
        text = self.text('ledger.jsonl')
        events = []
        if text is not None:
            for ordinal, line in enumerate(text.splitlines(), 1):
                try:
                    def nonfinite(value):
                        raise ValueError('Non-finite ledger value')
                    event = json.loads(line, object_pairs_hook=_object, parse_constant=nonfinite)
                    if not isinstance(event, dict) or not isinstance(event.get('event'), str):
                        raise ValueError('Expected an event object')
                    events.append(event)
                except ValueError:
                    self.errors.append(f'ledger.jsonl: invalid/partial event at line {ordinal}; run may be updating or interrupted')
        return events

    def stable(self):
        changed = [name for name, signature in self.fingerprints.items()
                   if self.signature(self.root/name) != signature]
        if changed:
            self.errors.append('Evidence changed during inspection: '+', '.join(changed))
        return not changed


def _stage(events, result):
    if result:
        if result.get('status') == 'REJECTED':
            return 'REJECTED'
        if result.get('measurement_valid') is False:
            return 'INVALID'
        if result.get('status') in ('STOP', 'CONTINUE'):
            return result['status']
        return 'INCOMPLETE'
    for event in reversed(events):
        stage = {'EXPERIMENT_STARTED':'EXPERIMENT_STARTED', 'REGISTER':'REGISTERED',
                 'INTERVENTION_REVIEW_STARTED':'REVIEW_STARTED', 'PRIMARY_READ_COMPLETED':'READING',
                 'AGENT_STARTED':'AGENT_STARTED', 'SESSION_CREATED':'PREPARED'}.get(event['event'])
        if stage:
            return stage
    return 'UNKNOWN'


def run_status(directory):
    evidence = Evidence(directory)
    events = evidence.ledger()
    result = evidence.json('result.json', required=False)
    if result is not None and not isinstance(result, dict):
        evidence.errors.append('result.json: expected an object'); result = None
    stable = evidence.stable()
    return {'run':str(Path(directory).resolve()), 'stage':_stage(events,result),
            'declared_result':result.get('status') if result else None,
            'measurement_valid':result.get('measurement_valid') if result else None,
            'last_event':events[-1] if events else None, 'liveness':'UNKNOWN',
            'agent_finish_recorded':any(x['event']=='AGENT_FINISHED' for x in events),
            'snapshot_stable':stable, 'errors':evidence.errors,
            'note':'Stage is recorded progress, not process liveness or an integrity verdict. No resume/retry is performed.'}


def list_studies(root):
    root = Path(root)
    rows = []
    names = {p.name for p in (root/'local_studies').glob('*') if p.is_dir() and not p.is_symlink()}
    names.update(p.name for p in (root/'runs').glob('*') if p.is_dir() and not p.is_symlink()
                 and not (p/'protocol.json').exists()
                 and ((p/'ledger.jsonl').exists() or (p/'result.json').exists()))
    for name in sorted(names):
        run = root/'runs'/name
        if run.is_dir() and not run.is_symlink():
            rows.append({'id':name, **run_status(run)})
        else:
            rows.append({'id':name,'stage':'RESERVED','liveness':'UNKNOWN','run':None,'errors':[]})
    return {'studies':rows,'read_only':True,'note':'Local autonomous run directories and reservations only; imported memory is shown by memory status.'}


def audit_run(directory):
    evidence = Evidence(directory)
    events = evidence.ledger()
    result = evidence.json('result.json')
    session = evidence.json('session.json')
    report = evidence.text('agent-REPORT.md')
    searches = evidence.json('search-records.json')
    checks = []
    def check(label, passed):
        checks.append({'check':label,'passed':bool(passed)})
        if not passed:
            evidence.errors.append(label)
    def count(kind):
        return sum(x['event']==kind for x in events)
    def ordered(kinds):
        types = [x['event'] for x in events]
        return all(types.count(kind)==1 for kind in kinds) and [types.index(k) for k in kinds] == sorted(types.index(k) for k in kinds)
    def compare(label, expected, observed):
        def equal(a,b):
            if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
                return math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9)
            if isinstance(a,list) and isinstance(b,list):
                return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
            if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,bool):
                return False
            return a==b
        check(label, equal(expected,observed))
    recomputed = None
    try:
        if not isinstance(result,dict) or not isinstance(session,dict):
            raise ValueError('Missing/malformed final result or session; inspect progress, do not resume automatically')
        terminal = result.get('status') in ('STOP','CONTINUE','REJECTED')
        check('Recognized terminal result',terminal)
        finished = [x for x in events if x['event']=='AGENT_FINISHED']
        check('One successful agent finish',len(finished)==1 and type(finished[0].get('exit_code')) is int and finished[0]['exit_code']==0)
        check('Agent report agrees with declared result',report is not None and result.get('status','__missing__') in report)
        reads = [x for x in events if x['event']=='PRIMARY_READ_COMPLETED']
        check('Two primary reads including full-text extraction recorded',len(reads)>=2 and any(x.get('full') is True for x in reads))
        check('Native search evidence present',isinstance(searches,list) and bool(searches))
        operations = [x.get('operation') for x in events if x['event']=='AGENT_REQUEST']
        if result.get('status')=='REJECTED':
            check('Rejection has no scientific measurement',result.get('scientific_status')=='NOT_RUN' and result.get('measurement_valid') is None and result.get('experiment_started') is False)
            check('Rejected before registration or inference',count('REGISTER')==count('EXPERIMENT_STARTED')==count('DECISION')==0 and operations.count('run')==0 and operations.count('register')==1)
            check('Rejection then session finish',ordered(['REGISTRATION_REJECTED','AGENT_FINISHED']))
            rejection = [x for x in events if x['event']=='REGISTRATION_REJECTED']
            check('Rejection ledger matches result',len(rejection)==1 and rejection[0].get('result')==result)
            check('Rejected run has no registration file',evidence.path('registered.json',required=False) is None)
        elif result.get('status') in ('STOP','CONTINUE'):
            protocol = evidence.json('registered.json')
            if not isinstance(protocol,dict):
                raise ValueError('Missing frozen registration')
            policy, plan = protocol['policy'], protocol['plan']
            from .task_contracts import validate_sr_policy
            validate_sr_policy(policy)
            code = evidence.text('candidate.py'); final_code = evidence.text('agent-candidate.py')
            final_plan = evidence.json('agent-research.json')
            code_hash = hashlib.sha256(code.encode()).hexdigest() if code is not None else None
            check('Frozen and final candidate hashes match',code_hash==protocol['candidate_sha256'] and final_code==code)
            check('Final plan matches frozen plan',final_plan==plan)
            for field in ('controls','minimum_effect','max_latency_ratio','bootstrap','observation_ids'):
                check('Plan preserves policy field: '+field,plan.get(field)==policy[field])
            registration = [x for x in events if x['event']=='REGISTER']
            check('Registration ledger binds protocol and code',len(registration)==1 and registration[0].get('protocol_sha256')==digest(protocol) and registration[0].get('candidate_sha256')==code_hash)
            check('Single registration/run, no rejection',operations.count('register')==operations.count('run')==1 and count('REGISTRATION_REJECTED')==0 and count('EXPERIMENT_STARTED')<=1)
            check('Registration, decision and finish ordered',ordered(['REGISTER','DECISION','AGENT_FINISHED']))
            decisions = [x for x in events if x['event']=='DECISION']
            starts = [x for x in events if x['event']=='EXPERIMENT_STARTED']
            check('Experiment start binds registered protocol',all(x.get('protocol_sha256')==digest(protocol) for x in starts))
            check('Decision ledger matches result',len(decisions)==1 and decisions[0].get('result')==result)
            if policy.get('intervention_review',{}).get('required'):
                review = evidence.json('intervention-review.json')
                check('Review PASS bound to frozen code/plan',isinstance(review,dict) and review.get('decision')=='PASS' and review.get('candidate_sha256')==code_hash and review.get('plan_sha256')==digest(plan))
                review_started = [x for x in events if x['event']=='INTERVENTION_REVIEW_STARTED']
                review_finished = [x for x in events if x['event']=='INTERVENTION_REVIEW_FINISHED']
                check('Review ledger agrees with PASS and candidate',len(review_started)==len(review_finished)==1 and review_started[0].get('candidate_sha256')==code_hash and review_finished[0].get('decision')=='PASS')
                check('Review completed before registration',ordered(['INTERVENTION_REVIEW_STARTED','INTERVENTION_REVIEW_FINISHED','REGISTER']))
            if result.get('measurement_valid') is True:
                check('One experiment before decision',ordered(['REGISTER','EXPERIMENT_STARTED','DECISION','AGENT_FINISHED']))
                rows = evidence.json('observations.json')
                if not isinstance(rows,list):
                    raise ValueError('Missing paired observations')
                ids = policy['observation_ids']
                if not isinstance(ids,list) or not 2<=len(ids)<=100 or len(set(ids))!=len(ids):
                    raise ValueError('Invalid frozen observation identities')
                bootstrap = policy['bootstrap']
                if (type(bootstrap['resamples']) is not int or not 1000<=bootstrap['resamples']<=100000
                        or type(bootstrap['seed']) is not int or not .8<=bootstrap['confidence']<=.99):
                    raise ValueError('Unbounded or invalid frozen bootstrap')
                if len(ids)*bootstrap['resamples']>1000000:
                    raise ValueError('Frozen bootstrap exceeds read-only audit work limit; no partial recomputation')
                number(policy['minimum_effect'],'minimum_effect',0)
                number(policy['max_latency_ratio'],'max_latency_ratio',0)
                if policy['primary_metric']['direction']!='higher':
                    raise ValueError('Only current higher-is-better SR results supported')
                validate_result(policy,{'observations':rows,'baseline_score':result['baseline_psnr_y'],'candidate_score':result['candidate_psnr_y']})
                recomputed = summarize(policy,rows)
                recomputed['mean_gain_db'] = sum(recomputed['observation_effects'])/len(rows)
                for field in ('mean_gain_db','observation_count','observation_effects','observation_effect_std','bootstrap_interval','bootstrap_confidence','latency_ratio'):
                    compare('Recomputed '+field,recomputed[field],result.get(field))
                passed = passes_gates(policy, recomputed['mean_gain_db'], recomputed)
                compare('Decision follows all frozen gates','CONTINUE' if passed else 'STOP',result['status'])
            else:
                check('Invalid measurement closes STOP',result.get('measurement_valid') is False and result['status']=='STOP')
    except (ValueError,TypeError,KeyError,IndexError,ZeroDivisionError,OverflowError) as exc:
        evidence.errors.append(f'Cannot establish integrity: {type(exc).__name__}: {exc}')
    stable = evidence.stable()
    return {'audit_ok':not evidence.errors,'read_only':True,'run':str(Path(directory).resolve()),
            'stage':_stage(events,result if isinstance(result,dict) else None),
            'declared_scientific_status':result.get('status') if isinstance(result,dict) else None,
            'measurement_valid':result.get('measurement_valid') if isinstance(result,dict) else None,
            'snapshot_stable':stable,'checks':checks,'errors':evidence.errors,'recomputed':recomputed,
            'limits':['Artifact consistency and recorded-score reanalysis only; no pixel scoring, model execution, process liveness, authenticity or proof of novelty.',
                      'Original images/weights and historical input files are not reread; a historical checkout may have legitimately changed.',
                      'An invalid measurement or rejected proposal can have internally consistent evidence; audit success is not scientific success.']}
