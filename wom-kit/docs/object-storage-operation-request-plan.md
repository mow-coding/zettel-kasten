# Object Storage Operation Request Plan

Status: v0.3.45 read-only request package baseline
Date: 2026-06-15

`object-storage-operation-request-plan` composes the safe request package before
any future object-storage adapter runs.

It is not an upload, download, metadata listing, provider call, or presigned URL
creator. It is the step that says:

```text
This is the object-storage operation being requested.
These are the local setup, object, and credential approval gates.
Nothing live has run yet.
```

## Command

```bash
archive object-storage-operation-request-plan <archive-root> \
  --operation presigned_download \
  --object-id sha256:<hex> \
  --store-ref object-store-20260615 \
  --credential-id cred:object-storage \
  --credential-ref secret:object-storage-token \
  --credential-kind object_storage_token \
  --approval-decision needs_review \
  --dry-run \
  --format json
```

Aliases:

```text
object-storage-request-plan
objet-storage-operation-request
```

MCP:

```text
object_storage_operation_request_plan
```

Related upload execution contract:

```text
archive object-storage-adapter-execution-contract <archive-root> --operation upload_object --dry-run
MCP: object_storage_adapter_execution_contract
```

## What It Composes

The request package reuses existing read-only gates:

- `object-storage-adapter-readiness-plan`
- `presigned-url-plan` for `presigned_download` and `presigned_head`
- `resolve-objet-ref` for object-specific upload/download/head requests
- `credential-policy-check` for `object_storage_request`

Supported operations:

- `upload_object`
- `download_object`
- `head_object`
- `presigned_download`
- `presigned_head`
- `list_metadata_only`

## Request States

The JSON output returns `request_state`:

- `needs_human_approval`
- `ready_for_future_adapter_after_approval`
- `denied_by_human_decision`
- `denied_by_policy`
- `blocked`

Top-level `ok: true` means the request package was safely produced and is either
waiting for human approval or has a verified approval receipt. It does not mean
that WOM-kit has a live object-storage adapter today.

`live_execution_allowed_now` remains `false`.

## Approval Receipt Rule

When `--approval-decision approve_once` is used, an
`--approval-receipt <archive-relative-path>` must be supplied and verified.

The output does not echo the approval receipt path. It only returns booleans
such as:

```text
approval_receipt_supplied
approval_receipt_verified
approval_receipt_path_echoed
future_adapter_has_verified_receipt
```

A future live adapter must verify the same receipt again before doing anything.

## What It Does Not Echo

The planner does not echo:

- bucket names,
- object prefixes,
- provider endpoint URLs,
- generated presigned URLs,
- provider account values,
- local absolute paths,
- exact credential refs,
- approval receipt paths,
- secret values,
- provider setup receipt paths.

Safe labels such as `cloudflare-r2`, `generic_provider`, `object_storage`, and a
reviewed `store_ref` may appear.

## Closed Actions

`object-storage-operation-request-plan` does not:

- call provider APIs,
- retrieve credential values,
- open a password manager, keyring, browser password store, or secret manager,
- create presigned URLs,
- upload objects,
- download objects,
- list remote metadata,
- read object bytes,
- check remote object availability,
- write files or receipts,
- draft zets,
- mint zets.

It is an approval request package for a future adapter, not the adapter itself.

## Safe Workflow

```text
provider-status
-> object-storage-adapter-readiness-plan
-> resolve-objet-ref or presigned-url-plan
-> credential-access-approval
-> object-storage-operation-request-plan
-> future provider adapter, not implemented in v0.3.45
-> future non-secret adapter audit receipt
```

For beginners: this is like preparing a signed checklist before anyone is
allowed to touch the storage provider. The checklist can say "ready after
approval," but it still does not press the upload/download button.
