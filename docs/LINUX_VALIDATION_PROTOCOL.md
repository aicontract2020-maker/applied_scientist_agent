# Linux support validation protocol (before the live cycle)

2026-11-04. Hypothesis: a clean Ubuntu 24.04 Linux environment with Python 3.12,
CPU-only pinned PyTorch and rootless Bubblewrap can complete setup → actual isolation
probes → fresh agent literature/code/registration → exactly one experiment → report,
without mounting the macOS home or repository into the VM or weakening existing gates.

Baseline: v0.9.0 uses macOS Seatbelt only. Primary outcome: all stages pass once in
Linux, including real denial of repository/control reads, response-file edits, outside
writes, candidate network access, host-process visibility, and an unchanged registered
candidate/plan. Runtime or namespace restrictions fail closed before model/experiment
execution. Unit tests are not substitutes for kernel probes or a live research cycle.

Smallest decisive live test: one deterministic fixed-weight SR candidate proposed by
an actual agent from fresh primary literature, one pre-frozen unused Urban100-12 set,
strong existing two-pass reference. Same +.05 dB, original-image bootstrap 95% lower>0,
latency <=2.5, 20-minute session/600-second reference/90-second candidate. All five
previously stopped families remain STOP. No training, tuning, fallback, second candidate,
or retries after a scored negative. A valid negative is an acceptable workflow completion.
Execution-invalid output produces no scientific conclusion; preserve its exact failure.

Uncertainty: one feasibility cycle, no claim of scientific reliability or all-distribution
Linux compatibility. Record kernel, architecture, bwrap/Python/package versions. Validate
macOS regression separately. Prefer non-root Linux account with functioning userns;
restricted HPC/container hosts must be rejected with actionable diagnostics. Root is
only used for VM OS package setup, not to run the research process or bwrap.

Use a private local Linux VM with 4 vCPU/12 GiB RAM/24 GiB virtual disk and no host
folder mounts. Existing own Codex credentials may be transferred directly to a private
VM-only credential directory for validation, never printed/committed; remove afterward.
Colleagues use their own headless login. Actual model bill unknown, local proxy
$1/machine-hour, no cloud GPU; record setup/VM/storage/transfer costs and missing items.

GO: all boundary checks plus one complete cycle → publish scoped Linux support with
setup, diagnostics, evidence and unsupported-host behavior. NO-GO: failed boundary or
incomplete cycle → do not claim full Linux readiness. Synthetic setup failures can be
fixed before any scoring and are recorded explicitly. Do not change scientific criteria.
