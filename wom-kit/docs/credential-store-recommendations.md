# Credential Store Recommendations

Status: v0.3.113 read-only recommendation baseline with account recovery scenarios
Date: 2026-06-19

This document explains which external secret store fits which human scenario,
and how WOM should refer to those stores without becoming the vault itself.

## Short Answer

WOM should not store real IDs, passwords, API keys, app passwords, OAuth
tokens, or CLI tokens.

WOM should store:

- a safe credential id,
- the credential kind,
- the provider,
- the purpose,
- the store class,
- the ref prefix,
- the tool/source allowed to ask for it.

The actual value should stay in a password manager, platform password manager,
OS keyring, or developer secret manager.

## Read-Only Planner

v0.3.22 adds:

```powershell
python cli\archive.py credential-store-recommendation .\my-archive `
  --scenario personal_local_first `
  --platform windows `
  --dry-run `
  --format json
```

Aliases:

```text
credential-store-plan
secret-store-recommendation
```

MCP:

```text
credential_store_recommendation
```

The planner does not open a password manager, read a keyring, read environment
variables, call browser APIs, call providers, write files, or echo secrets.

v0.3.113 adds account recovery and break-glass scenarios for 2FA recovery
codes, backup codes, and emergency-only access material. The planner still
returns only policy, refs, and metadata. It never asks for or echoes the code
values.

## Scenario Matrix

| Human scenario | Primary recommendation | WOM ref style | Notes |
| --- | --- | --- | --- |
| `personal_local_first` | KeePassXC-style offline password manager | `secret:` | Best fit when the user wants local-first control and does not need cloud sync by default. |
| `multi_device_sync` | Bitwarden or 1Password-style syncing password manager | `secret:` | Best fit when desktop, phone, browser, and family/team usability matter. |
| `team_or_family_sharing` | 1Password or Bitwarden sharing features | `secret:` | Use the manager's native sharing controls; WOM records refs only. |
| `browser_or_platform_password_manager` | Chrome, Edge, Windows Hello, Android, iOS, Samsung, or similar login surface | `secret:` plus future broker | Best for website logins/passkeys/autofill; not a general API-key or CLI-token vault. |
| `automation_or_dev_secrets` | Bitwarden Secrets Manager or another developer secret manager | `secret:` or short-lived `env:` | Best for API keys, object storage tokens, model/OCR keys, CI-like injection, and service credentials. |
| `local_app_adapter` | Windows Credential Manager, macOS Keychain, or Linux Secret Service keyring | `keyring:` | Best fit for a future local WOM adapter that needs approved OS-mediated retrieval. |
| `institutional_mail` | Provider-required credential mode plus OS keyring/password manager | `keyring:` or `secret:` | Keep `imap:account:*` account labels separate from username/app-password/OAuth refs. |
| `account_recovery_codes` | KeePassXC-style offline password manager plus independent offline copy | `secret:` plus metadata-only offline label | Best for 2FA recovery codes, backup codes, and emergency account access material. Requires at least two independent locations and blocks a single digital-only copy. |
| `break_glass_secrets` | Same policy as account recovery, with separate custody review for very high-risk material | `secret:` plus metadata-only offline label | Best for emergency-only secrets. Wallet seed or private-key material must not be folded into generic credential migration. |

## Account Recovery And Break-Glass Material

Recovery codes and break-glass secrets are different from ordinary login
passwords because they are meant for the moment when the normal login route is
unavailable.

Use:

```text
secret:keepassxc-account-recovery-codes
offline:physical-safe
```

The `secret:` ref points to an encrypted digital copy in a password manager such
as KeePassXC. The `offline:` label is only metadata for an independent physical
copy, such as a printed copy in a protected place. WOM should record the labels
and redundancy policy only. WOM should never record the actual recovery code
values.

Minimum safe policy:

- keep at least two independent locations,
- do not keep the only copy in one digital vault or one device,
- check for circular dependency before trusting a vault,
- if the protected account controls vault sync, device login, email recovery, or
  password-manager access, the vault copy alone is not a valid recovery path,
- classify the material through `credential-semantic-extraction-recipe` before
  planning migration or inventory metadata.

## Browser And Platform Password Managers

Chrome, Edge, Windows Hello, Android, iOS, and Samsung-style password surfaces
are very good at user-facing login flows:

- remembering website credentials,
- filling login forms,
- managing passkeys,
- using device biometrics or PIN prompts,
- syncing through the user's platform account when enabled.

They are not always the right place for:

- OpenAI API keys,
- OCR API keys,
- object storage tokens,
- CLI tokens,
- backup repository passwords,
- automation secrets.

Those values usually need a password manager, OS keyring, or developer secret
manager instead.

## Future Credential Access Broker

The desired future WOM user experience is:

```text
human asks AI to do a task
-> AI asks WOM for a specific credential capability
-> WOM checks policy, purpose, provider, source, and human approval
-> a local broker asks the real vault/keyring/platform surface
-> the adapter uses the secret for the approved action
-> the secret value is never printed into chat, zets, receipts, logs, prompts, or public docs
```

The AI should not freely scrape browser databases, desktop files, plaintext
notes, or password manager exports.

A safe migration flow for an existing plaintext note should be:

```text
human selects the file in a local UI
-> tool detects candidate secret fields locally
-> human confirms each entry
-> tool writes to the chosen vault/keyring through an approved adapter
-> WOM records only refs/catalog metadata
-> human deletes or quarantines the old plaintext note
```

v0.3.22 does not implement that migration or broker. It only defines the
recommendation and compatibility boundary.

v0.3.23 adds a read-only broker request planner. See
[Credential Access Broker Plan](credential-access-broker-plan.md).

v0.3.31 adds a non-secret approval receipt preview and local writer. See
[Credential Access Approval Plan](credential-access-approval-plan.md).

v0.3.25 adds a read-only adapter readiness preview. See
[Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md).

v0.3.26 adds a read-only adapter manifest preview. See
[Credential Adapter Manifest Plan](credential-adapter-manifest-plan.md).

v0.3.27 adds a read-only adapter audit receipt preview. See
[Credential Adapter Audit Plan](credential-adapter-audit-plan.md).

v0.3.28 adds a read-only vault onboarding plan. See
[Credential Vault Onboarding Plan](credential-vault-onboarding-plan.md).

v0.3.32 adds a KeePassXC-specific command preflight after approval receipt
verification. See [Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md).

v0.3.33 adds a CLI-only KeePassXC write adapter after the same approval and
policy gates. See [Credential KeePassXC Write](credential-keepassxc-write.md).

v0.3.29 adds a read-only plaintext migration plan. See
[Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md).

v0.3.113 adds `account_recovery_codes` and `break_glass_secrets` scenario
profiles. They recommend an encrypted `secret:` entry plus independent offline
redundancy, and add explicit circular-dependency guidance without implementing
secret retrieval.

## WOM Compatibility Rules

Use:

```text
secret:keepassxc-personal-mail
secret:bitwarden-openai-api
secret:onepassword-family-login
keyring:wom-mail-access
env:WOM_OPENAI_API_KEY
imap:account:naver-personal
```

Do not use:

```text
real email addresses
real usernames
real passwords
real app passwords
real OAuth tokens
real API keys
real browser profile paths
real vault file paths
```

`account_ref` is still not a secret. It should be a non-secret account label,
such as `imap:account:personal-mail`.

## Current Closed Actions

`credential-store-recommendation` does not:

- open KeePassXC,
- open Chrome or Edge password stores,
- open Windows Credential Manager,
- read environment variables,
- ask for a master password,
- ask for an API key,
- import a plaintext note,
- write to any vault,
- call providers,
- draft zets,
- mint zets.

It is a recommendation planner, not a secret broker.
