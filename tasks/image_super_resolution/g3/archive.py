"""Archive a completed cycle without rerunning inference or selecting candidates."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
RUN=ROOT/'runs/autonomous-g3'
EVIDENCE=HERE/'evidence';EVIDENCE.mkdir(exist_ok=True)
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p: json.loads(p.read_text())
write=lambda p,v:p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
session=load(RUN/'session.json');control=Path(session['control_directory'])
for name in ['result.json','registered.json','observations.json','ledger.jsonl','session.json','search-records.json','candidate-resources.json','actor.sb']:
    shutil.copyfile(RUN/name,EVIDENCE/name)
for name in ['reference-timings.json']:
    shutil.copyfile(control/name,EVIDENCE/name)
for name in ['reference-logs','candidate-output','smoke-output-1']:
    shutil.copytree(control/name,EVIDENCE/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns("*.npy"))
write(EVIDENCE/'candidate-array-hashes.json',{p.name:sha(p) for p in (control/'candidate-output').glob('*.npy')})
shutil.copyfile(RUN/'candidate.py',HERE/'candidate.py')
shutil.copyfile(RUN/'agent-research.json',HERE/'research.json')
shutil.copyfile(RUN/'agent-REPORT.md',HERE/'AGENT_REPORT.md')
# Preserve source metadata and hashes without republishing third-party full texts.
library=load(RUN/'library.json')
for paper in library:
    for key in ['abstract','full_text']:paper.pop(key,None)
write(EVIDENCE/'primary-sources.json',library)
events=[json.loads(s) for s in (RUN/'agent-events.jsonl').read_text().splitlines()]
commands=[v['item'] for v in events if v.get('type')=='item.completed' and v.get('item',{}).get('type')=='command_execution']
provenance=[{k:i.get(k) for k in ['id','command','exit_code','status']} for i in commands]
write(EVIDENCE/'command-provenance.json',provenance)
usage=[v['usage'] for v in events if v.get('type')=='turn.completed']
ledger=[json.loads(s) for s in (RUN/'ledger.jsonl').read_text().splitlines()]
operations=[v['operation'] for v in ledger if v['event']=='AGENT_REQUEST']
registered=load(RUN/'registered.json');result=load(RUN/'result.json')
assert sha(HERE/'candidate.py')==registered['candidate_sha256']==sha(RUN/'agent-candidate.py')
assert operations.count('run')==operations.count('register')==1
assert result['measurement_valid'] and result['status']=='STOP'
assert len(load(RUN/'search-records.json'))==1 and len(library)==2
assert 'STOP' in (HERE/'AGENT_REPORT.md').read_text()
locked=load(HERE/'inputs.lock.json')['files']
assert all(sha(ROOT/p)==h for p,h in locked.items())
source_dir=EVIDENCE/'executed-sources';source_dir.mkdir(exist_ok=True)
for p in locked:
    if p.startswith('research_harness/'):
        shutil.copyfile(ROOT/p,source_dir/Path(p).name)
audit={'workflow_completed':True,'scientific_decision':'STOP','candidate_unchanged':True,'frozen_inputs_verified':True,'operations':operations,'live_search_calls':1,'search_queries':2,'primary_reads_attempted':4,'primary_reads_succeeded':2,'full_text_reads_succeeded':1,'full_text_was_truncated':True,'valid_experiments':1,'no_post_result_tuning':True,'public_benchmark_network_access_observed':False,'network_audit_scope':'Recorded queries and shell commands; actor egress is not domain-hard-isolated','raw_events_sha256':sha(RUN/'agent-events.jsonl'),'raw_events_local_path':str(RUN/'agent-events.jsonl'),'raw_library_sha256':sha(RUN/'library.json'),'raw_library_local_path':str(RUN/'library.json')}
write(EVIDENCE/'workflow-audit.json',audit)
paths=[ROOT/'.venv-sr',ROOT/'assets',ROOT/'external',ROOT/'.cache',control.parent]
bytes_total=sum(p.stat().st_size for parent in paths for p in parent.rglob('*') if p.is_file() and not p.is_symlink())
write(EVIDENCE/'resource-accounting.json',{'session_wall_seconds':session['total_wall_seconds'],'session_local_proxy_usd':session['local_proxy_usd'],'experiment_wall_seconds_subset':result['experiment_wall_seconds'],'usage':usage,'actual_model_id':None,'actual_model_billing_usd':None,'shared_environment_assets_and_session_bytes':bytes_total,'coarse_full_session_residency_byte_hours':bytes_total*session['total_wall_seconds']/3600,'candidate_peak_rss_bytes':load(RUN/'candidate-resources.json')['peak_rss_bytes'],'reference_peak_rss_bytes':None,'successful_primary_download_bytes':sum(p['download_bytes'] for p in library),'failed_pdf_downloads':2,'failed_pdf_read_cap_bytes_each':20971520,'failed_download_actual_bytes':'cap+1 bytes read before rejection, plus unmetered HTTP overhead and abstract HTML; files not retained','data_download_egress_bytes':None,'unpriced':['setup and audit time','data preparation transfer','electricity/depreciation','long-term retention','model invoice']})
print(json.dumps({'audit':audit,'usage':usage,'disk_bytes':bytes_total},indent=2))
