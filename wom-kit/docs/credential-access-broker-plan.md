# Credential Access Broker Plan

Status: v0.3.23 read-only broker planning baseline
Date: 2026-06-15

This document defines how WOM should let an AI request credential use without
showing the secret value to the AI.

## Short Answer

The desired future UX is:

```text
human asks AI to do a task
-> AI asks WOM for a credential capability
-> WOM checks policy, purpose, provider, consumer, and human approval
-> a local broker talks to the real vault/keyring/platform surface
-> the adapter uses the secret for the approved action
-> the secret value is not returned to chat
```

v0.3.23 does not implement secret retrieval. It only plans the broker request.

## Read-Only Planner

```powershell
python cli\archive.py credential-access-broker-plan .\my-archive `
  --credential-id cred:openai-api `
  --credential-ref secret:keepassxc-openai-api `
  --action-kind model_api_call `
  --store-kind password_manager `
  --dry-run `
  --format json
```

Aliases:

```text
credential-broker-plan
secret-access-broker-plan
```

MCP:

```text
credential_access_broker_plan
```

The exact `credential_ref` value is not echoed back. The planner reports only
the ref store and prefix, such as `secret:`.

## Supported Action Kinds

| Action kind | Meaning |
| --- | --- |
| `mail_source_read` | Future approved mail username/app-password/OAuth use. |
| `model_api_call` | Future approved model provider API key use. |
| `ocr_api_call` | Future approved OCR provider API key use. |
| `object_storage_request` | Future approved object storage token use. |
| `cli_token_auth` | Future approved local CLI/provider token use. |
| `browser_login_fill` | Future approved browser/platform login or passkey/autofill flow. |
| `plaintext_secret_migration` | Future approved migration from a human-selected plaintext note into a real vault/keyring. |

## Supported Store Kinds

```text
password_manager
browser_platform_manager
os_keyring
developer_secret_manager
environment
future_wallet
```

These are store classes, not implemented adapters.

## Plaintext Secret Migration Boundary

If a user has an old text file with API keys or passwords, WOM should not ask
the user to paste it into chat.

A future safe flow should be:

```text
human chooses a plaintext note through a local UI
-> local tool scans candidate fields in memory
-> human confirms each target entry
-> future adapter writes each secret to the chosen vault/keyring
-> WOM records only refs and catalog metadata
-> human separately reviews deletion or quarantine of the old plaintext note
```

v0.3.23 does not read that file, detect secrets, write a vault entry, or delete
the old note.

## Broker Rules

The broker request should include:

- credential id,
- action kind,
- provider,
- purpose,
- consumer/tool label,
- store kind,
- approval receipt requirement.

It should not include:

- real username,
- real password,
- real app password,
- real API key,
- real OAuth token,
- real browser profile path,
- real vault file path,
- real local plaintext note path.

## Current Closed Actions

`credential-access-broker-plan` does not:

- open KeePassXC,
- open Bitwarden or 1Password,
- open Chrome or Edge password stores,
- open Windows Credential Manager, macOS Keychain, or Linux keyring,
- read environment variables,
- read a plaintext secret note,
- ask for a master password,
- ask for an API key,
- write to any vault,
- call providers,
- draft zets,
- mint zets.

It is a broker contract planner, not a broker adapter.
