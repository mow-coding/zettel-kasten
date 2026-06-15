# Credential Adapter Audit Plan

Status: v0.3.27 read-only adapter audit receipt preview baseline
Date: 2026-06-15

v0.3.27 adds a non-secret audit receipt preview for future credential adapter
use.

This does not execute an adapter. It previews what WOM should record after a
future approved local adapter operation.

## Command

```bash
archive credential-adapter-audit-plan <archive-root> \
  --adapter-id win-keyring \
  --adapter-kind windows_credential_manager \
  --operation resolve_for_approved_action \
  --credential-id cred:openai-api \
  --credential-kind openai_api_key \
  --provider openai \
  --action-kind model_api_call \
  --result-status not_run \
  --platform windows \
  --dry-run \
  --format json
```

Aliases:

```text
credential-adapter-audit
secret-adapter-audit-plan
```

MCP tool:

```text
credential_adapter_audit_plan
```

## What It Previews

The planner emits:

- a proposed audit receipt path,
- a `credential_adapter_audit` receipt preview,
- adapter metadata,
- operation metadata,
- approval dependency,
- manifest dependency,
- allowed non-secret result metadata,
- secret-material exclusions,
- closed actions.

The proposed receipt path has this shape:

```text
receipts/credentials/adapter-audits/<case-id>.credential-adapter-audit.json
```

## Allowed Result Metadata

Future adapter audit receipts may record non-secret metadata such as:

- result status,
- adapter id,
- adapter kind,
- operation,
- action kind,
- credential id,
- provider label,
- cost class,
- source object ids,
- derived text receipt refs,
- error class.

## What It Must Not Contain

The receipt preview must not contain:

- secret values,
- exact credential refs,
- usernames,
- email addresses,
- tokens,
- local paths,
- provider URLs,
- passwords,
- API keys.

## Current Boundary

v0.3.27 does not write audit receipts.

It does not:

- execute a live adapter,
- open a password manager,
- open a browser password store,
- open an OS keyring,
- read environment variables,
- read plaintext secret files,
- write a manifest,
- write an approval receipt,
- write an audit receipt,
- write or migrate secrets,
- call providers.

It is an audit receipt preview, not an adapter runner.

## Relationship To The Previous Layers

The expected future order remains:

```text
credential ref
-> adapter manifest
-> readiness check
-> human approval receipt
-> KeePassXC command preflight, where relevant
-> local adapter operation
-> audit receipt
```

v0.3.27 only previews the last receipt shape. The middle live operation remains
closed.
