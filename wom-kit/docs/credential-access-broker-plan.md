# Credential Access Broker Plan

Status: v0.4.0 generic read-only plan; v0.3.320 Notion capability is historical evidence
Date: 2026-08-15

Previous checkpoint: Status: v0.3.23 read-only broker planning baseline

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

The generic v0.3.23 command does not implement secret retrieval. It only plans
the broker request.

Historically, v0.3.320 implemented one narrow broker boundary inside
`notion-page-recovery`. In v0.4.0 that worker's approval is fixed closed before
private request, credential, or provider reads and creates no capability or
claim. It is not exposed as a generic CLI/MCP command. See the immutable
[Credential Capability Contract](credential-capability-contract.md).

v0.3.31 historically added a non-secret approval receipt preview and local
writer. Its v0.4.0 receipts are `legacy_unbound` advisory metadata and never
authorize an adapter. See
[Credential Access Approval Plan](credential-access-approval-plan.md).

v0.3.25 adds a read-only adapter readiness preview. See
[Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md).

v0.3.32 adds a read-only KeePassXC command preflight after approval receipt
verification. See
[Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md).

v0.3.33 historically added a minimal CLI-only KeePassXC write adapter after the
same approval and policy gates. Its v0.4.0 approval path is fixed closed before
receipt, credential, or database reads. See
[Credential KeePassXC Write](credential-keepassxc-write.md).

## Read-Only Planner

```powershell
$env:PYTHONPATH='src'; python -m wom_kit.archive_cli credential-access-broker-plan .\my-archive `
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

## Historical v0.3.320 Recovery Distinction

Do not confuse the generic planner above with current live recovery. The
following describes v0.3.320 evidence only. At that checkpoint the path existed
only after `notion-page-recovery` approval, whose parent
parent mints a fresh one-use, expiring, secret-free capability bound to the
exact request, plan, reviewer, selected authenticated receipt/lifecycle scopes,
fixed read-only Notion endpoints, and bounded provider-attempt budget.

The isolated worker validates the binding, then creates an exclusive
archive-key-HMAC claim before the first native credential read. It rechecks the
claim and exact authority before each provider attempt and finalizes the claim
with content-free evidence. Any existing claim leaf permanently spends the id.
A fully verified historical local replay created no claim and performed no
credential read or provider request.

In v0.4.0 `notion-page-recovery --approve` returns
`compound_exact_human_approval_binding_required` before the private request,
credential, provider, archive, capability, or claim boundary and writes
nothing. The historical implementation does not make
`credential-access-broker-plan` live or authorize any other action or store.
