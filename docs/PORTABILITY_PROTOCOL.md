# Portability validation, declared before the live cycle

2026-11-04. Hypothesis: a fresh repository checkout on this supported macOS host,
using its own newly installed Python environment and downloaded pinned assets, can
complete setup → doctor → new-study preparation → real agent literature search →
agent code → preregistration → one experiment → STOP/CONTINUE → portable report,
without copying the original checkout's environment, asset folders or candidate code.

Baseline: the original host checkout required manual environment/assets/preparation
and host-specific run instructions. Primary metric: binary complete workflow in one
fresh-checkout attempt after software-only setup validity checks. Minimum meaningful
success: every stage works, the candidate/plan remain unchanged, and the agent invokes
exactly one registered experiment. Scientific success is separate: gain >=.05 dB,
95% paired original-image bootstrap lower >0, latency ratio <=2.5. Templates freeze
12 previously unused image IDs before search and exclude all four STOP routes.

Controls: same pinned upstream commits/checkpoint, CPU float32 four threads, official
PSNR-Y and crop2; no copied local assets, private developer paths or model plan; fresh
venv, live primary retrieval; same user-provided Codex login and installed macOS tools.
This is a same-host clean-checkout test, not a second person's hardware/OS test.

Uncertainty/replication: one deterministic integration cycle, not a reliability estimate.
Synthetic probes, unit tests, downloading and installation are software/setup validity
checks, not scientific experiments. Record setup failures and fixes explicitly. Once
real image scoring happens, no candidate retry/tuning, even if negative. A valid negative
still satisfies workflow feasibility if all stages finish and the agent reports STOP.
A failed or incomplete cycle stays failed; no automatic new candidate. Genuine new
hypotheses require new external evidence and a new protocol; exhausted images stop.

Limits: one live agent session <=1200s, reference <=600s, candidate <=90s, <=3 synthetic
checks, <=6 search calls/primary retrievals; actual model bill unknown, local proxy
$1/machine-hour. Charge setup downloads/disk/time separately from session cost; neither
proxy nor wall limits are a model-service dollar cap. No training, tuning or cloud GPU.

STOP/GO: all workflow checks pass → publish portability support scoped to macOS and
this tested setup; any failed stage → do not claim full handoff readiness. Preserve
negative research findings and disclose portability limits and residual security scope.
