# A1: Airfoil baseline qualification review

Status: **CONTINUE / measurement valid** after explicit user approval on 2026-11-06. One execution, 15 fixed fits, validation predictions/scoring only; read-only audit passed. See [the result report](REPORT.md), [all aggregate results](result-summary.json) and [audit](audit.json).

Exact frozen review SHA-256: `ac8f7df93f688a9621038c881fa5ab312e4bc5790d7f59c134547dbbd81e2dd5`.

Local full review: `reviews/airfoil-baseline-020/`. Public files contain metadata, protocol and source/data digests only; no rows or targets are published here.

Read [the complete decision and scope](../../../docs/AIRFOIL_BASELINE_REVIEW.md), [frozen recipe](REVIEW.md), and [content manifest](review-manifest.json). The [intake rule](intake-rule.json) was written before download. No alternate split was tried.

Software evidence: 169 tests pass in the full research environment; base Python runs 169 with 9 dependency/runtime skips. [macOS synthetic isolation](macos-software-check.json) checks 15 fixed fits, audit, tampering and repeated/copied attempt rejection. Linux CI runs the same synthetic integration; it never downloads or fits the real Airfoil dataset.

The approval covered one 15-fit baseline qualification against validation only and has now been consumed. Extra Trees qualified; mean condition MAE 1.359248 dB, mean gain over median 4.155519 dB, grouped 99% interval [3.486052, 4.782259] dB. Do not rerun the qualification in another checkout or machine. The original frozen review remains unchanged as historical evidence.

The 285 final held-out observations across 21 condition groups remain unused. Only a separate candidate protocol may now be drafted; candidate execution/holdout scoring was not approved. The existing Abalone T1/T2 STOP records remain closed. This is not a human-efficiency comparison.
