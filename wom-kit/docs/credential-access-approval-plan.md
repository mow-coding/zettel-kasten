# Credential Access Approval Plan

Status: v0.3.31 credential approval receipt writer checkpoint
Date: 2026-06-15

This document defines the receipt preview and local receipt writer that must
exist before a future credential access broker is allowed to use a secret.

## Short Answer

WOM should not let an AI use a credential just because a ref exists.

A future broker needs a human-reviewed approval receipt:

```text
credential ref exists
-> broker request is planned
-> human reviews approve_once / deny / needs_review
-> approval receipt is written by credential-access-approval --approve
-> policy-check can verify that receipt
-> future broker can use the secret only inside that receipt's scope
```

v0.3.31 can write the non-secret approval receipt into the archive. It still
does not read, store, print, or retrieve the real secret value.

## Preview

```powershell
python cli\archive.py credential-access-approval-plan .\my-archive `
  --credential-id cred:openai-api `
  --credential-ref secret:keepassxc-openai-api `
  --action-kind model_api_call `
  --decision approve_once `
  --dry-run `
  --format json
```

## Record A Reviewed Receipt

```powershell
python cli\archive.py credential-access-approval .\my-archive `
  --credential-id cred:openai-api `
  --credential-ref secret:keepassxc-openai-api `
  --action-kind plaintext_secret_migration `
  --decision approve_once `
  --store-kind password_manager `
  --consumer wom:adapter:keepassxc `
  --reviewed-by human:me `
  --approve `
  --format json
```

Aliases:

```text
credential-access-approval
secret-access-approval-plan
```

MCP:

```text
credential_access_approval_plan
```

The MCP tool remains preview-only. Use the local CLI for `--approve`.

The exact `credential_ref` value is not echoed back. The preview includes only
safe metadata such as credential id, kind, provider, purpose, ref store, and ref
prefix.

## Decisions

| Decision | Meaning |
| --- | --- |
| `needs_review` | Keep the request pending for human review. |
| `approve_once` | Future approval receipt would allow one scoped action only. |
| `deny` | Future approval receipt would deny the requested action. |

`--approve` can record only `approve_once` or `deny`. `needs_review` remains
preview-only.

Even a recorded `approve_once` receipt does not grant live access by itself. A
future adapter still needs a policy check and its own non-echoing execution
gate.

## Receipt Preview Rules

The preview may include:

- credential id,
- credential kind,
- provider,
- purpose,
- ref store and prefix,
- action kind,
- store kind,
- consumer/tool label,
- reviewer label,
- decision,
- proposed receipt path,
- non-secret result metadata allowed for the future action.

The preview must not include:

- secret value,
- exact credential ref value,
- username,
- email address,
- app password,
- OAuth token,
- API key,
- local file path,
- browser profile path,
- provider URL.

## Current Closed Actions

`credential-access-approval-plan --dry-run` does not:

- write an approval receipt,
- grant live approval,
- open a password manager,
- open a browser password store,
- open an OS keyring,
- read environment variables,
- read a plaintext secret note,
- call providers,
- draft zets,
- mint zets.

`credential-access-approval --approve` writes one archive-internal JSON receipt
under `receipts/credentials/access-approvals/`. It still does not:

- read the credential value,
- write a vault entry,
- open a password manager,
- open a keyring,
- read a plaintext note,
- call providers,
- grant live adapter execution.

Next layer:

- [Credential Policy Check](credential-policy-check.md), optionally with
  `--approval-receipt <path>`
- [Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)
