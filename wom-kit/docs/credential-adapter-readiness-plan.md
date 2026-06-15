# Credential Adapter Readiness Plan

Status: v0.3.25 read-only adapter readiness baseline
Date: 2026-06-15

WOM should be able to prepare for keyring and password-manager integration
without becoming a password vault itself.

This document defines the v0.3.25 read-only readiness planner for future
credential adapters.

## Command

```bash
archive credential-adapter-readiness-plan <archive-root> \
  --adapter-kind windows_credential_manager \
  --operation resolve_for_approved_action \
  --credential-id cred:openai-api \
  --credential-ref keyring:openai-api-key \
  --credential-kind openai_api_key \
  --provider openai \
  --action-kind model_api_call \
  --platform windows \
  --dry-run \
  --format json
```

Aliases:

```text
credential-adapter-plan
secret-adapter-readiness
```

MCP tool:

```text
credential_adapter_readiness_plan
```

## What It Plans

The planner describes the contract a future local adapter must satisfy before
it can safely touch a real credential store.

Supported adapter kinds:

- `keepassxc_cli`,
- `bitwarden_cli`,
- `onepassword_cli`,
- `windows_credential_manager`,
- `macos_keychain`,
- `linux_secret_service`,
- `browser_platform_manager`,
- `developer_secret_manager`,
- `environment_injection`,
- `future_wallet`.

Supported operation plans:

- `resolve_for_approved_action`,
- `write_new_secret`,
- `rotate_secret`,
- `plaintext_secret_migration`,
- `browser_login_fill`,
- `list_metadata_only`.

## Required Boundary

The planner requires the same boundary as the broker and approval planners:

```text
credential ref
-> broker request
-> human approval receipt
-> future local adapter
-> non-secret audit metadata
```

It does not skip the approval layer. It previews the approval dependency and
the future adapter contract together.

## Non-Secret Inputs

The planner can accept:

- credential id,
- credential kind,
- provider label,
- action kind,
- adapter kind,
- operation kind,
- store kind,
- ref store and ref prefix.

The exact `credential_ref` value is not echoed back.

## Forbidden Inputs And Outputs

The future adapter contract must not expose:

- raw password,
- raw token,
- raw API key,
- exact credential ref value in AI-visible output,
- absolute vault path,
- browser profile path,
- provider account email.

The future adapter output must not include:

- secret value,
- password,
- token,
- API key,
- local secret file path.

## Current Boundary

v0.3.25 does not implement live adapter execution.

It does not:

- open KeePassXC, Bitwarden, or 1Password,
- open Windows Credential Manager, macOS Keychain, or Linux keyrings,
- open browser password stores,
- read environment variables,
- read plaintext secret notes,
- write new secrets,
- rotate secrets,
- migrate plaintext secrets,
- call providers,
- write approval or audit receipts.

It is an adapter readiness preview, not a keyring reader, vault writer, or
secret migration tool.

## Why This Exists

The user may want WOM-side AI to help with real tasks such as mail reading,
OCR, model calls, object storage, browser login assistance, or migration from
plaintext notes into a password manager.

The safe shape is not:

```text
AI receives the password
```

The safe shape is:

```text
AI requests a scoped capability
local policy checks it
human approves it
local adapter uses the secret without echoing it
WOM records non-secret metadata
```

This planner prepares that contract without executing an adapter itself.

Next layer:

- [Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md)
- [Credential KeePassXC Write](credential-keepassxc-write.md)
- [Credential Adapter Manifest Plan](credential-adapter-manifest-plan.md)
