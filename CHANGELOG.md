# Changelog

## 0.27.0

- Record C8 user acceptance. Add conservative Airfoil baseline/candidate memory from published A1/A2 metadata, local reservations and imported state. Carry incomplete reservations without freeing data, keep INVALID separate from scientific STOP, reject conflicting bindings and terminal decisions.
- Extend unified handoff to v2 with Airfoil memory as a third required component. All components publish atomically; v1 remains readable with explicit missing Airfoil coverage. Add top-level `handoff` while retaining the `tabular handoff` alias. No SR/proposer reservation migration or private evidence transfer.
- Enforce retained Airfoil consumption and stopped mechanisms during preparation, approval and preflight, including the post-isolation recheck. Preserve scientific recipes, evaluators, task bindings and historical artifacts; synthetic software validation only, no new research experiment.

## 0.26.0

- Record C7 user acceptance. Add `tabular handoff` status/export/verify/import for one fixed-format snapshot containing tabular exclusion memory and all local data-use blocks. Private full evidence remains separate; Airfoil/SR reservations are outside this format.
- Validate both components and their local unions before a single atomic, no-overwrite publication. Legacy readers consume both components from the same retained packet; repeated import is idempotent, older snapshots cannot clear blocks or downgrade terminal decisions, and malformed state fails closed.
- Preserve legacy component commands, isolation, preregistration, scientific recipes and STOP rules. Add synthetic failure/compatibility checks and actual isolated synthetic receiver verification; no new research experiment or model call.

## 0.25.0

- Record C6 user acceptance. Add local dataset-use blocks keyed by exact dataset id/version/source, independent of qualification packet, intended use or baseline/candidate adapter. Preserve historical evidence and scientific decisions; a data pause is not scientific STOP.
- Check blocks during baseline/candidate preparation, approval and execution, and before tabular proposal work. Recheck after isolation probes, before reservation or worker/actor launch. Existing scientific recipes, evaluator thresholds and isolation remain unchanged.
- Add `data-blocks` status/add/export/import with exact-hash human recording, strict bounded envelopes, atomic local writes and additive idempotent handoff. Corrupt state fails closed; no unblock, permission inference, automatic revocation discovery or cross-checkout synchronization. Software fixtures only; no new research experiment.

## 0.24.0

- Record C5 user acceptance; require separately accepted candidate-scoped data qualification for the existing Abalone and Airfoil candidate stages. Bind evidence and use to the complete proposal, recipe, exact audited baseline and all partitions; baseline qualification cannot authorize candidate use.
- Add read-only candidate preflight commands and recheck exact approval, review and exclusion memory after isolation probes. Legacy real trials remain audit-only without admission; private evidence handoff retains embedded qualification. Keep all scientific gates and original isolation unchanged.
- Propagate qualification through the unified tabular proposal workflow and direct proposer before actor calls or research output/reservations; reject runtime qualification overrides during execution. Add 14 synthetic tests and admitted synthetic candidate isolation checks. No new real research experiment or model call.

## 0.23.0

- Record user acceptance of C4 and require accepted metadata qualification plus explicit intended use before either public baseline prepare command reads real data. Embed the private evidence/decision snapshot and bind it to adapter identity, dataset revision, frozen partitions and the unchanged baseline recipe.
- Enforce admission on new baseline approval and execution; add read-only `airfoil preflight` / `tabular preflight`. Recheck the entire review and approval after environment/isolation probes, before reserving or starting a worker. Legacy real-data bundles remain readable for historical audits but cannot bypass admission for new execution.
- Add 11 synthetic integration tests and exercise both existing isolated baseline workers with admitted synthetic records. No new real research experiment, model call, data source or generic executor; all scientific thresholds and historical artifacts remain unchanged.

## 0.22.0

- Add offline `data-review` template, prepare, inspect and exact-hash human decision commands. Require all eight metadata criteria and referenced evidence; unresolved cases block and incompatible cases stop data qualification. Acceptance permits protocol design only, never execution.
- Embed bounded, checksum-verified metadata text for private offline handoff. Reject changed evidence, ambiguous JSON, missing criteria, unsafe paths and overwrite attempts; bind a single local decision to the complete packet.
- Add synthetic workflow, 15 regression tests and Python 3.10/3.12 macOS/Linux CI coverage for the new module. Existing runners, task bindings, scientific gates and historical research artifacts are unchanged. No new research experiment was run.

## 0.21.0

- After explicit user authorization, send the reviewed metadata/permission inquiry to the verified Delft dataset co-creator and record the reply-assessment boundary. Keep private mail receipts local, preserve the pre-send review snapshot, and leave all external experiments unregistered and unrun.

- Screen independent sources for A2-R1, pin a metadata-only Delft inventory, and document a conditional direct-transfer protocol. Keep execution blocked on measurement compatibility, acoustic validity, eligible groups and intended-use permission; no external labels, fits, predictions or messages. Original A2 evidence and protocol remain unchanged.

- Execute the separately approved frozen A2 once on macOS: valid CONTINUE, mean gain 0.253169 dB, grouped 95% interval [0.124917, 0.389737], latency ratio 1.098316. Publish decision and consumed-holdout memory; all 285 final rows are unavailable for reuse. External replication requires a separate review. Correct the A2 index hash typo; formal frozen artifacts and implementation are unchanged.

- Prepare the single A2 suction-side Strouhal feature hypothesis from a checked NASA source and the pinned Extra Trees implementation. No real candidate fit, prediction or holdout score.
- Add fixed-intervention review, exact approval, six paired isolated fits, historical A1 validation reproduction, condition-level effect/uncertainty/latency gates, conservative reservations and read-only audit.
- Validate positive/negative gates and actual macOS/Linux synthetic boundaries; preserve A1 and all previously stopped routes. Generic autonomous Airfoil research and human-efficiency evaluation remain outside this release.

## 0.20.0

- 2026-11-06: execute explicitly approved A1 once on macOS Seatbelt. Extra Trees qualifies with condition MAE 1.359248 dB and mean gain 4.155519 dB versus median; valid CONTINUE and read-only audit pass. Preserve the reservation; no tuning or second execution. All 285 final holdout observations remain unscored; only a separate candidate protocol may be drafted.
- Add a pinned public Airfoil task with target-blind condition-group partitions, macro condition MAE, grouped uncertainty and a fixed five-model/three-seed baseline qualification.
- Add exact review/approval, single-attempt dataset reservations, isolated trusted worker and read-only audit; preserve existing Abalone/SR protocols and stopped routes.
- Validate new boundaries with synthetic tests and actual OS-isolated fits. Prepare the real A1 review without real training, prediction or scoring. No human-efficiency or commercial-value claim.

## 0.19.0

- 2026-11-06: record C3 handoff acceptance as user-confirmed PASS for commit bf832f6; recipient logs and timing/cost records were not supplied. Prepare the D1 research-value comparison design; no new empirical execution is authorized or started.
- Add conservative published/local/imported tabular exclusions with row fingerprints and stopped feature structure checks; matching records block renamed studies, reordered rows, repartitioning and numeric retuning.
- Add private allowlisted evidence export, exact Python 3.12 offline verification and review-only unpacking. Packets contain data/labels/paper/approval text; no private packet is published.
- Add explicit propose/execute stages under the unified research CLI while preserving immutable v1 evaluation bindings and exact human approval.
- Verify completed T2 evidence read-only on macOS and Linux without model calls, training or inference; preserve all original artifacts and its STOP.
- Prepare a synthetic handoff fixture and an independent-colleague acceptance plan. New datasets and general autonomous research remain outside the supported pilot.

## 0.18.0

- 2026-11-06: after explicit user approval, execute frozen T2 once and retain a valid STOP: MAE gain 0.0092071 <0.05, 95% interval crosses zero, latency ratio 1.4498 >1.1. All 804 final holdout rows are consumed; no retry/tuning. Pinned Python 3.12 read-only audit passes.

- Add an isolated tabular literature/proposal actor with no dataset rows, training or score operation.
- Interpret a closed arithmetic feature language instead of importing candidate Python; reject obvious constant, duplicate and single-column monotone features using synthetic probes.
- Add content-bound candidate review/approval, six fixed paired HGB fits, historical validation reproduction, private-label controller scoring, shared effect/bootstrap/latency gates and conservative partition reservations.
- Add read-only completed-trial auditing and actual macOS/Linux synthetic integration checks; these are not evidence of research performance.
- Preserve the pre-agent Node startup failure and a separate, narrowly checked native-launch recovery. No credential transfer was performed. The actor produced a shell-mass-fraction proposal for review; no real candidate training or final holdout scoring occurred.

## 0.17.0

- Add read-only historical baseline auditing across checkout upgrades while keeping current-source equality mandatory for new baseline approval/execution.
- Add a fixed validation-median-offset proposal screen with an analytical MAE improvement bound, explicit REJECTED/NOT_RUN versus pending research review, and no training or holdout scoring.
- Bind proposal records to prior qualified HGB evidence and retain conservative published/local task/data-scoped mechanism closures; changed IDs cannot reopen a closed or reserved screen.
- Preserve the T1 negative proposal: offset 0.0121221781 rings bounds any possible MAE gain below its predeclared 0.05 threshold. No parameter rescue, new baseline attempt or final holdout evaluation.
- Keep tabular autonomous research disabled. Screening and baseline audit are engineering capabilities, not scientific success or authenticated execution proofs.

## 0.16.0

- Prepare a pinned, licensed UCI Abalone baseline-qualification review with feature-hash train/validation/holdout splits; do not fit or score real data during preparation.
- Bind review/approval to data, fixed recipe, source and environment requirements. Execute a single reviewed attempt with a built-in worker, private validation labels and untouched final holdout; refuse stale approval and retries.
- Add a separate pinned CPU environment, fixed median/Ridge/HGB baselines, exact model/seed/output validation, repeatability and qualification gates, measured resources and explicitly unknown local monetary costs.
- Validate task isolation and the complete baseline path using synthetic records on macOS and in Linux CI. Keep the general regression task evaluation-only: this does not enable autonomous candidate research, shared task memory or generalized study auditing.
- Publish a concrete second-task review request; real Abalone baseline fitting/scoring remains pending user review.

## 0.15.0

- Add a closed, versioned task catalog and `task list/show`; bind new SR policies to the task contract digest. Reject unknown and evaluation-only tasks before autonomous setup, reservation or model calls.
- Extract existing SR scoring into a task evaluator and share the frozen effect/interval/latency gate across Workspace, autonomous evaluation and read-only audit; keep historical SR formats and decisions.
- Add an evaluation-only deterministic tabular regression contract: fixed target/baseline/candidate content hashes, exact row identities, finite predictions, lower-is-better MAE and independent-row bootstrap.
- Run a synthetic second-task registration/evaluation/STOP/report demo through the existing ledger; no candidate execution, training, live research, generalized memory/audit or scientific performance claim.
- Publish a unified roadmap with explicit completion gates for the remaining second-task autonomous runner and research-quality evaluation.

## 0.14.0

- Add offline study evidence export, verification and review-only unpacking using a versioned JSON envelope and flat filename allowlist.
- Check per-file/envelope hashes and independently rerun the existing audit before exporting or unpacking; do not trust a sender's audit flag.
- Refuse inconsistent, incomplete, linked, changing or oversized evidence and existing destinations; keep review copies separate from research memory and execution.
- Publish unpacked run directories only after staging selected files; exclude raw model logs, papers, arrays and auth files from automatic collection. Text still requires review before sharing.

## 0.13.0

- Add read-only `study list`, `study status --run` and `study audit --run` without model or image access.
- Audit lifecycle order, frozen code/plan and review hashes, observation identities and aggregates; recompute paired bootstrap/latency and enforce all frozen adoption gates.
- Require this audit for new `research` completion reports; incomplete or inconsistent artifacts cannot claim workflow completion.
- Keep invalid measurements and pre-registration rejections distinct from scientific success; status never infers process liveness or resumes work.

## 0.12.0

- Add offline research-memory status/export/import for transferring conservative SR exclusions, stopped/rejected proposal mechanisms and optional candidate source across checkouts.
- Bind packets to a versioned task/dataset identity and checksum; reject conflicting study identities, terminal decisions and overlapping independent reservations before atomic import.
- Freeze merged published/local/imported memory with new studies; retain papers and reservations after rejection/incomplete execution and prevent shared study-ID reuse.
- Enforce a host-local single-writer lock throughout autonomous research and memory updates; process exit releases the lock but never a reservation.
- Keep experimental thresholds, scientific history and OS isolation unchanged; migration acceptance uses software fixtures only.

## 0.11.0

- Require an immutable preregistration intervention review for new autonomous studies: stopped-code fingerprints, isolated synthetic tests after actual output conversion, and an independent isolated mechanism reviewer.
- Close a rejected proposal before registration, inference or scoring; keep NOT_RUN separate from scientific STOP.
- Validate one Linux autonomous cycle with review PASS followed by a valid negative geometric-registration result; stop the route and exclude its 12 fresh holdout originals.
- Preserve review artifacts and separate reviewer token usage; model charges remain unknown. Finite probes and model review are conservative checks, not equivalence proofs.

## 0.10.0

- Add fail-closed rootless Linux Bubblewrap isolation with explicit mounts, PID/network namespaces, read-only responses/inputs and no host-root bind.
- Add Linux CPU wheel locks, non-root bootstrap, headless login/admin guidance and actual namespace/inside-actor CLI probes.
- Keep shared preregistration, independent scoring, one-run and stopping logic; normalize Linux peak RSS from KiB to bytes.
- Validate one full Ubuntu ARM64 autonomous cycle, macOS regression, and x86_64 CPU/kernel CI without model credentials.
- Preserve the valid negative phase-offset study and carry its STOP, used images and sources forward.

## 0.9.0

- Add a source-checkout bootstrap with pinned dependencies and verified external assets.
- Add `doctor` with login/capability checks and actual macOS filesystem/network probes.
- Add `research --id` to freeze a fresh holdout and run one autonomous literature/code/experiment/report cycle.
- Preserve reports, papers, arrays and controller sources in the run directory; refuse duplicate IDs and automatic retries.
- Carry published and local STOP routes, used sources and image reservations into new studies.
- Validate the workflow from an independent environment in a clean, space-containing path on the same Apple Silicon Mac. The research candidate validly STOPPED; this is workflow validation, not algorithm success.
