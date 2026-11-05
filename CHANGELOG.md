# Changelog

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
