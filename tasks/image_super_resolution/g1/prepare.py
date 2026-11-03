"""Freeze benchmark identity and planning context. Does not run model inference."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
source = ROOT / 'external/SelfExSR'
revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
images = []
inputs = {}
for dataset, count in [('BSD100', 100), ('Set14', 14)]:
    folder = source / f'data/{dataset}/image_SRF_2'
    paths = sorted(folder.glob('*_HR.png'))
    if len(paths) != count:
        raise ValueError(f'{dataset}: expected {count} HR images')
    for hr in paths:
        lr = hr.with_name(hr.name.replace('_HR.png', '_LR.png'))
        for path in (hr, lr):
            inputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        if dataset == 'BSD100':
            images.append(hr.name.removesuffix('_SRF_2_HR.png'))
manifest = {'repository': 'https://github.com/jbhuang0604/SelfExSR', 'revision': revision,
            'holdout_ids': images, 'development_dataset': 'Set14 (unused so far)', 'inputs': inputs,
            'source_note': 'EDSR server failed TLS handshake; original benchmark-author repository used instead. No scores or existing method outputs inspected.'}
with (HERE / 'data.lock.json').open('x') as f:
    json.dump(manifest, f, indent=2)
brief = f'''Prepare exactly one constrained engineering hypothesis for fixed-weight SwinIR-S x2.
This is our first real planner invocation. Do not claim novel science or general research competence.
G0 reproduced Set5 PSNR-Y 38.1394098 versus reference 38.14. No candidate method measured.

Strongest eligible reproduced baseline: fixed official SwinIR-S x2 DIV2K checkpoint,
source revision 6545850fbf8df298df73d81f3e8cba638787c8bd, CPU float32, 4 threads,
full image inference, no ensemble or tiling. We do not claim this is global SOTA.
Constraints: no training, no new weights, no architecture changes, no tuning or sweeps.
Use one of two audited, pre-existing engineering interventions:
- horizontal_flip_ensemble: arithmetic mean of f(x) and inverse_flip(f(horizontal_flip(x)))
  in float32 before clamping/rounding. Exactly two forwards; step_size must be 0.
- single_step_back_projection: y=f(x); y'=y+U(x-D(y)), exactly once, step_size=1;
  D is OpenCV INTER_CUBIC resize to original LR dimensions; U is INTER_CUBIC to HR.
  This is only an approximate degradation operator; discuss its mismatch risk.
Do not present either known method as a new scientific discovery. Choose one, not both.
Source context: SwinIR official repo supplies the model/metrics; EDSR official repo
https://github.com/sanghyun-son/EDSR-PyTorch describes self-ensemble (+) inference.
https://github.com/jbhuang0604/SelfExSR supplies the standard bicubic LR/HR benchmark pairs.
These sources were inspected by the orchestrator; do not invent a citation or fetch tools.

Data: all 100 original BSD100 x2 image pairs, downloaded and hashed BEFORE planning.
The entire list below is fixed; no selecting cases, cropping for scores, filtering or shuffling.
No measurements from BSD100 have been obtained. Set14 is available for future work but
this experiment is a one-shot holdout evaluation; no development measurements or model selection.
Public datasets are not guaranteed unseen to the LLM and are not access-isolated.

Required ID: swinir-g1-inference. Required design: paired_observations.
replicates=1, seeds=[0] (an execution ID, never independent training seeds).
primary_metric={{"name":"BSD100 mean per-image PSNR-Y","direction":"higher","unit":"dB"}}.
minimum_effect=0.05 dB. This is a pilot adoption threshold selected BEFORE results,
not a validated customer-value threshold. Bootstrap resamples=10000, seed=20261103,
confidence=0.95. Resample ORIGINAL images, never patches or inference runs.
max_latency_ratio=2.5 (aggregate candidate time / baseline time).
The runtime uses one unscored small warmup for each arm, counted in compute time,
and alternating arm order across the frozen image list. Timing is descriptive, not a
multi-run production latency benchmark. No additional model-based warmup tuning.
GO only if mean PSNR gain >=0.05, lower bootstrap CI >0, and latency ratio <=2.5.
Otherwise STOP the chosen intervention without adjusting parameters, metric, threshold,
sampling, number of trials or architecture. Operational/validity failure is not a negative
scientific result and requires a specifically recorded correction before a new protocol.

Budget: one local CPU execution, timeout=600 seconds, proxy USD 1/machine-hour,
experiment proxy budget USD 0.20. No cloud compute or paid data. Storage byte-hours,
peak memory and inference latency must be reported. Proxy costs exclude unmetered setup,
electricity, depreciation, and subsequent retention; list these unknowns explicitly.
Planner allowance: exactly ONE model request, 120-second timeout; account usage and
USD amount may be unknown. Do not fabricate a dollar cost or conflate it with experiment costs.
These complete constraints are supplied by the orchestrator, not invented user consent.
No execution configuration may appear in your response.

Required validity_checks (exact text):
["All 100 frozen BSD100 image pairs evaluated", "Frozen inputs and metric code unchanged", "No training or tuning"]

Frozen observation_ids:
{json.dumps(images)}
'''
(HERE / 'BRIEF.md').write_text(brief)
request_protocol = {'id': 'planner-p1', 'hypothesis': 'A single bounded planner request produces a schema-valid, constraint-compliant, ready-for-review protocol from this complete brief.',
 'baseline': 'Human-authored frozen brief and deterministic schema/constraint oracle; no claim of outperforming human research.',
 'controls': ['same brief and schema', 'no tools or experiments', 'one request only'],
 'metric': 'All syntax and frozen-constraint checks pass (binary)', 'minimum_effect': 'Pass=1; otherwise stop planning route and preserve failure',
 'replication': 'One integration attempt, not a statistical model-quality benchmark',
 'uncertainty': 'No generalization or reliability claim from one response',
 'budget': {'requests': 1, 'timeout_seconds': 120, 'account_usd': None},
 'outcomes': {'pass': 'Inspect proposal and implement only the frozen intervention before registering G1',
              'fail': 'Stop; preserve output, classify missing context or protocol violation; no candidate experiment',
              'transport_invalid': 'Record exact failure; repair transport only under a newly logged request protocol'}}
with (HERE / 'planner-request.json').open('x') as f:
    json.dump(request_protocol, f, indent=2)
print('Frozen 100 BSD100 observation identities, asset hashes, brief, and one-request planning protocol.')
