"""Operator audit and binding of a model proposal to reviewed local code.

Uses existing user authorization to continue this bounded local pilot. This does
not fabricate a human approval record, and the model cannot supply execution code.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from research_harness.core import digest
from research_harness.planning import validate_plan

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
proposal_dir = ROOT / 'proposals/swinir-g1-p1'
envelope = json.loads((proposal_dir / 'proposal.json').read_text())
if digest(envelope['content']) != envelope['sha256']:
    raise ValueError('Planner proposal changed')
plan = envelope['content']['plan']
validate_plan(plan)
if plan['status'] != 'ready_for_review':
    raise ValueError('Planner did not provide a ready plan')
p = plan['protocol']
data = json.loads((HERE / 'data.lock.json').read_text())
expected = {'id': 'swinir-g1-inference', 'design': 'paired_observations', 'replicates': 1, 'seeds': [0],
            'observation_ids': data['holdout_ids'], 'minimum_effect': 0.05, 'max_latency_ratio': 2.5,
            'bootstrap': {'resamples': 10000, 'seed': 20261103, 'confidence': 0.95}, 'budget_usd': 0.2,
            'primary_metric': {'name': 'BSD100 mean per-image PSNR-Y', 'direction': 'higher', 'unit': 'dB'},
            'intervention': {'kind': 'horizontal_flip_ensemble', 'step_size': 0},
            'validity_checks': ['All 100 frozen BSD100 image pairs evaluated', 'Frozen inputs and metric code unchanged', 'No training or tuning']}
for name, value in expected.items():
    if p[name] != value:
        raise ValueError(f'Proposal violated frozen request constraint: {name}')
events = [json.loads(line) for line in (proposal_dir / 'events.jsonl').read_text().splitlines()]
# Reject planner tool use: response must come from supplied context alone.
for event in events:
    kind = event.get('item', {}).get('type')
    if kind not in (None, 'agent_message', 'reasoning', 'error'):
        raise ValueError(f'Planner used an unexpected tool/item type: {kind}')
usage = [e['usage'] for e in events if e.get('type') == 'turn.completed']
if len(usage) != 1:
    raise ValueError('Expected one completed planner turn')
checkpoint = 'assets/swinir/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth'
inputs = dict(data['inputs'])
paths = [checkpoint, 'external/SwinIR/models/network_swinir.py', 'external/SwinIR/utils/util_calculate_psnr_ssim.py',
         'tasks/image_super_resolution/requirements.lock.txt', 'tasks/image_super_resolution/g1/worker.py',
         'tasks/image_super_resolution/g1/evaluate.py', 'tasks/image_super_resolution/g1/data.lock.json',
         'research_harness/observations.py', 'research_harness/core.py']
for name in paths:
    inputs[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
# Direct byte-identity overlap check with previously scored Set5 images.
g0 = json.loads((ROOT / 'tasks/image_super_resolution/assets.lock.json').read_text())
seen = {sha for path, sha in g0['inputs'].items() if '/HR/' in path}
if seen & {sha for path, sha in data['inputs'].items() if '/BSD100/' in path and path.endswith('_HR.png')}:
    raise ValueError('Holdout contains a byte-identical previously scored Set5 image')
setup_bytes = sum(x.stat().st_size for name in ('.venv-sr', '.cache', 'external', 'assets')
                  for x in (ROOT / name).rglob('*') if x.is_file() and not x.is_symlink())
manifest = {'inputs': inputs, 'checkpoint': checkpoint, 'setup_disk_bytes': setup_bytes,
            'planner_proposal_sha256': envelope['sha256'], 'data_revision': data['revision']}
with (HERE / 'execution.lock.json').open('x') as f:
    json.dump(manifest, f, indent=2)
inputs['tasks/image_super_resolution/g1/execution.lock.json'] = hashlib.sha256((HERE / 'execution.lock.json').read_bytes()).hexdigest()
p['execution'] = {'cwd': str(ROOT), 'command': [str(ROOT / '.venv-sr/bin/python'), 'tasks/image_super_resolution/g1/worker.py', '--seed', '{seed}', '--output', '{output}'],
                  'timeout_seconds': 600, 'compute_usd_per_hour': 1,
                  'fixed_costs': {'data_usd': 0, 'storage_usd': 0, 'tuning_usd': 0}, 'inputs': inputs}
p['cost_assumptions'] = {'compute_proxy': 'USD 1 per local allocated machine-hour, not actual billing',
                         'model_usage': usage[0], 'planner_billing_usd': None,
                         'unpriced': ['Planner USD cost', 'Setup CPU time', 'Electricity/depreciation', 'Storage retention after run'],
                         'setup_disk_bytes': setup_bytes}
with (HERE / 'protocol.json').open('x') as f:
    json.dump(p, f, indent=2)
# Preserve actual model proposal, transport metadata and usage without claiming human approval.
for source, target in [('response.json', 'planner-response.json'), ('provider.json', 'planner-provider.json')]:
    (HERE / target).write_bytes((proposal_dir / source).read_bytes())
audit = {'status': 'PASS_OPERATOR_CONSTRAINT_CHECK', 'proposal_sha256': envelope['sha256'],
         'request_sha256': hashlib.sha256((HERE / 'planner-request.json').read_bytes()).hexdigest(),
         'usage': usage[0], 'billing_usd': None,
         'limitations': 'One request from a two-option supplied shortlist; not open-ended invention; no human approval record created.',
         'registration_basis': 'Existing user instruction to continue the bounded local pilot, with operator-audited trusted code.'}
with (HERE / 'operator-audit.json').open('x') as f:
    json.dump(audit, f, indent=2)
print(json.dumps(audit, indent=2))
