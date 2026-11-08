# A2-R1 external replication — data qualification blocked

2026-11-08. **BLOCKED_DATA_QUALIFICATION / NOT_REGISTERED / NOT_RUN**.

Preferred source for further qualification: Luesutthiviboon and Lima Pereira,
*Dataset: Aeroacoustic Benchmarking of Trailing-edge Noise from a NACA 633–018
Airfoil with Trailing-edge Serrations*, version 1,
[DOI 10.4121/20940646.v1](https://doi.org/10.4121/20940646.v1).
This is an independent acquisition candidate, not yet a qualified direct A2
replication dataset. No acoustic target files were downloaded or scored.

Read the [review and proposed protocol](../../../docs/AIRFOIL_REPLICATION_REVIEW.md),
[source screening](source-screen.json), [pinned metadata inventory](metadata-inventory.json),
[decision record](decision.json), and [author inquiry draft](AUTHOR_QUESTIONS.md).
The draft has not been sent. An execution approval cannot waive unresolved
measurement definitions or create data-use permission from the rights holder.

The [protocol draft](protocol-draft.json) preserves the A2 intervention, reference,
training rows, metric, thresholds, uncertainty and no-rescue rules. It is a design
record, **not an execution manifest**. Its data mapping, eligible row IDs and
adapter remain unqualified; it must not be passed to `airfoil approve-trial` or
`airfoil execute-trial`. Those commands remain specific to the consumed A2 packet.

Recheck the downloaded, local metadata without model execution:

```sh
python3 scripts/check-airfoil-external-metadata.py \
  --metadata-dir reviews/airfoil-external-screen-022
```

For another checkout, download only the two master tables from the exact URLs
in `source-screen.json`, retain the filenames expected by the checker, and verify
the pinned hashes. No automatic download, acoustic read, fit or approval occurs.
The checker reports a blocked inventory; it is not a general data-qualification
or research-approval engine. Raw tables and downloaded documents remain local.

A1 and A2 evidence and consumed-holdout memory are unchanged. A2 remains a valid
local CONTINUE; this metadata blockage is neither replication success nor a
scientific negative result for Strouhal augmentation.
