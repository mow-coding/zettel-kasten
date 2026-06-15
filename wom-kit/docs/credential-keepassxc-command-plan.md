# Credential KeePassXC Command Plan

Status: v0.3.32 read-only KeePassXC command preflight
Date: 2026-06-15

This document defines the first KeePassXC-specific command planning layer.

It does not execute KeePassXC. It only verifies that a written credential access
approval receipt exists, reuses `credential-policy-check`, and returns a safe
`keepassxc-cli add` command shape with placeholders.

## Why This Exists

The user may want to move a secret from a human-selected plaintext note into a
real password manager.

WOM should not become that password manager, and AI should not receive the
secret value in chat.

The safe chain is:

```text
human chooses external vault
-> credential ref and migration are planned
-> human writes one scoped approval receipt
-> policy check verifies the receipt
-> KeePassXC command plan previews the local command shape
-> CLI-only KeePassXC write adapter may execute separately
-> execution receipt records non-secret result metadata
```

## Command

```bash
archive credential-keepassxc-command-plan <archive-root> \
  --credential-id cred:openai-api \
  --credential-ref secret:keepassxc-openai-api \
  --credential-kind openai_api_key \
  --provider openai \
  --action-kind plaintext_secret_migration \
  --operation plaintext_secret_migration \
  --approval-receipt receipts/credentials/access-approvals/<id>.credential-access-approval.json \
  --entry-label openai-api \
  --group-label wom-secrets \
  --database-ref keepassxc:personal-vault \
  --consumer wom:adapter:keepassxc \
  --reviewed-by human:me \
  --dry-run \
  --format json
```

Aliases:

```text
keepassxc-command-plan
credential-keepassxc-write-plan
```

MCP tool:

```text
credential_keepassxc_command_plan
```

## Receipt Requirement

`--approval-receipt` is required.

If it is missing, the JSON blockers include `approval_receipt is required`.

The receipt must:

- live under `receipts/credentials/access-approvals/`,
- be a `credential_access_approval` receipt,
- belong to the same archive,
- match the same credential id,
- match `action_kind`,
- match `store_kind=password_manager`,
- match `consumer`,
- record `decision=approve_once`,
- include no secret-like or private locator material.

If the receipt does not verify, the command plan is blocked.

## Command Shape

KeePassXC documents a command-line tool, `keepassxc-cli`, for direct terminal
access to a database. The man page shape used here is:

```text
keepassxc-cli add [options] <database> <entry>
```

The preview uses:

```text
keepassxc-cli add --password-prompt <database.kdbx selected by human outside WOM> <safe-entry-label>
```

`--password-prompt` means the entry password should be typed into the local CLI
prompt, not passed as an argv value, not piped through stdin, and not pasted
into chat.

References:

- [KeePassXC User Guide](https://keepassxc.org/docs/KeePassXC_UserGuide)
- [keepassxc-cli man page](https://man.archlinux.org/man/keepassxc-cli.1.en)

## Safe Inputs

The command accepts only safe labels:

- `credential_id`,
- `entry_label`,
- optional `group_label`,
- optional `database_ref`,
- `consumer`,
- `reviewed_by`.

`database_ref` is a label, not the `.kdbx` path.

Do not pass:

- a vault file path,
- a username,
- an email address,
- a provider URL,
- a password,
- an app password,
- an OAuth token,
- an API key,
- a plaintext secret file path.

## Current Closed Actions

`credential-keepassxc-command-plan` does not:

- run `keepassxc-cli`,
- open KeePassXC,
- open a password manager,
- read a KeePassXC database path,
- read a database password,
- read a plaintext file,
- detect secret values,
- write a vault entry,
- write a keyring entry,
- pipe secrets to stdin,
- pass secrets through argv,
- call providers,
- start OAuth,
- write files.

It is a command preflight, not a vault adapter.

v0.3.33 adds a separate CLI-only live write adapter. See
[Credential KeePassXC Write](credential-keepassxc-write.md). MCP still exposes
only the read-only preflight.

## Output Guarantees

The output keeps:

- `live_execution_allowed_now: false`,
- `command_execution_implemented: false`,
- `secret_value_in_argv: false`,
- `secret_value_in_stdin: false`,
- `database_path_included: false`,
- `exact_credential_ref_echoed: false`,
- `would_change: []`.

## Relationship To The Credential Layers

The safe chain is now:

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
-> credential-keepassxc-write --approval-receipt <path> --approve
-> non-secret KeePassXC write execution receipt
```

v0.3.32 adds the KeePassXC-specific command preflight. It still does not
perform the execution.

v0.3.33 adds [Credential KeePassXC Write](credential-keepassxc-write.md), a
separate CLI-only adapter that can execute `keepassxc-cli add` after the same
receipt and policy gates pass.
