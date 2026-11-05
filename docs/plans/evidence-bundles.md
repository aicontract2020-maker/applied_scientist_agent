# Offline audit-evidence handoff

Deliver an auditable run snapshot distinct from exclusion-only research memory.
- `study export --run DIR --out FILE`: audit an existing terminal run and copy only named audit inputs into a versioned JSON envelope. Reject inconsistent, incomplete, linked, changing or oversized inputs; never edit evidence or overwrite a target.
- `study verify FILE`: check closed schema, per-file/content hashes and size limits, then recompute the existing read-only audit in temporary storage. No source execution, model, image, paper or external path access.
- `study unpack FILE --out NEW_DIR`: verify and audit first, create an exclusive private review container and publish its `run/` directory after all files are written. Preserve a receipt binding the files to the packet. Never register research, import exclusions, allocate data or resume a process.

Only explicit audit filenames may appear. No arbitrary relative/absolute paths, archive extraction, raw model logs, credentials, papers, image arrays or unbounded attachments. Reports, ledger and code can contain proprietary or sensitive text: selection is not automatic redaction. Sharing remains a deliberate review step. Integrity is not sender authenticity or scientific success.

Acceptance is software-only: synthetic negative/positive/invalid/rejected terminal evidence roundtrips, changed hashes/results and path keys are rejected, foreign source is never executed, existing outputs and original files remain untouched, failed operations leave no new usable review directory. A hard process kill can leave an incomplete private container, never a newly published `run/` directory before all files are written. Verify a historical G7 transfer using plain Python in a clean checkout; no new experiment or model call.
