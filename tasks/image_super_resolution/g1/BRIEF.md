Prepare exactly one constrained engineering hypothesis for fixed-weight SwinIR-S x2.
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
primary_metric={"name":"BSD100 mean per-image PSNR-Y","direction":"higher","unit":"dB"}.
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
["img_001", "img_002", "img_003", "img_004", "img_005", "img_006", "img_007", "img_008", "img_009", "img_010", "img_011", "img_012", "img_013", "img_014", "img_015", "img_016", "img_017", "img_018", "img_019", "img_020", "img_021", "img_022", "img_023", "img_024", "img_025", "img_026", "img_027", "img_028", "img_029", "img_030", "img_031", "img_032", "img_033", "img_034", "img_035", "img_036", "img_037", "img_038", "img_039", "img_040", "img_041", "img_042", "img_043", "img_044", "img_045", "img_046", "img_047", "img_048", "img_049", "img_050", "img_051", "img_052", "img_053", "img_054", "img_055", "img_056", "img_057", "img_058", "img_059", "img_060", "img_061", "img_062", "img_063", "img_064", "img_065", "img_066", "img_067", "img_068", "img_069", "img_070", "img_071", "img_072", "img_073", "img_074", "img_075", "img_076", "img_077", "img_078", "img_079", "img_080", "img_081", "img_082", "img_083", "img_084", "img_085", "img_086", "img_087", "img_088", "img_089", "img_090", "img_091", "img_092", "img_093", "img_094", "img_095", "img_096", "img_097", "img_098", "img_099", "img_100"]
