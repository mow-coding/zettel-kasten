# Credential KeePassXC Write

Status: v0.3.33 CLI-only KeePassXC write adapter
Date: 2026-06-15

This document defines the first live credential write adapter in WOM-kit.

It is intentionally narrow:

- CLI-only,
- approval-receipt-gated,
- KeePassXC-only,
- `keepassxc-cli add` only,
- one approval receipt can produce only one execution receipt,
- no secret value, vault password, database path, exact credential ref,
  username, email, token, provider URL, or raw adapter output is written to WOM
  output or receipts.

MCP remains preview-only. There is no live MCP tool for this command.

## Command

Dry-run:

```bash
archive credential-keepassxc-write <archive-root> \
  --credential-id cred:openai-api \
  --credential-ref secret:keepassxc-openai-api \
  --credential-kind openai_api_key \
  --provider openai \
  --action-kind plaintext_secret_migration \
  --operation write_new_secret \
  --approval-receipt receipts/credentials/access-approvals/<id>.credential-access-approval.json \
  --entry-label openai-api \
  --group-label wom-secrets \
  --database-ref keepassxc:personal-vault \
  --consumer wom:adapter:keepassxc \
  --reviewed-by human:me \
  --dry-run \
  --format json
```

Approved local execution:

```bash
archive credential-keepassxc-write <archive-root> \
  --credential-id cred:openai-api \
  --action-kind plaintext_secret_migration \
  --operation write_new_secret \
  --approval-receipt receipts/credentials/access-approvals/<id>.credential-access-approval.json \
  --entry-label openai-api \
  --group-label wom-secrets \
  --database-ref keepassxc:personal-vault \
  --database-path <local-human-selected-database.kdbx> \
  --consumer wom:adapter:keepassxc \
  --reviewed-by human:me \
  --approve \
  --format json
```

Alias:

```text
keepassxc-write
```

There is no MCP live execution tool.

## Execution Chain

The intended chain is:

```text
credential-access-approval --approve
-> credential-policy-check --approval-receipt <path> --dry-run
-> credential-keepassxc-command-plan --approval-receipt <path> --dry-run
-> credential-keepassxc-write --approval-receipt <path> --approve
-> non-secret KeePassXC write execution receipt
```

`credential-keepassxc-write` reuses the same receipt verification and policy
gate as the command preflight before it executes.

## What It Executes

KeePassXC documents this CLI shape:

```text
keepassxc-cli add [options] <database> <entry>
```

WOM-kit invokes the local shape:

```text
keepassxc-cli add --password-prompt <local database path> <safe entry label>
```

`--password-prompt` means the new entry password is typed into the local
KeePassXC CLI prompt. WOM-kit does not accept the secret value as an argument
and does not pipe it through stdin.

References:

- [KeePassXC User Guide](https://keepassxc.org/docs/KeePassXC_UserGuide)
- [keepassxc-cli man page](https://man.archlinux.org/man/keepassxc-cli.1.en)

## Required Human Inputs

For `--approve`, the human operator must provide:

- an archive-relative approval receipt path,
- a safe entry label,
- an optional safe group label,
- a safe database ref label,
- a local `.kdbx` database path,
- the KeePassXC database unlock secret through the local CLI prompt,
- the new entry password through the local CLI prompt.

The `.kdbx` path is used only for the local subprocess call. It is not echoed
in JSON, not written to the execution receipt, and must be outside the WOM
archive root.

## Execution Receipt

On approved execution, WOM-kit writes one non-secret receipt:

```text
receipts/credentials/keepassxc-writes/<id>.credential-keepassxc-write.json
```

The receipt records:

- approval receipt path,
- credential id,
- credential kind/provider if supplied,
- adapter kind,
- operation,
- action kind,
- consumer,
- safe entry/group labels,
- execution status,
- command shape with placeholders,
- whether raw stdout/stderr were included.

The receipt does not record:

- secret value,
- database password,
- `.kdbx` path,
- exact credential ref value,
- username,
- email address,
- token,
- provider URL,
- raw adapter stdout/stderr.

If the execution receipt already exists for the same approval receipt and
entry target, replay is blocked. The human must create a new approval receipt
for another attempt.

## Current Closed Actions

`credential-keepassxc-write --approve` still does not:

- return a secret to AI,
- read a plaintext secret note,
- detect secret values,
- accept a secret value through argv,
- pipe a secret value through stdin,
- expose a live MCP tool,
- read OS keyrings,
- read browser password stores,
- call providers,
- start OAuth,
- call OpenAI or paid OCR providers.

It does execute `keepassxc-cli add` locally and can modify the human-selected
KeePassXC database.

## Output Guarantees

The output keeps:

- `mcp_live_tool_exposed: false`,
- `database_path_included: false`,
- `database_paths_echoed: false`,
- `secret_values_echoed: false`,
- `credential_ref_values_echoed: false`,
- `raw_adapter_output_echoed: false`,
- `secret_value_return_to_ai: false`.

## Relationship To The Credential Layers

v0.3.33 is the first end-to-end credential execution path:

```text
approval receipt writer
-> policy gate
-> KeePassXC command preflight
-> CLI-only KeePassXC write adapter
-> execution receipt
```

It does not implement secret retrieval, model API calls, OCR API calls, OS
keyring writes, browser password-store access, OAuth, or provider integrations.
