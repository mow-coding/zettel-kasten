# Credential Adapter Manifest Plan

Status: v0.3.26 read-only adapter manifest preview baseline
Date: 2026-06-15

v0.3.26 adds a non-secret manifest preview for future credential adapters.

The manifest is not a vault. It is a declaration of what a future local adapter
is allowed to claim before it can be reviewed, approved, and eventually
implemented.

## Command

```bash
archive credential-adapter-manifest-plan <archive-root> \
  --adapter-id win-keyring \
  --adapter-kind windows_credential_manager \
  --operation resolve_for_approved_action \
  --operation list_metadata_only \
  --platform windows \
  --dry-run \
  --format json
```

Aliases:

```text
credential-adapter-manifest
secret-adapter-manifest-plan
```

MCP tool:

```text
credential_adapter_manifest_plan
```

## Manifest Shape

The preview emits:

- a proposed archive-relative manifest path,
- a `manifest_preview` object,
- JSON schema validation status,
- closed actions,
- privacy guards.

The proposed path has this shape:

```text
config/credential-adapters/<adapter-id>.credential-adapter.json
```

The preview uses this schema name:

```text
credential-adapter-manifest.schema.json
```

The manifest itself declares:

- adapter id,
- adapter kind,
- adapter family,
- store kind,
- platform,
- consumer label,
- expected ref prefixes,
- supported operations,
- required policy/approval/audit boundaries,
- privacy contract,
- closed actions.

## What It Must Not Contain

The manifest preview must not contain:

- secret values,
- exact credential refs,
- local absolute paths,
- vault file paths,
- browser profile paths,
- provider account values,
- provider URLs,
- passwords,
- tokens,
- API keys.

## Supported Adapter Kinds

```text
keepassxc_cli
bitwarden_cli
onepassword_cli
windows_credential_manager
macos_keychain
linux_secret_service
browser_platform_manager
developer_secret_manager
environment_injection
future_wallet
```

## Supported Operations

```text
resolve_for_approved_action
write_new_secret
rotate_secret
plaintext_secret_migration
browser_login_fill
list_metadata_only
```

## Current Boundary

v0.3.26 does not write adapter manifests.

It does not:

- open a password manager,
- open a browser password store,
- open an OS keyring,
- read environment variables,
- read plaintext secret files,
- write a manifest,
- write a secret,
- migrate a secret,
- call providers,
- write approval receipts,
- write audit receipts.

It is a manifest preview and schema baseline, not a manifest writer or live
credential adapter.

## Relationship To Readiness Planning

[Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)
answers:

```text
Can this future adapter operation be shaped safely?
```

This manifest planner answers:

```text
What non-secret adapter declaration would be safe to review later?
```

Both stay dry-run only in v0.3.26.
