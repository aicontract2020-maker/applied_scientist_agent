# G6: next autonomous research cycle on Linux (before any new search/scoring)

2026-11-04 America/Toronto. User authorized the agent to find its own new primary
literature, propose a mechanism distinct from all seven STOP routes, and run one
preregistered experiment on Linux. No paper list, algorithm menu or candidate code
will be supplied by the operator. Reuse the verified rootless Bubblewrap runtime;
fail closed if any file/network/PID/auth/asset preflight check fails.

Before the agent starts, `research --id linux-g6-20261104` freezes 12 unused Urban100
x2 image IDs by study-id/filename hash, excluding all historical and VM-local reserved
IDs. Same fixed SwinIR-S weights, CPU float32/four threads, official quantization,
PSNR-Y/crop2; comparison is the stronger existing fixed two-forward flip reference,
not bicubic or a claim of global SOTA. Candidate receives plain one-forward SR only.

The agent must actually search, read >=2 primary papers (>=1 full-text extraction;
truncation declared), cite >=1 previously unused source, preregister a falsifiable
hypothesis and causal rationale, controls, all constants/formulae, baseline, metric,
uncertainty, costs and decision meanings before requesting its ONE real experiment.

Adopt/CONTINUE only if mean paired PSNR-Y gain >=0.05 dB, original-image paired
bootstrap 95% lower >0 (10,000 resamples, seed20261103), latency ratio <=2.5.
Valid below-threshold result -> STOP this route, no parameter/kernel/threshold/grid/
objective/data changes, ablation, second candidate or retry. Operational failure ->
no scientific conclusion, preserve exact failure; no automatic retry. No defensible
new hypothesis -> report inability and stop without inventing evidence.

Prior STOP families: prediction ensembles; LR/SR residual backprojection; weak
high-frequency shrinkage; global luminance contrast expansion; luminance-preserving
gamut compression; constant 2x2 phase-locked luminance offset correction; BT.601-preserving RGB lattice selection. Old papers
alone and cosmetic rewording do not reopen them. Template/local history remain binding.

Deterministic inference, no stochastic training or seed-shopping. Effect/std and image
sampling CI are reported, not a generalization/training-reliability claim. Single study
changes adoption/abandonment of exactly the frozen candidate; comparisons changing
forward count do not isolate postprocessor causality without a preregistered ablation.

Limits unchanged: session1200s, reference600s, candidate90s, <=3 synthetic checks,
<=6 literature calls/retrievals, one experiment, output256MiB. Local proxy $1/machine-hour,
actual model id/billing unknown until observable. Preserve all usage, setup/VM/storage/
latency costs and unknowns. No training, sweeps, extra weights or cloud GPU.

Workflow success is separately search -> evidence -> agent proposal/code -> registration
-> one valid evaluation -> faithful STOP/CONTINUE report. Scientific negative is a final
output. If complete, archive evidence and decision; do not automatically start a new route.

G5 is final STOP (-0.100211 dB); no change to its luminance weights, lattice neighborhood, softness or adaptive logic can reopen it. Previously used Urban100 images total 60; the next 12 must be selected from the remaining unused/reservation-free IDs before search. No criterion changes after viewing results. All three conjunctive gates must appear in the agent report, including bootstrap lower >0; G5 reporting omitted that gate in a summary, while the evaluator enforced it.
