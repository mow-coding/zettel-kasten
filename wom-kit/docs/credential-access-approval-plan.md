# Credential Access Approval Plan

Status: v0.3.24 read-only approval receipt preview baseline
Date: 2026-06-15

This document defines the receipt preview that should exist before a future
credential access broker is allowed to use a secret.

## Short Answer

WOM should not let an AI use a credential just because a ref exists.

A future broker needs a human-reviewed approval receipt:

```text
credential ref exists
-> broker request is planned
-> human reviews approve_once / deny / needs_review
-> approval receipt is written by a future approval writer
-> broker can use the secret only inside that receipt's scope
```

v0.3.24 does not write that receipt. It only previews the receipt shape.

## Read-Only Planner

```powershell
python cli\archive.py credential-access-approval-plan .\my-archive `
  --credential-id cred:openai-api `
  --credential-ref secret:keepassxc-openai-api `
  --action-kind model_api_call `
  --decision approve_once `
  --dry-run `
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

The exact `credential_ref` value is not echoed back. The preview includes only
safe metadata such as credential id, kind, provider, purpose, ref store, and ref
prefix.

## Decisions

| Decision | Meaning |
| --- | --- |
| `needs_review` | Keep the request pending for human review. |
| `approve_once` | Future approval receipt would allow one scoped action only. |
| `deny` | Future approval receipt would deny the requested action. |

Even `approve_once` is only a preview in v0.3.24. It does not grant live access.

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

`credential-access-approval-plan` does not:

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

It is an approval receipt preview, not an approval writer.

Next layer:

- [Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)
