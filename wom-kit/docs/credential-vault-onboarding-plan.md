# Credential Vault Onboarding Plan

Status: v0.3.28 read-only vault onboarding planning baseline
Date: 2026-06-15

v0.3.28 adds a read-only planner for choosing and setting up an external
password manager, platform password manager, OS keyring, developer secret
manager, or environment-variable injection surface.

It is for the human workflow around secrets:

```text
human chooses a real vault/keyring outside WOM
-> WOM records only safe credential refs and catalog metadata
-> future broker/approval/adapter layers may use the secret without echoing it
```

It is not a password manager, keyring reader, browser password-store scraper,
secret importer, or adapter runner.

For beginner-facing first-use steps, see
[Beginner Setup Manual](beginner-setup-manual.md). That guide explains what a
vault is, how to choose safe non-secret labels, and which dry-run commands to
run next without asking for secret values.

## Command

```bash
archive credential-vault-onboarding-plan <archive-root> \
  --scenario personal_local_first \
  --store-id keepassxc \
  --credential-id cred:openai-api \
  --credential-kind openai_api_key \
  --provider openai \
  --action-kind model_api_call \
  --platform windows \
  --dry-run \
  --format json
```

Aliases:

```text
credential-vault-onboarding
secret-vault-onboarding-plan
```

MCP tool:

```text
credential_vault_onboarding_plan
```

## Supported Human Scenarios

The planner reuses the scenario set from
[Credential Store Recommendations](credential-store-recommendations.md):

- `personal_local_first`,
- `multi_device_sync`,
- `team_or_family_sharing`,
- `browser_or_platform_password_manager`,
- `automation_or_dev_secrets`,
- `local_app_adapter`,
- `institutional_mail`.

## Supported Store IDs

Use `--store-id recommended` to follow the scenario recommendation, or choose:

- `keepassxc`,
- `bitwarden`,
- `1password`,
- `browser_or_platform_password_manager`,
- `os_keyring`,
- `developer_secret_manager`,
- `environment_variable`.

The output includes:

- the selected store id,
- store class,
- store kind,
- future adapter kind,
- WOM ref prefix to record,
- generic example ref shape,
- human setup steps,
- WOM compatibility steps,
- broker-plan summary when a safe `credential_id` is supplied,
- adapter-readiness summary when a safe `credential_id` is supplied.

## WOM Compatibility

WOM should record only labels such as:

```text
secret:keepassxc-personal-mail
secret:bitwarden-openai-api
keyring:wom-mail-access
env:WOM_OPENAI_API_KEY
```

Those are not the secret values. They are labels or variable names.

The real ID, password, API key, OAuth token, app password, CLI token, database
path, account email, browser profile, and provider URL stay outside WOM.

## Human Setup Boundary

The planner may tell the human to use the external product UI manually.

Examples:

- KeePassXC desktop UI,
- Bitwarden UI,
- 1Password UI,
- Chrome/Edge/platform autofill UI,
- Windows Credential Manager,
- macOS Keychain,
- Linux Secret Service-compatible keyring,
- a developer secret manager console,
- a shell or runtime that injects environment variables outside WOM.

WOM does not open those tools in v0.3.28.

## Current Closed Actions

`credential-vault-onboarding-plan` does not:

- open KeePassXC,
- open Bitwarden,
- open 1Password,
- open Chrome or Edge password stores,
- open Windows Credential Manager,
- open macOS Keychain,
- open Linux keyrings,
- read environment variables,
- read plaintext secret files,
- import a plaintext note,
- ask for a master password,
- ask for an API key,
- write to a vault,
- write to a keyring,
- write to an environment file,
- call providers,
- start OAuth,
- write files,
- draft zets,
- mint zets.

It is a vault onboarding planner, not a vault adapter.

## Relationship To The Credential Layers

The safe chain remains:

```text
credential-store-recommendation
-> credential-vault-onboarding-plan
-> credential-ref-plan
-> credential-ref-inventory
-> credential-access-broker-plan
-> credential-access-approval-plan
-> credential-adapter-readiness-plan
-> credential-adapter-manifest-plan
-> credential-adapter-audit-plan
```

v0.3.28 plans the human-facing setup layer. It still does not store, read,
return, migrate, or use the secret value.

v0.3.29 adds a read-only pathless migration planner for old plaintext notes.
See [Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md).
