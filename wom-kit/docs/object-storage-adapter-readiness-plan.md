# Object Storage Adapter Readiness Plan

Status: v0.4.13 exact-first local setup readiness
Date: 2026-08-29

`object-storage-adapter-readiness-plan` checks whether a WOM archive has the
canonical local metadata needed before an object-storage operation can be
considered.

The planner is not an adapter and does not call a provider. v0.4.13 has a
separate, narrow provider-capable preservation route under
`object-storage-adopt-existing --preserve-local-only`; planner readiness alone
does not authorize or prove that route.

## Command

```bash
archive object-storage-adapter-readiness-plan <archive-root> \
  --operation presigned_download \
  --dry-run \
  --format json
```

Aliases:

```text
object-storage-adapter-plan
objet-storage-adapter-readiness
```

MCP:

```text
object_storage_adapter_readiness_plan
```

Related request package:

```text
archive object-storage-operation-request-plan <archive-root> --dry-run
MCP: object_storage_operation_request_plan
```

Related upload execution contract:

```text
archive object-storage-adapter-execution-contract <archive-root> --operation upload_object --dry-run
MCP: object_storage_adapter_execution_contract
```

## What It Checks

The planner reads local provider metadata and setup receipts through
`provider-status`. The current reader derives the canonical binding identity
and expected exact receipt first. It uses a legacy receipt only when that
receipt satisfies the complete strict historical bridge.

It checks:

- whether an object-storage provider binding exists,
- whether that binding is setup-managed,
- whether the local setup receipt is present,
- whether exact binding/receipt identity agrees without an orphan, malformed,
  changing, case-colliding, or cross-provider receipt,
- which operation is being planned,
- which future gates are still required.

Supported operations:

- `upload_object`
- `download_object`
- `head_object`
- `presigned_download`
- `presigned_head`
- `list_metadata_only`

## What It Does Not Echo

The planner does not echo:

- bucket names,
- object prefixes,
- provider endpoint URLs,
- provider account values,
- local absolute paths,
- exact credential refs,
- secret values,
- generated URLs,
- provider setup receipt paths.

The output may include a provider kind such as `cloudflare-r2` or `generic-s3`,
but it does not expose resource details.

## Required Gates

Before the current exact preservation route can call a provider, WOM still
needs:

- current exact `provider-status` setup evidence,
- the intended project runtime and archive identity,
- a separately authorized credential capability,
- an exact operation manifest and native run/cancel decision,
- a stable local-byte preflight,
- a private manifest-bound resume ledger,
- conditional create-only remote publication,
- HEAD plus complete GET rehash before terminal success,
- an immutable terminal receipt and independent verification.

Download, presigned URL, listing, and the unscoped legacy upload/adopt families
remain outside this narrow implementation. Their planning rows are not live
provider authority.

## Closed Actions

`object-storage-adapter-readiness-plan` does not:

- call provider APIs,
- retrieve credential values,
- open a password manager, keyring, browser password store, or secret manager,
- create presigned URLs,
- upload objects,
- download objects,
- read object bytes,
- check remote object availability,
- write files or receipts,
- draft zets,
- mint zets.

It is a readiness planner, not an object-storage client.
