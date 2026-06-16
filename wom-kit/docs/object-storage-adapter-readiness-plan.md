# Object Storage Adapter Readiness Plan

Status: v0.3.41 read-only adapter readiness baseline
Date: 2026-06-15

`object-storage-adapter-readiness-plan` checks whether a WOM archive has the
local metadata needed before a future object-storage adapter can be implemented.

It is not an adapter. It does not call a provider.

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
`provider-status`.

It checks:

- whether an object-storage provider binding exists,
- whether that binding is setup-managed,
- whether the local setup receipt is present,
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

Before any future live adapter can run, WOM still needs:

- `provider-status` ready state,
- credential access broker plan,
- credential policy check,
- human approval receipt,
- object-storage operation request plan,
- adapter manifest,
- private URL handling policy for presigned operations,
- non-secret adapter audit receipt after execution.

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
