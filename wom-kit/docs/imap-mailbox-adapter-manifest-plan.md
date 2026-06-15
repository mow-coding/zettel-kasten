# IMAP Mailbox Adapter Manifest Plan

Status: v0.3.54 read-only IMAP adapter manifest preview plus schema baseline
Date: 2026-06-16

`imap-mailbox-adapter-manifest-plan` previews the non-secret manifest shape for
a future IMAP mailbox adapter and validates that preview against a JSON Schema.

It is not an IMAP client. It does not write a manifest, open a mailbox, search
a mailbox, list messages, read headers, or write receipts.

## Command

```bash
archive imap-mailbox-adapter-manifest-plan <archive-root> \
  --adapter-id local-imap \
  --provider gmail \
  --provider naver \
  --operation header_metadata_scan \
  --selection-rule newest_first \
  --selection-rule unread_first \
  --dry-run \
  --format json
```

Aliases:

```text
imap-mailbox-adapter-manifest
mailbox-adapter-manifest-plan
```

MCP:

```text
imap_mailbox_adapter_manifest_plan
```

## What It Previews

The planner emits:

- a proposed archive-relative manifest path,
- a `manifest_preview` object,
- supported provider labels,
- supported operation labels,
- supported selection rules,
- required approval and audit boundaries,
- privacy contract,
- closed actions,
- schema validation status.

The proposed path has this shape:

```text
config/imap-adapters/<adapter-id>.imap-mailbox-adapter.json
```

The preview validates against this schema:

```text
imap-mailbox-adapter-manifest.schema.json
```

## Manifest Shape

The manifest declares:

- adapter id,
- adapter kind,
- adapter family,
- platform,
- consumer label,
- supported providers,
- supported operations,
- supported selection rules,
- required source/request/selection/approval/audit boundaries,
- privacy contract,
- closed actions.

## What It Must Not Contain

The manifest preview must not contain:

- email addresses,
- username values,
- exact account refs,
- exact credential refs,
- exact mailbox refs,
- real mailbox names,
- IMAP host values,
- provider URLs,
- IMAP UIDs,
- Message-ID values,
- subjects,
- sender or recipient values,
- message headers,
- message bodies,
- attachment names,
- approval receipt paths,
- selection receipt paths,
- local absolute paths,
- tokens,
- passwords,
- secret values.

Safe public labels such as `gmail`, `naver`, `generic_imap`, `local-imap`,
`header_metadata_scan`, and `newest_first` may appear.

## Current Boundary

This planner does not write IMAP adapter manifests. v0.3.54 adds a separate
approval-gated write command:

```text
imap-mailbox-adapter-manifest-write
```

It does not:

- write a manifest,
- execute a live adapter,
- open an IMAP connection,
- attempt login,
- select a mailbox,
- search a mailbox,
- list candidate messages,
- read IMAP UIDs,
- read Message-ID values,
- read message headers,
- read message bodies,
- read attachments,
- create derived text,
- retrieve credential values,
- open a password manager, keyring, browser password store, or secret manager,
- start OAuth,
- call providers,
- write files or receipts,
- draft zets,
- mint zets.

It is a manifest preview, not a manifest writer or adapter runner.

## Safe Workflow

```text
imap-mailbox-plan
-> imap-mailbox-adapter-manifest-plan
-> credential-access-approval
-> imap-mailbox-operation-request-plan
-> imap-mailbox-adapter-readiness-plan
-> imap-mailbox-selection-plan
-> imap-mailbox-adapter-audit-plan
-> imap-mailbox-adapter-manifest-write
-> future read-only mailbox selection adapter, not implemented in v0.3.54
-> future header-only metadata scan, not implemented in v0.3.54
-> future non-secret adapter audit receipt writer, not implemented in v0.3.54
-> future message capture with separate approval
```

For beginners: this step is like writing the adapter's job description before
letting it work. It says which mail providers and operations the adapter may
claim to support, and it says which private mail details must never appear in
that declaration.
