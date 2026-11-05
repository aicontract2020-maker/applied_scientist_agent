# Task contracts: first extraction

Scope: separate task identity, evaluation and capability dispatch from research orchestration without widening execution permissions. Preserve existing SR thresholds, history, isolation, preregistration and single-attempt behavior.

- Closed built-in registry: SR autonomous task and deterministic tabular regression evaluation-only task. Bind new protocols/policies to a version and contract digest. Never load a module/command supplied by a task document.
- Move current SR image scoring into its task evaluator; share the existing effect/interval/latency decision gate between execution, generic Workspace and read-only audit. Keep historical result formats and hashes untouched.
- Add a regression evaluator for fixed target/prediction records: exact frozen identities, finite values, positive measured latencies and content-bound target/baseline/candidate inputs. Use lower-is-better MAE and independent-row paired bootstrap; no training or time-series claims.
- Register before evaluation in the synthetic regression demonstration. Reuse Workspace ledger and STOP behavior. No model calls, new empirical claims, automatic candidate execution or automatic scientific approval.
- Reject an evaluation-only task at the autonomous entry point before environment probes, locks, data reservation or model calls. Existing SR remains the default.

Acceptance: software tests for changed bindings/inputs, unknown tasks, missing/duplicate rows, non-finite values, all three decision gates, terminal STOP, non-execution of task text and legacy SR compatibility; synthetic second-domain end-to-end demo. Historical G7 read-only audit must still pass. Run full software suite and Linux CI.

This is the first step toward task portability, not a complete second autonomous scientist. Next gate: choose a real independent-row regression dataset and baseline, review rights/data splits/cost limits, preregister a baseline reproduction, implement isolated execution plus intervention review and task-scoped memory/audit before any live agent experiment. Do not route regression through the trusted unsandboxed runner as a substitute.
