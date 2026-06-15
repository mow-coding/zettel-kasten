# Credential Policy Check

Status: v0.3.32 credential policy gate plus KeePassXC preflight checkpoint
Date: 2026-06-15

v0.3.30 added the first concrete credential policy gate. v0.3.31 lets the gate
verify a written credential access approval receipt.
v0.3.32 adds a KeePassXC command preflight that must pass this gate first.

This is still read-only, but it is not only a planner. It evaluates a proposed
credential use request and returns a policy result:

- `ready_after_approval_receipt`,
- `needs_human_review`,
- `denied_by_human_decision`,
- `denied_by_policy`,
- `blocked`.

The policy gate is the layer a future live adapter must pass before it can run.

## Command

```bash
archive credential-policy-check <archive-root> \
  --credential-id cred:openai-api \
  --credential-ref secret:keepassxc-openai-api \
  --credential-kind openai_api_key \
  --provider openai \
  --action-kind plaintext_secret_migration \
  --approval-decision approve_once \
  --store-kind password_manager \
  --adapter-kind keepassxc_cli \
  --operation plaintext_secret_migration \
  --consumer wom:adapter:keepassxc \
  --reviewed-by human:tester \
  --approval-receipt receipts/credentials/access-approvals/<id>.credential-access-approval.json \
  --platform windows \
  --dry-run \
  --format json
```

Aliases:

```text
credential-access-policy-check
secret-policy-check
```

MCP tool:

```text
credential_policy_check
```

## Policy Object

The output includes a `credential_access_policy` preview with rules such as:

- secret values must never be returned to AI/chat/logs/receipts,
- exact credential refs must not be echoed in AI-visible output,
- one action requires one scoped human approval receipt,
- adapter kind must match the requested store kind,
- adapter operation must match the requested action kind,
- plaintext migration requires visible local UI and per-entry confirmation,
- browser/platform stores are login/passkey surfaces, not general API-key
  vaults.

## What Passes

A request can return `ready_after_approval_receipt` only when:

- the command is `--dry-run`,
- the credential id is a safe label,
- the approval decision is `approve_once`,
- the store kind is compatible with the adapter kind,
- the adapter supports the requested operation,
- the operation is valid for the requested action kind,
- any supplied approval receipt matches the same credential id, action, store,
  consumer, decision, and archive,
- no secret value or exact credential ref is echoed.

Even then, `live_execution_allowed_now` is still `false` in v0.3.32.

The result means:

```text
policy is ready after a written approval receipt
```

It does not mean:

```text
run the adapter now
```

## What Fails

Examples that return `denied_by_policy`:

- using a browser/platform password manager for an API-key model call,
- asking an adapter to perform an operation that does not match the action
  kind,
- using an adapter kind that does not match the store kind,
- using environment variables as a durable migration/write target.

`needs_review` returns `needs_human_review`.

`deny` returns `denied_by_human_decision`.

## Current Closed Actions

`credential-policy-check` does not:

- write an approval receipt,
- run a live adapter,
- open KeePassXC,
- open Bitwarden,
- open 1Password,
- open browser password stores,
- open Windows Credential Manager,
- open macOS Keychain,
- open Linux keyrings,
- read environment variables,
- read plaintext files,
- detect secret values,
- write vault entries,
- write keyring entries,
- call providers,
- start OAuth,
- draft zets,
- mint zets.

It is a policy gate, not a secret executor.

When `--approval-receipt` is supplied, the command reads only that
archive-relative, non-secret receipt and reports whether it was verified. It
does not read or infer the underlying secret.

## Relationship To The Credential Layers

The safe chain becomes:

```text
credential-store-recommendation
-> credential-vault-onboarding-plan
-> credential-plaintext-migration-plan
-> credential-ref-plan
-> credential-ref-inventory
-> credential-access-broker-plan
-> credential-access-approval-plan / credential-access-approval --approve
-> credential-policy-check --approval-receipt <path>
-> credential-keepassxc-command-plan --approval-receipt <path>
-> future adapter execution
-> credential-adapter-audit-plan
```

v0.3.31 connects the written approval receipt to the gate that future adapter
execution must satisfy. It still does not perform the execution.

v0.3.32 adds [Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md),
which reuses this policy gate before previewing a safe `keepassxc-cli add`
command shape. It still does not run KeePassXC.
