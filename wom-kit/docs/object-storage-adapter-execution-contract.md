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
- a sha256 content-addressed remote key strategy,
- a provider HEAD/idempotency check before upload,
- a provider confirmation check after upload,
- a bounded retry and resume ledger for large media,
- a non-secret execution receipt after execution,
- a manifest location update only after provider confirmation.

The remote key strategy is:

```text
{provider_prefix}/sha256/<first2>/<sha256>
```

The provider prefix value itself must not be echoed in public output.

## Integrity Rules

The object id is the WOM content identity. A future live adapter must verify the
local bytes against that id before upload.

For S3-compatible providers, the contract prefers SHA-256 provider checksums
when the provider supports them. ETag is not treated as the WOM SHA-256 unless a
provider-specific policy has explicitly verified that equivalence for the exact
upload mode. Multipart uploads and encrypted objects can make ETag unsuitable as
a SHA-256 proof.

Official references checked for this checkpoint:

- AWS S3 object integrity and checksum documentation:
  <https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html>
- AWS S3 `PutObject` API checksum fields:
  <https://docs.aws.amazon.com/AmazonS3/latest/API/API_PutObject.html>
- AWS S3 object and ETag documentation:
  <https://docs.aws.amazon.com/AmazonS3/latest/API/API_Object.html>
- Cloudflare R2 S3 API compatibility:
  <https://developers.cloudflare.com/r2/api/s3/api/>

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
