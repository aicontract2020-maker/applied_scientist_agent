# A2: single Strouhal feature — valid CONTINUE

2026-11-07. User approved the frozen review; one macOS Seatbelt execution completed with six fits and a valid **CONTINUE**. Read the [result and limits](REPORT.md). All 285 final held-out rows in 21 conditions are now consumed; no retry or reuse is permitted.

Frozen SHA-256: `de0f852d0bfb7a832604aef4f2fb5c82944176bda4a354deadb573ed726ea5de`. Local full review: `reviews/airfoil-a2-strouhal-021-final/`. This corrects a one-character index typo; the formal review, public manifest and local frozen packet were already consistent and remain unchanged.

Read [the design and limits](../../../docs/AIRFOIL_CANDIDATE_REVIEW.md), [frozen proposal](proposal.json), [complete frozen review](REVIEW.md) and [manifest](review-manifest.json). A1 exact evidence remains unchanged and passes historical read-only audit.

One appended coordinate: frequency * suction-side displacement thickness / velocity. Same qualified Extra Trees, same A1 training set, three paired seeds and six fits. All seed gains >=0.2 dB condition-macro MAE, grouped 95% bootstrap lower >0 and prediction latency ratio <=1.1 are required. Failure closes the route; no tuning, replacement or retry.

Separate A2 approval authorized one use of the final holdout. Mean MAE gain 0.253169 dB, seed gain standard deviation 0.012197 dB, grouped 95% interval [0.124917, 0.389737], latency ratio 1.098316. All gates passed; only a separately reviewed external replication may follow. The [published consumption record](../trial-history.json) and local reservation prevent repeat use. Historical REVIEW.md and manifest retain their pre-approval status as frozen artifacts, not current status.

Software validation: 177 tests pass in the full research environment; base Python runs 177 with 9 dependency/runtime skips. [macOS kernel integration](macos-software-check.json) uses synthetic data only, verifies changed predictions, reproduction, auditing, tampering and repeat/copy rejection. Linux CI runs the same synthetic check. These are not scientific findings.

The current session agent retrieved and checked the NASA formula and proposed the intervention; no separate model actor was launched. Only this closed mechanism is supported, not arbitrary Airfoil autonomous research. Original data, labels, historical predictions, approval text and downloaded literature remain local.
