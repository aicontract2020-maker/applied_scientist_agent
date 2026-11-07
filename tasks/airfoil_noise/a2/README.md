# A2: single Strouhal feature — awaiting research review

2026-11-07. Status **AWAITING_RESEARCH_REVIEW / NOT_RUN**. Real candidate training, prediction, scoring and final-holdout exposure have not started.

Frozen SHA-256: `de0f852d0bfb7a832604aef4f2fb5c82944177bda4a354deadb573ed726ea5de`. Local full review: `reviews/airfoil-a2-strouhal-021-final/`.

Read [the design and limits](../../../docs/AIRFOIL_CANDIDATE_REVIEW.md), [frozen proposal](proposal.json), [complete frozen review](REVIEW.md) and [manifest](review-manifest.json). A1 exact evidence remains unchanged and passes historical read-only audit.

One appended coordinate: frequency * suction-side displacement thickness / velocity. Same qualified Extra Trees, same A1 training set, three paired seeds and six fits. All seed gains >=0.2 dB condition-macro MAE, grouped 95% bootstrap lower >0 and prediction latency ratio <=1.1 are required. Failure closes the route; no tuning, replacement or retry.

Approval would authorize one use of all 285 final held-out rows in 21 condition groups; no A2 approval or reservation exists yet. A1 approval does not authorize A2.

Software validation: 177 tests pass in the full research environment; base Python runs 177 with 9 dependency/runtime skips. [macOS kernel integration](macos-software-check.json) uses synthetic data only, verifies changed predictions, reproduction, auditing, tampering and repeat/copy rejection. Linux CI runs the same synthetic check. These are not scientific findings.

The current session agent retrieved and checked the NASA formula and proposed the intervention; no separate model actor was launched. Only this closed mechanism is supported, not arbitrary Airfoil autonomous research. Original data, labels, historical predictions, approval text and downloaded literature remain local.
