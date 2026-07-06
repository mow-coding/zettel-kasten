# Object Storage Adapter Execution Contract

Status: v0.3.78 read-only upload execution-contract checkpoint
Date: 2026-06-16

`object-storage-adapter-execution-contract` defines the safety contract a future
live object-storage upload adapter must satisfy.

It is not the upload adapter. It does not read object bytes, compute local file
hashes, call a storage provider, retrieve a secret, write a resume ledger, write
an execution receipt, or update `objects/manifests/files.jsonl`.

It answers one narrow question:

```text
If WOM-kit later uploads a sha256-addressed objet, what must the adapter prove
before and after it touches the provider?
```

## Command

```bash
archive object-storage-adapter-execution-contract <archive-root> \
  --operation upload_object \
  --object-id sha256:<hex> \
  --store-ref object-store-20260616 \
  --provider-ref cloudflare-r2 \
  --dry-run \
  --format json
```

Aliases:

```text
object-storage-upload-execution-contract
objet-storage-adapter-execution-contract
```

MCP:

```text
object_storage_adapter_execution_contract
```

## What It Contracts

The upload adapter contract requires:

- a ready object-storage setup and local setup receipt,
- a scoped `object-storage-operation-request-plan`,
- a verified human approval receipt,
- a local object whose content SHA-256 matches the `sha256:<hex>` object id,
- a selectable remote key strategy (the default is sha256 content-addressed; see below),
- a provider HEAD/idempotency check before upload, on the RECORDED remote key,
- a provider confirmation check after upload,
- a bounded retry and resume ledger for large media,
- a non-secret execution receipt after execution,
- a manifest location update only after provider confirmation.

### Remote key strategy (v0.3.166: selectable)

Two strategies are supported, chosen per run with `--key-strategy`:

- **`sha256_content_addressed`** (default): the object lands at exactly

  ```text
  sha256/<first2>/<sha256>
  ```

  No provider prefix is prepended.

- **`prefix`**: the object lands under an operator-supplied literal key prefix

  ```text
  <configured-prefix>/<sha256>[.<ext>]
  ```

  The extension suffix appears only under `--key-append-extension`, and only when
  the original-filename extension is recoverable byte-exactly; otherwise nothing
  is appended (no bare trailing dot). The full original filename never appears.

The configured prefix VALUE is never echoed in public output
(`remote_prefix_value_echoed: false`). Every location keeps a content-addressed
`key_hint` (the digest binding on the immutable object id) AND records the actual
`remote_key`. The HEAD-before idempotency check uses the recorded `remote_key`,
not a recomputed content-addressed key — this is the fix for the false-skip where
an object stored under a client's own key layout was re-uploaded (or, worse,
falsely skipped).

Since v0.3.175, `object-storage-upload --force-reupload` lets an operator RE-PUT an
already-present, size/hash-matching object for LIVE verification (e.g. a forced small
multipart). A forced re-PUT bypasses the present+match skip (`skipped_remote_same`) and
the resume-ledger terminal-success short-circuit, but PRESERVES the pre-PUT local
`sha256(local)==object_id` re-verify (a corrupt local file is refused before any PUT)
and the HEAD-after re-download-and-hash verification (a re-PUT is verified exactly like a
first PUT, with SA-5 delete-on-mismatch and the cumulative PUT ceiling still in force).
Since v0.3.177, that ledger bypass also applies when a post-crash/handoff state has a
terminal resume-ledger row but no `wom_uploaded` manifest location, and a forced result
with `put_calls == 0` fails closed as `force_reupload_not_performed`. It requires
`--approve` AND `--reviewed-by`, is inert under `--dry-run`, and is REFUSED for any
non-sha-derived `--key-strategy` (the conflict-guard bypass is safe only when the remote
key embeds the object digest). The execution receipt records a top-level
`forced_reupload` boolean.

### Adopt-existing (the 158 GB false-skip fix)

`object-storage-adopt-existing` lets an operator whose objects already live under
their own key layout record those objects without re-uploading. A **verified**
adopt (with `--approve` + a live transport) issues a **presence-only** `HeadObject`
for each computed `remote_key` and adopts ONLY on a 200 + Content-Length
size-match (presence+size). The presence-only HEAD deliberately does NOT trigger
the whole-object re-download-and-hash described in Integrity Rules below — it reads
presence and `Content-Length` only and leaves the checksum unset. This is the
whole point of the cost design: adopting a large archive costs one HEAD per
object, not one GetObject-download per object (a content re-hash of a 158 GB set
would download all 158 GB). `--content-hash-verify` is an explicit per-object
opt-in that additionally GetObject-and-rehashes; it is never the default. A 404 /
size-mismatch does NOT adopt, so a wrong-prefix/wrong-extension template
self-limits to zero adopts and those objects simply re-upload. A **declared** adopt
(`--accept-unverified-adopt`, distinct from `--approve`) records a NON-gating
`declared_uploaded` location that never skips a PUT.

Verified adopt is a live-execution surface (it reaches the live transport), so it
still bounds the first live batch behind a tiny-first proof. Since v0.3.174 the
adopt gate is DECOUPLED from the `object-storage-upload` 5 GiB / multipart tier
proof (additive, no migration): adopt is HEAD-only and moves zero bytes, so it uses
a BINARY adopt-specific gate rather than the upload 3-tier ladder — a single
tiny-first adopt (`--only <id>`) is always permitted, and exactly one prior VERIFIED
tiny-first adopt unlocks a batch adopt of any size N. A bulk first-live adopt on a
store with no prior verified adopt REFUSES with `adopt_tiny_first_unmet` (NOT the
upload gate's `tiered_gate_unmet`, which is unchanged); the adopt proof is derived
only from execution receipts carrying a verified `adopt_verification` marker
(`presence_size`/`content_hash`), so an `object-storage-upload` receipt never
unblocks adopt and a declared/unverified adopt never counts. A location adopted
presence+size records `remote_key_verification: presence_size`, and the executor's
later skip re-HEAD of such a location is likewise presence-only — a size-only proof
is never silently promoted to a content-hash claim.

## Integrity Rules

The object id is the WOM content identity. A future live adapter must verify the
local bytes against that id before upload.

For S3-compatible providers, the contract prefers SHA-256 provider checksums
when the provider supports them. ETag is not treated as the WOM SHA-256 unless a
provider-specific policy has explicitly verified that equivalence for the exact
upload mode. Multipart uploads and encrypted objects can make ETag unsuitable as
a SHA-256 proof.

Stage 2 (v0.3.164) makes this concrete, and does so WITHOUT depending on any
provider-stored SHA-256 checksum. This is deliberate: a stored server-side
whole-object SHA-256 is not reliably available on the target. On both AWS S3 and
Cloudflare R2 a SHA-256 multipart checksum can only be COMPOSITE (a
checksum-of-checksums that never equals the whole-object digest); full-object
multipart checksums are CRC-only. R2 additionally does not implement
GetObjectAttributes and marks the `x-amz-checksum-*` headers "Feature Not
Implemented". A design that relied on `x-amz-checksum-sha256` + `FULL_OBJECT` +
GetObjectAttributes therefore could never confirm a genuine upload against R2.

Instead, the whole-object proof is **re-download-and-hash**: after a PUT or a
completed multipart upload, the transport issues a `HeadObject` (presence +
`Content-Length`) and then a `GetObject`, streams the returned bytes, and computes
their SHA-256, returning it as lowercase hex. The WOM executor compares that hex
to the object id byte-for-byte. This is identical for single-part and multipart
objects and depends on no provider checksum surface. The upload requests still
sign the real payload SHA-256 in SigV4 (`x-amz-content-sha256`), so the provider
independently validates each PUT/part body on the wire; we simply do not rely on
the provider to store or surface a whole-object SHA-256. If the object cannot be
read back and hashed to the object id, the object FAILS — it is never confirmed on
ETag or size alone, and a completed-but-wrong object is deleted. The one live
residual (`unproven_against_live_provider` until the first live object) is
signature ACCEPTANCE by R2's authorizer and read-after-write consistency, not any
checksum-surface question.

Official references checked for this checkpoint:

- AWS S3 object integrity and checksum documentation:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html>
- AWS S3 multipart checksum algorithm/type support table (SHA-256 is
  composite-only; full-object multipart is CRC-only):
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html>
- AWS S3 `PutObject` API checksum fields:
  <https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html>
- AWS S3 object and ETag documentation:
  <https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html>
- Cloudflare R2 S3 API compatibility:
  <https://developers.cloudflare.com/r2/api/s3/api/>

## Multipart part size and live-verification override (v0.3.172)

An object at or above `--multipart-threshold` (default 5 GiB) uploads via multipart:
create → N × put_part → complete, with each part read from disk in
`OBJECT_STORAGE_MULTIPART_PART_SIZE_BYTES` (64 MiB) chunks by default.

The multipart **code path** is already unit-tested with no network: the injected fake
transport drives a 65 MiB fixture to `part_count == 2`, exercising
create/put_part/complete/abort-on-error. What that does NOT prove is **live R2
multipart** — real per-part SigV4 signing and a `CompleteMultipartUpload` accepted by
R2's authorizer. That remains `unproven_against_live_provider` until a human runbook
confirms the first live multipart object.

To make that live proof reachable on a small object, `object-storage-upload` accepts a
live-verification part-size override:

- **`--multipart-part-size <BYTES>`** — bounded to `[4096, 64 MiB]`. It changes ONLY the
  `handle.read()` chunk size (how the file is fragmented into parts); it changes nothing
  about integrity.
- **`--allow-tiny-parts`** — required to set a part size below the 64 MiB default. The
  acknowledgment exists because real R2 rejects multipart parts smaller than 5 MiB except
  the last. A sub-5-MiB part is therefore a fake-transport / local validation aid: a live
  tiny-part rejection is an upload **rejection** (a failed status), never a silent
  integrity bypass. Tiny parts are NOT R2-accepted.

To force multipart on a small object you lower BOTH `--multipart-threshold` and
`--multipart-part-size` — the two flags are paired. The threshold floor is validated
against the *effective part size*, not the 64 MiB constant, so the threshold can drop
below 64 MiB together with the part size. The threshold stays an explicit,
receipt-recorded operator choice; the part-size flag does not silently move it.

Integrity is unchanged by the part size. The before-hash is the whole-object
`content_sha256`, computed once over the whole file; `complete_multipart` and the
HEAD-after re-download-and-hash both verify the FULL-OBJECT sha256, never a per-part
digest; SA-5 delete-on-mismatch and the leak gate are unconditional. On any part-size,
threshold, or acknowledgment violation the run does not proceed and no provider PUT is
issued. The execution receipt records `effective_multipart_part_size_bytes` so an auditor
can verify `ceil(size / part_size) == part_count` and confirm the split was forced.

Since v0.3.175, upload **tier2** is proven by EITHER a genuine 5 GiB large-object PUT
(`bytes_uploaded >= OBJECT_STORAGE_MULTIPART_THRESHOLD_BYTES`, kept verbatim) OR a real
multipart execution (`part_count > 1` on an `uploaded` receipt). A forced small multipart
is therefore the tier2 proof it actually is, so a store with no >5 GiB object can prove
upload tier2 (paired with `--force-reupload` on an already-present object). The
`part_count` disjunct is guarded to `status == "uploaded"` — `part_count` is only ever
written from a real multipart execution on an `uploaded` receipt (skips carry
`part_count 0`), so a fabricated skip receipt cannot mint tier2. The adopt tier ladder is
unaffected.

## Resume Ledger

Large media uploads must not be a blind one-shot action. A future adapter needs
a non-secret resume ledger such as:

```text
receipts/providers/object-storage-executions/<case-id>.resume-ledger.jsonl
```

The ledger may record safe progress metadata such as operation, object id,
chunk/part counters, retry counts, timestamps, and result status. It must not
record secret values, exact credential refs, provider URLs, bucket names, local
absolute paths, or raw adapter output.

## Execution Receipt

After a future upload succeeds or fails, the adapter must write a non-secret
receipt shaped like:

```text
receipts/providers/object-storage-executions/<case-id>.object-storage-upload.json
```

Expected safe fields:

- operation,
- object id,
- provider kind,
- safe store ref,
- key strategy,
- result status,
- uploaded byte count,
- checksum algorithm,
- the effective multipart threshold and part size, and the part count,
- retry summary,
- manifest update preview.

The receipt must not include:

- secret values,
- exact credential refs,
- bucket names,
- provider URLs,
- local absolute paths,
- raw adapter output.

## Manifest Update Rule

`objects/manifests/files.jsonl` may be updated only after provider confirmation.

A future manifest location update may add safe fields such as:

- provider,
- store kind,
- store ref,
- availability,
- content-addressed flag,
- WOM byte-verification flag,
- upload timestamp,
- execution receipt reference.

It must not publish provider URLs or provider resource details.

## Closed Actions

`object-storage-adapter-execution-contract` does not:

- call provider APIs,
- retrieve credential values,
- open a password manager, keyring, browser password store, or secret manager,
- read object bytes,
- hash local object bytes,
- check remote object availability,
- upload objects,
- write resume ledgers,
- write execution receipts,
- update manifests,
- draft zets,
- mint zets.

For beginners: this is the rule sheet for the future upload button. It proves
what the button must check, but it still does not press the button.
