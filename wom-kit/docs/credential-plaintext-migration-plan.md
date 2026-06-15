# Credential Plaintext Migration Plan

Status: v0.3.29 read-only plaintext secret migration planning baseline
Date: 2026-06-15

v0.3.29 adds a read-only planner for the case where a human already has IDs,
passwords, API keys, app passwords, OAuth tokens, or CLI tokens in a plaintext
note and wants to move them into a real vault/keyring.

The planner does not read that note.

It describes the safe future workflow:

```text
human chooses a plaintext note in a visible local UI
-> local scanner proposes candidate entries without returning values to AI
-> human confirms each entry and target
-> future approved adapter writes the secret to the selected vault/keyring
-> WOM records only refs, metadata, approval receipts, and audit receipts
```

It is not a secret scanner, importer, vault writer, keyring writer, or cleanup
tool.

## Command

```bash
archive credential-plaintext-migration-plan <archive-root> \
  --source-label plaintext-note-001 \
  --credential-id cred:openai-api \
  --credential-kind openai_api_key \
  --provider openai \
  --target-store-id keepassxc \
  --scenario personal_local_first \
  --platform windows \
  --dry-run \
  --format json
```

Aliases:

```text
secret-migration-plan
credential-import-plan
```

MCP tool:

```text
credential_plaintext_migration_plan
```

## Source Label Rule

`--source-label` is a safe non-secret label only.

Use:

```text
plaintext-note-001
old-api-key-note
legacy-password-list
```

Do not use:

```text
local file paths
email addresses
provider URLs
real usernames
real passwords
real API keys
real tokens
```

v0.3.29 does not accept or print the real local path of the plaintext note.

## Target Store

The command reuses the v0.3.28 vault onboarding store ids:

- `recommended`,
- `keepassxc`,
- `bitwarden`,
- `1password`,
- `browser_or_platform_password_manager`,
- `os_keyring`,
- `developer_secret_manager`,
- `environment_variable`.

For most plaintext secret migration cases, `keepassxc`, `bitwarden`,
`1password`, `os_keyring`, or `developer_secret_manager` is safer than a
browser/platform password manager or environment variable.

## Current Closed Actions

`credential-plaintext-migration-plan` does not:

- ask the user to paste a secret into chat,
- read a plaintext file,
- print a plaintext file path,
- hash plaintext bytes,
- detect secret values,
- return candidate secret values to AI,
- open KeePassXC,
- open Bitwarden,
- open 1Password,
- open browser password stores,
- open Windows Credential Manager,
- open macOS Keychain,
- open Linux keyrings,
- read environment variables,
- write to any vault,
- write to any keyring,
- write `.env` files,
- call providers,
- start OAuth,
- delete or quarantine the old plaintext note,
- write receipts,
- draft zets,
- mint zets.

It is a plaintext migration planner, not a migration executor.

## Relationship To The Credential Layers

The safe chain remains:

```text
credential-store-recommendation
-> credential-vault-onboarding-plan
-> credential-plaintext-migration-plan
-> credential-ref-plan
-> credential-ref-inventory
-> credential-access-broker-plan
-> credential-access-approval-plan
-> credential-policy-check
-> credential-adapter-readiness-plan
-> credential-adapter-manifest-plan
-> credential-adapter-audit-plan
```

v0.3.29 adds only the pathless, non-secret migration planning step. Actual
secret detection, vault writes, keyring writes, cleanup, and deletion remain
future local UI and adapter work.

v0.3.30 adds a read-only execution gate. See
[Credential Policy Check](credential-policy-check.md).

v0.3.31 adds a non-secret approval receipt writer that policy-check can verify
before any future migration adapter runs. See
[Credential Access Approval Plan](credential-access-approval-plan.md).
