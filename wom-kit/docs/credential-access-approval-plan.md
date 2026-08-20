# Credential Access Approval Plan

Status: v0.4.0 legacy-unbound approval metadata; writer remains non-authorizing
Date: 2026-08-15

Previous checkpoint: Status: v0.3.31 credential approval receipt writer checkpoint

This document defines the receipt preview and local receipt writer introduced
in v0.3.31. In v0.4.0 the receipt is structurally auditable metadata only: it is
`legacy_unbound`, advisory, and cannot authorize a current or future adapter.

## Short Answer

WOM should not let an AI use a credential just because a ref exists.

The historical v0.3 design recorded a human-reviewed approval receipt:

```text
credential ref exists
-> broker request is planned
-> human reviews approve_once / deny / needs_review
-> approval receipt is written by credential-access-approval --approve
-> policy-check can structurally review that legacy receipt
-> no current or future broker authority is created
```

The local writer can still record the non-secret receipt in the archive. The
receipt does not read, store, print, or retrieve the real secret value and does
not grant execution authority.

## Preview

```powershell
$env:PYTHONPATH='src'; python -m wom_kit.archive_cli credential-access-approval-plan .\my-archive `
  --credential-id cred:openai-api `
  --credential-ref secret:keepassxc-openai-api `
  --action-kind model_api_call `
  --decision approve_once `
  --dry-run `
  --format json
```

## Record A Reviewed Receipt

```powershell
$env:PYTHONPATH='src'; python -m wom_kit.archive_cli credential-access-approval .\my-archive `
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
| `approve_once` | Legacy reviewed-decision metadata for one scoped action; grants no execution authority. |
| `deny` | Legacy reviewed-decision metadata denying the requested action. |

`--approve` can record only `approve_once` or `deny`. `needs_review` remains
preview-only.

Even a structurally valid `approve_once` receipt does not grant live access or
future adapter readiness. Receipt review and policy check classify it as
`legacy_unbound`/advisory, keep `future_adapter_authorized` false, and keep
`would_allow_future_adapter_after_receipt` false.

The immutable v0.3.320 Notion recovery capability is historical evidence, not
a current product path. In v0.4.0 `notion-page-recovery --approve` returns
`compound_exact_human_approval_binding_required` before private request,
credential, provider, capability, or claim access and writes nothing. A
generic access-approval receipt is never converted into live recovery
authority.
See the [Credential Capability Contract](credential-capability-contract.md).

For KeePassXC, v0.3.32 historically added a read-only command preflight after
the policy check. See [Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md).

v0.3.33 historically added a separate CLI-only KeePassXC write adapter after
that preflight. In v0.4.0 its approval path is fixed closed before receipt,
credential, or database reads. See
[Credential KeePassXC Write](credential-keepassxc-write.md). MCP still cannot
write approval receipts or execute the adapter.

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
- [Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md),
  also requiring `--approval-receipt <path>`
- [Credential KeePassXC Write](credential-keepassxc-write.md), whose v0.4.0
  dry-run is content-free and whose approval is fixed closed before receipt,
  credential, or database reads
- [Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)
