# Credential KeePassXC Write

Status: v0.4.0 dry-run-only KeePassXC command preview; write fixed closed
Date: 2026-06-15

This document preserves the historical v0.3.33 adapter contract and the current
v0.4.0 boundary. Only dry-run is operational now. Approval returns
`compound_exact_human_approval_binding_required` before approval-receipt,
credential, database, provider, or target reads; it never invokes KeePassXC and
writes no receipt.

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

Alias:

```text
keepassxc-write
```

There is no MCP live execution tool.

## Execution Chain

The current safe chain stops at preview:

```text
credential-access-approval metadata receipt (legacy, advisory only)
-> credential-policy-check --approval-receipt <path> --dry-run
-> credential-keepassxc-command-plan --approval-receipt <path> --dry-run
-> credential-keepassxc-write --dry-run
-> stop; no vault or execution receipt write in v0.4.0
```

Legacy receipt verification is structural and `legacy_unbound`/advisory only.
`would_allow_future_adapter_after_receipt` remains false and the write command
does not execute.

## Historical Execution Contract

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

The historical v0.3 writer required:

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

Historical v0.3 approved execution wrote one non-secret receipt; v0.4.0 does
not create it:

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

Historical replay evidence remains auditable but grants no current execution
authority.

## Current Closed Actions

In v0.4.0 `credential-keepassxc-write` does not:

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

Historical v0.3 approved execution could run `keepassxc-cli add` locally and
modify the human-selected KeePassXC database. v0.4.0 never invokes it.

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

The v0.3.33 historical path was:

```text
legacy approval receipt writer
-> policy gate
-> KeePassXC command preflight
-> CLI-only KeePassXC write adapter
-> execution receipt
```

In v0.4.0 the chain stops at content-free preflight. It implements no secret
retrieval, vault write, execution receipt, model/OCR call, OS keyring write,
browser password-store access, OAuth, or provider integration.
