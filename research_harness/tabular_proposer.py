"""Isolated proposal-only actor. No dataset rows, training, labels or score RPC."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .autonomy import bounded_process
from .core import digest
from .memory import read_json
from .planning import object_schema
from .portable import ROOT
from .primary_literature import fetch_primary
from .state_lock import research_lock
from .tabular_audit import validated_baseline
from .tabular_data import write_json
from .tabular_trial import validate_proposal, scope_for, RECIPE

TEXT={'type':'string'}
SCHEMA=object_schema({**{name:TEXT for name in ('id','hypothesis','mechanism','why_new','feature_rationale','candidate_source')},
    'evidence':{'type':'array','items':object_schema({'url':TEXT,'claim':TEXT})},
    'limitations':{'type':'array','items':TEXT}})
PROMPT='''Read context.json. Conduct ONE literature-grounded feature proposal for fixed HGB regression.
Search primary literature using native web search, at most six searches. Read the methods of
two or three DISTINCT arXiv papers. Cite canonical https://arxiv.org/abs/ID URLs (version optional).
Explain precisely what they support, and distinguish your inference from their findings.
Never download, look up or reconstruct Abalone data/labels/predictions or benchmark outcomes.
You receive only a public task description and historical aggregate baseline qualification.
Do not train models, run experiments, access the checkout, call other agents, or tune candidates.
Choose one hypothesis and write candidate_source in the following CLOSED language:
def augment(row):
    return [ONE_TO_THREE_ARITHMETIC_EXPRESSIONS]
Expressions use only row[0]..row[9], finite constants abs<=10, + - * / unary +/- and
abs(x), min(x,y), max(x,y), sqrt(x), log1p(x). No imports, assignments, loops, comprehensions,
attributes, conditionals, power, annotations or other calls. Each output must actually depend
on at least TWO original columns. Original ten columns are automatically preserved.
Use domain-safe expressions including zero-valued features. No fitted statistics, scaling
search, model changes or prediction postprocessing. No constant median-residual calibration:
that route was rejected and must stay closed. Adding complexity to repair it is forbidden.
Select the smallest distinct feature mechanism supported by external evidence; never claim
novelty or guaranteed improvement. Freeze every constant and explain it in feature_rationale.
The frozen protocol requires >=0.05 ring MAE gain, positive bootstrap lower bound, <=1.1
latency ratio, three seeds as repeatability checks, and failure STOP with no parameter rescue.
Do not manufacture evidence, costs, independent-row assumptions or human approval. Clearly
state weak baseline comparisons and doubts. Return exactly the supplied JSON schema; this
is a proposal for human review, NOT a registered/approved experiment. Do not edit/revise
after rejection. You have 600 seconds; no retries or alternative candidates.
'''


def actor_executable():
    """Use the installed native macOS executable when npm ships it; no download."""
    import sys,platform
    found=shutil.which('codex')
    if not found: raise ValueError('Codex CLI is missing')
    entry=Path(found).resolve()
    if sys.platform=='darwin' and entry.name=='codex.js':
        arch='arm64' if platform.machine()=='arm64' else 'x64'
        triple='aarch64' if arch=='arm64' else 'x86_64'
        native=entry.parent.parent/f'node_modules/@openai/codex-darwin-{arch}/vendor/{triple}-apple-darwin/bin/codex'
        if not native.is_file(): raise ValueError('Installed native Codex executable is missing; no fallback or download')
        return str(native)
    return 'codex' if sys.platform=='linux' else str(entry)


def launch_failure_evidence(folder):
    """Only an observed Node initialization abort, before any agent event, is recoverable."""
    folder=Path(folder)
    process=read_json(folder/'process.json')
    result=read_json(folder/'result.json')
    stdout=folder/'process/stdout.log'; stderr=folder/'process/stderr.log'
    if any(p.is_symlink() for p in (folder,folder/'process',stdout,stderr)):
        raise ValueError('Linked failure evidence')
    if (process.get('returncode')!=-6 or result.get('status') not in ('REJECTED','INCOMPLETE')
            or stdout.stat().st_size!=0 or (folder/'proposal.json').exists()
            or stderr.stat().st_size>65536 or 'node::InitializeOncePerProcessInternal' not in stderr.read_text()):
        raise ValueError('Recovery is limited to the recorded pre-agent Node initialization abort')
    return {'reason':'Observed Node initialization SIGABRT with zero agent events and no proposal; not a failed research hypothesis',
            'prior_process_sha256':digest(process),'prior_result_sha256':digest(result),
            'change':'Use the already-installed native Codex executable under the unchanged OS profile',
            'limit':'One explicit infrastructure recovery; never after search, proposal, training or scoring'}


def propose(baseline, output, root=ROOT, recover_launch=None):
    import sys
    if sys.platform not in ('linux','darwin'): raise ValueError('Proposal actor requires Linux or macOS isolation')
    from .linux_isolation import linux_actor_command
    from .doctor import isolation_probe
    with research_lock(root):
        packet,_,result,_=validated_baseline(baseline)
        if result['status']!='CONTINUE' or result['selected_baseline']!='hgb': raise ValueError('Qualified HGB required')
        scope=scope_for(packet); folder=Path(output).absolute()
        if folder.exists() or folder.is_symlink(): raise ValueError('Proposal output exists; no retries')
        reservation=Path(root)/'.research-memory/tabular-proposer'/scope
        if any(p.is_symlink() for p in (reservation,reservation.parent,reservation.parent.parent)):
            raise ValueError('Linked proposal reservation')
        recovery=None
        if recover_launch is not None:
            if sys.platform!='darwin': raise ValueError('This observed launcher recovery applies only to macOS')
            recovery=launch_failure_evidence(recover_launch)
            prior=read_json(reservation/'reservation.json')
            if (prior.get('baseline_sha256')!=packet['sha256'] or prior.get('scope')!=scope
                    or read_json(reservation/'decision.json')!=read_json(Path(recover_launch)/'result.json')
                    or (reservation/'launch-recovery.json').exists()):
                raise ValueError('Recovery does not match the retained failed attempt or was already consumed')
        elif reservation.exists():
            raise ValueError('Proposal session already reserved; preserve failure, no automatic retry')
        probe=isolation_probe(check_login=True)
        context={'task':'Predict UCI Abalone rings; engineering benchmark, not commercial proof',
            'columns':['sex M','sex F','sex I','length','diameter','height','whole weight','shucked weight','viscera weight','shell weight'],
            'baseline_mae':result['mean_validation_mae'],'baseline_parameters':packet['content']['recipe']['baseline_parameters']['hgb'],
            'stopped':['T1 additive validation median residual: bound 0.012122178108001425 < 0.05; no rescue'],
            'recipe':RECIPE,'data_access':'No dataset rows or labels; all real computation remains behind human review'}
        if recovery is None:
            reservation.mkdir(parents=True,exist_ok=False)
            write_json(reservation/'reservation.json',{'baseline_sha256':packet['sha256'],'scope':scope,'status':'RESERVED'})
        else: write_json(reservation/'launch-recovery.json',recovery)
        folder.mkdir(parents=True,mode=0o700,exist_ok=False)
        write_json(folder/'context.json',context); write_json(folder/'preflight.json',probe)
        (folder/'prompt.txt').write_text(PROMPT)
        with tempfile.TemporaryDirectory(prefix='rh-tabular-proposer-') as tmp:
            session=Path(tmp).resolve(); actor=session/'actor'; control=session/'control'
            actor.mkdir(); control.mkdir(); (actor/'responses').mkdir()
            write_json(actor/'context.json',context); write_json(actor/'schema.json',SCHEMA)
            command=[actor_executable(),'--search','-c','approval_policy="never"','exec','--ignore-user-config','--ephemeral',
                     '--skip-git-repo-check','--sandbox','danger-full-access','--json','--output-schema',str(actor/'schema.json'),
                     '--output-last-message',str(actor/'proposal.json'),PROMPT]
            if sys.platform=='linux': command=linux_actor_command(command,ROOT,control,actor)
            else:
                from .autonomy import actor_profile
                profile=folder/'actor.sb'; profile.write_text(actor_profile(control,actor))
                command=['/usr/bin/sandbox-exec','-f',str(profile),*command]
            version_command=command[:command.index('--search')]+['--version']
            version=subprocess.run(version_command,cwd=actor,capture_output=True,text=True,timeout=15)
            write_json(folder/'cli-preflight.json',{'returncode':version.returncode,'version':version.stdout.strip()})
            if version.returncode: raise ValueError('CLI launch probe failed before any model call; reservation retained')
            if recovery is not None: write_json(folder/'launch-recovery.json',recovery)
            write_json(folder/'isolation-command.json',{'argv':command,'network':'Model/search network allowed; external benchmark exclusion is a task rule, not an egress firewall'})
            process=bounded_process(command,actor,folder/'process',600,quota=16*1024*1024)
            write_json(folder/'process.json',process)
            # Always retain the final actor text even when validation fails. Never import it.
            path=actor/'proposal.json'
            if path.is_file() and not path.is_symlink() and path.stat().st_size<=65536:
                shutil.copyfile(path,folder/'proposal.json')
        outcome={'status':'INCOMPLETE','model_billing_usd':None,'model_session_attempts':1,
                 'final_holdout_scored':False,'new_training_runs':0}
        try:
            if process['error']: raise ValueError('Actor process failed: '+process['error'])
            events=[json.loads(line) for line in (folder/'process/stdout.log').read_text().splitlines()]
            searches={e['item']['id']:e['item'] for e in events if e.get('item',{}).get('type')=='web_search'}
            write_json(folder/'search-records.json',list(searches.values()))
            # This is an audited limit; native tools are not broker-enforced.
            if not 1<=len(searches)<=6: raise ValueError('Expected 1..6 recorded native searches; no retry')
            proposal=read_json(folder/'proposal.json'); gate=validate_proposal(proposal)
            write_json(folder/'feature-review.json',gate)
            papers=[]
            for i,reference in enumerate(proposal['evidence']):
                papers.append(fetch_primary(reference['url'],folder/'papers'/str(i),full=True))
            write_json(folder/'literature.json',papers)
            outcome.update(status='AWAITING_RESEARCH_REVIEW',proposal_sha256=digest(proposal),
                           literature_sha256=digest(papers),searches=len(searches))
        except (OSError,ValueError,KeyError,TypeError) as exc:
            outcome.update(status='INCOMPLETE' if process['error'] else 'REJECTED',reason=str(exc))
        write_json(folder/'result.json',outcome)
        write_json(reservation/('recovery-decision.json' if recovery else 'decision.json'),outcome)
        return outcome
