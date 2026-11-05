# Portable research memory — implementation contract

Problem: a new clone only knows committed history. Local reservations, completed STOPs and papers read in failed/rejected cycles are lost when work moves between colleagues. The current single-writer rule is advisory.

Deliver one offline vertical slice:
- `memory status`: report conservative holdout availability and retained history without models/assets.
- `memory export --out FILE`: a versioned, content-bound JSON snapshot containing exclusions, stopped/rejected proposal mechanisms and optional source, plus study identity/provenance. No papers, arrays, raw events, credentials or external file references.
- `memory import FILE`: validate the entire snapshot, reject incompatible tasks, hashes, conflicting study identities/terminal decisions and overlapping independent reservations, and atomically append its content-addressed packet. Reimport is idempotent; no replacement or deletion command.
- New SR studies merge published, local and imported memory before selecting data or invoking models. Frozen review catalogs include transferred stopped implementations. Reading a paper still excludes it after proposal rejection/incomplete execution. RESERVED is distinct from scored; exclusions never shrink automatically.
- A host-local OS lock serializes research, reservation and memory operations; interruption releases the lock, not the reservation. No cross-machine live coordination is claimed. Exchange snapshots before starting new work, not after two machines independently consume the same holdout.

Acceptance uses software fixtures only: move a stopped synthetic study from clone A to B; preserve its code and paper exclusions; select disjoint new fixture IDs on B; reject conflicts/corruption without partial import; cannot reclaim rejected/incomplete reservations; subprocess lock contention fails before model/data work; actual CLI export/import/status works without scientific dependencies. Historical studies and adoption thresholds remain untouched. No new research experiment/model call is authorized by this implementation contract.

Boundaries: checksums detect accidental changes, not authenticity or honest research. Import is a deliberate trust decision about a colleague's text/code; imported code is never executed by memory handling. JSON limits and closed schemas bound input; relative/absolute paths are never followed from a packet. Source/plan descriptions may be proprietary and are explicitly documented as shareable content. This is a file exchange protocol, not a distributed registry, general task plug-in system or automatic scientific validation.
