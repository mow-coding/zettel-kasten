# Object Storage Upload Evidence Audit

Status: v0.3.86 read-only upload evidence audit checkpoint
Date: 2026-06-17

`object-storage-upload-evidence-audit` checks whether a local upload evidence
receipt and the local object manifest agree with each other.

It is not a remote availability check. It does not call Cloudflare R2, S3, or
any other provider. It does not prove that a remote object is online right now.

It answers this narrower question:

```text
Did WOM-kit record the reviewed external upload evidence consistently?
```

## Command

```bash
archive object-storage-upload-evidence-audit <archive-root> \
  --receipt receipts/providers/object-storage-upload-evidence/<receipt>.json \
  --dry-run \
  --format json
```

Aliases:

```text
object-storage-external-upload-evidence-audit
objet-storage-upload-evidence-audit
```

MCP:

```text
No MCP tool is exposed for this surface.
```

## What It Checks

The audit reads one archive-relative receipt and
`objects/manifests/files.jsonl`. It checks:

- the receipt schema is `wom-kit/object-storage-upload-evidence-receipt/v0.1`,
- the lifecycle action is `object_storage_upload_evidence_register`,
- the receipt belongs to the current archive,
- provider kind and `store_ref` are safe labels,
- `reviewed_by` is a safe non-secret reviewer label,
- ledger paths were not included,
- privacy guards say paths, row values, object ids, provider URLs, bucket names,
  account ids, emails, tokens, and secret values were not echoed,
- closed actions say WOM-kit did not read source bytes, compute local source
  hashes, call providers, remote-HEAD objects, upload, download, or retrieve
  secrets,
- the manifest update was completed,
- manifest locations link back to the audited receipt,
- linked locations use `availability: declared_uploaded`,
- linked locations keep `byte_verification_by_wom_kit: false`,
- linked locations keep `provider_confirmation_by_wom_kit: false`,
- linked locations use the sha256 content-addressed key strategy,
- the linked manifest location count matches the receipt summary.

The command does not print receipt paths, manifest paths, object ids, or
location records. It reports counts and pass/block status instead.

## Closed Actions

This command does not:

- write files,
- write audit receipts,
- read source object bytes,
- compute local source-object hashes,
- call provider APIs,
- check remote availability,
- upload objects,
- download objects,
- sync objects,
- create provider URLs,
- open a password manager, keyring, browser password store, or secret manager,
- read environment variables,
- retrieve secret values,
- draft zets,
- mint zets.

For beginners: this is a receipt-and-catalog consistency check. It is useful
before real provider adapters exist, but it is not the same as opening R2 and
asking, "Is this file definitely there right now?"

## Why This Exists

v0.3.85 added local registration of reviewed external upload evidence. The next
safe step is a read-only audit that can catch mismatched receipts or manifest
locations before the project moves to live provider adapters.

The future live adapter still needs credential retrieval, local byte
verification, provider HEAD/idempotency checks, upload execution, remote
confirmation, and provider-confirmed manifest updates.
