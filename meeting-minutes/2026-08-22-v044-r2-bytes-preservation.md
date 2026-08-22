# Meeting Minutes: v0.4.4 R2 Emergency Bytes Preservation

Date: 2026-08-22
Status: adapter and writer candidate implemented in an isolated branch; no live
provider operation, protected-archive mutation, release, or formal adoption
claimed

## Direction and evidence boundary

The v0.4.4 slice was started from the integrated v0.4.3 exact-operation
foundation. The protected beta archive and remote object store were inspected
only through existing local evidence; this implementation branch did not call
a provider or mutate the archive.

The evidence audit fixed the working inventory before code was written:

- 23,580 manifest rows represent 22,431 unique Objet;
- 1,149 object ids have conflicting duplicate definitions;
- 4,525 local locations decompose into 1,149 conflict groups and 3,376
  non-conflicting local objects;
- two of those 3,376 already have remote evidence, leaving exactly 3,374
  emergency-preservation candidates;
- the full manifest evidence metric is 597 and the official de-duplicated
  evidence metric is 560. They remain separately named and are not silently
  collapsed.

All 1,149 duplicate groups share byte identity and size, but their metadata is
not automatically merged. The implementation classifies byte identity,
logical-key conflict, MIME conflict, local/remote complementarity, remote-key
evidence, and execution-receipt evidence into a content-free review projection.

## Implemented behavior

A new service module extends the existing `object-storage-adopt-existing`
command family through `--preserve-local-only`; no new top-level command was
added.

The plan scans the central manifest once, groups object ids once, hashes each
eligible local file, and creates one shared `ExactOperationManifest`. It does
not rewrite the central manifest per item. Execution uses the common fixed
writer lock and append-only checkpoints, plus an immutable receipt per object.
A private deterministic control document retains the exact operation data
needed for same-approval resume.

Every emergency key is derived only from the content digest:

```text
wom-bytes-preserved/v1/sha256/<first-two-hex>/<full-sha256>
```

The remote adapter requests a full proof through the existing S3-compatible
transport: HEAD establishes presence and size, then GET rehashes the complete
object. It distinguishes absent, unavailable, size mismatch, checksum
mismatch, and verified match without returning URLs, provider bodies,
credentials, remote keys, object ids, or local paths in the public projection.

For an absent key, the writer reuses the existing bounded upload and multipart
spine. It rehashes the local file immediately before the upload, refuses to
overwrite any present mismatch, verifies the uploaded bytes, writes the
immutable receipt, and then lets the independent exact-operation verifier run
a second HEAD plus complete GET rehash. Interrupted runs resume the same
checkpoint execution and do not issue a second PUT after the receipt already
exists.

The receipt deliberately records:

- `preservation_status: bytes_preserved`;
- `formal_adoption_status: not_adopted`;
- `manifest_location_updated: false`;
- complete remote size and SHA-256 verification;
- no unconditional remote-delete rollback support.

This is an emergency byte copy, not a claim that metadata conflicts or formal
adoption have been resolved.

## Feedback loop and corrections

The first focused test run exposed that a synthetic `store:test` label was not
valid under the established store-reference grammar. Tests were corrected to
use `storage:account:test`; product validation was not weakened.

A scale review then found that a 3,374-item private resume control document
would exceed the 64 KiB per-object receipt limit. Receipt and control limits
were separated: immutable item receipts remain capped at 64 KiB, while the
strict private control document has a bounded 64 MiB limit and stable
pre/post-read checks. A 600-item test proves a control document larger than
64 KiB persists and reloads to the byte-identical exact manifest.

The package-resource check also found one pre-existing v0.4.3
project-version-update source/package schema mismatch. The repository's
official resource synchronization tool repaired that mirror and added the new
bytes-preserved receipt schema to the package manifest.

The first full protected-archive dry-run then reported 597 for the strict
manifest-scope metric but only 558 for the official de-duplicated metric. A
bounded aggregate audit found the two missing cases: both have

- `wom_uploaded` availability;
- WOM byte verification and provider confirmation;
- an execution-receipt reference;
- a local copy;
- no manifest `remote_key`, and therefore no independent key verification.

The metric names and predicates were corrected instead of calling these two
records independently verified. The final names distinguish 597
`manifest_scope_remote_key_verified_object_count` from 560
`official_deduplicated_wom_uploaded_evidence_object_count`. The two legacy
key gaps remain outside the 3,374 emergency PUT set and remain evidence debt
for later formal adoption.

A final execution review found that directly inheriting the ordinary upload
command's 64-call ceiling would make a 3,374-object exact plan stop after its
first 64 PUTs. The emergency writer now derives both its expected no-retry call
count and hard retry ceiling from the exact manifest's bound object sizes and
the existing bounded per-object retry policy. This does not weaken the normal
upload command's 64-call gate. A 65-object regression proves the approved exact
batch is not silently truncated at the legacy ceiling.

## Verification performed so far

Focused synthetic coverage proves:

- full-scope and official de-duplicated evidence metrics remain distinct;
- remote absent/unavailable/size/checksum/match states;
- successful upload, immutable receipt, zero central-manifest rewrites, and
  independent verification;
- interruption after receipt followed by same-execution resume without a
  second PUT;
- fail-closed present-content conflict with no PUT and no receipt;
- manifest-bound execution beyond the ordinary 64-PUT ceiling without changing
  that ordinary command's safety limit;
- public output excludes paths, keys, object ids, URLs, and credentials;
- 5,000-row manifest planning remains linear and within the test budget;
- large private control persistence and exact reload;
- dry-run CLI routing through the existing adoption family;
- missing exact manifest approval fails before any credential read;
- source and packaged receipt schemas are byte-identical and validate a real
  generated receipt.

The final full protected-archive read-only plan completed with exit code zero,
accounted for all 22,431 unique Objet, selected exactly 3,374 preservation
targets, reported zero review exceptions in that target set, and reproduced
the separately named 597 and 560 metrics. Its first progress state appeared
immediately; an uncached run completed in about 45 seconds and an immediate
cached rerun completed in about 11 seconds.

The remaining work before release is broad regression, full protected-archive
read-only planning/performance evidence, independent review, and the later
human-approved live provider operation. This branch itself does not claim the
3,374 bytes have been uploaded.
