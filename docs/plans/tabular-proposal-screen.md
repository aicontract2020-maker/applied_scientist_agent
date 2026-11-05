# C2b: screen one fixed post-hoc calibration proposal

Recorded before calculating any calibration statistic for this route. This turn may prepare and screen a proposal using already-produced validation predictions; it does not authorize final holdout inference/scoring or a second baseline attempt.

Hypothesis: a single additive offset, delta = median(validation target - frozen HGB prediction), reduces mean absolute error on the untouched final holdout by at least 0.05 rings. Reference: qualified fixed HGB from baseline review bf68d98f1c7f3e67d47e39940e36d60f1bca32a4002a3ba75dcfcb27cf3e132f, selected from the prespecified Ridge/HGB comparison. Not a global SOTA claim.

Controls: same fixed training data, HGB parameters and dependencies; no new training/feature selection/ensembles, no scaling or tuning delta, no candidate alternatives after rejection. Use the seed-11 stored prediction table; the historical qualification must establish identical predictions across all three seeds. No final labels are needed for this screen.

Primary prospective metric: baseline MAE minus candidate MAE (rings). Minimum effect: 0.05. Prospective uncertainty: 1,000 paired row bootstrap resamples, seed 20261105, 95% interval lower bound >0; latency ratio <=1.1. This would be conditional on the fixed training sample and an unverified independent-row assumption, not a claim of independent training replication or business value. Final execution requires a separately reviewed complete protocol and task executor.

Screening stop/go, fixed in advance:
- Audit cannot establish valid qualification: fail closed, do not fit delta.
- Delta exactly zero: REJECTED / NOT_RUN (no intervention).
- abs(delta) < 0.05: REJECTED / NOT_RUN. Triangle inequality gives |y-p|-|y-(p+delta)| <= |delta| for every possible target/prediction. Thus even the best possible mean improvement cannot meet the fixed effect threshold. The deterministic bound needs no bootstrap or holdout data.
- Otherwise: AWAITING_RESEARCH_REVIEW, not acceptance, registration or permission to score. Passing this necessary condition does not predict a positive effect.

Evidence: Kuleshov et al., ICML 2018 (https://proceedings.mlr.press/v80/kuleshov18a.html); Marx et al., ICML 2022 (https://proceedings.mlr.press/v162/marx22a.html). Both concern probabilistic calibration, not a guarantee that this additive point correction improves MAE. The single-offset proposal is our inference; its L1 optimum on calibration residuals and the screening bound are elementary mathematical derivations, not claimed novel algorithms. HGB already trains with absolute_error; the only distinct intervention is a validation-fitted constant. Validation was used to choose HGB and is not fresh confirmatory data.

Engineering: add read-only historical baseline audit that does not require current checkout source equality, while execution remains strict. Bind proposal, candidate text, audit and screen results; retain task/data-scoped proposal history so a rejected fixed mechanism cannot be reopened under another output directory. No automatic holdout reservation/consumption at screening, no model charge, no worker training. Software fixtures cover tampering, historical compatibility, no-op/impossible/plausible cases and repeated-route rejection.
