# IMAP Mailbox Adapter Audit Plan

Status: v0.3.50 read-only IMAP adapter audit receipt preview baseline
Date: 2026-06-16

`imap-mailbox-adapter-audit-plan` previews the non-secret receipt shape that a
future IMAP adapter should write after an approved mailbox operation.

It is not an IMAP client. It does not open a mailbox, search a mailbox, list
messages, read headers, or write receipts.

## Command

```bash
archive imap-mailbox-adapter-audit-plan <archive-root> \
  --adapter-id local-imap \
  --source-id imap:gmail-personal \
  --provider gmail \
  --account-ref imap:account:gmail-personal \
  --username-ref env:WOM_GMAIL_USERNAME \
  --auth-mode oauth_token_ref \
  --oauth-token-ref keyring:gmail-oauth \
  --mailbox-ref imap:mailbox:inbox \
  --credential-id cred:gmail-mail-access \
  --operation header_metadata_scan \
  --selection-rule newest_first \
  --selector-id mail-selection:recent-inbox \
  --result-status not_run \
  --dry-run \
  --format json
```

Aliases:

```text
imap-mailbox-adapter-audit
mailbox-adapter-audit-plan
```

MCP:

```text
imap_mailbox_adapter_audit_plan
```

## What It Previews

The planner composes:

- `imap-mailbox-selection-plan`,
- the IMAP operation request package,
- credential policy state,
- a future non-secret adapter audit receipt shape.

The proposed receipt path has this shape:

```text
receipts/imap/adapter-audits/<case-id>.imap-mailbox-adapter-audit.json
```

## Allowed Future Result Metadata

Future IMAP adapter audit receipts may record non-secret metadata such as:

- result status,
- adapter id,
- adapter kind,
- provider label,
- operation label,
- selection rule,
- safe selector id,
- candidate count bucket,
- duration bucket,
- error class,
- selection receipt id,
- adapter audit receipt id.

They must not record exact candidate counts by default. Use buckets so the
receipt does not leak mailbox volume details.

## What It Must Not Contain

The receipt preview must not contain:

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
`newest_first`, and `mail-selection:recent-inbox` may appear.

## Current Boundary

v0.3.50 does not write audit receipts.

It does not:

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

It is an audit receipt preview, not an adapter runner.

## Safe Workflow

```text
imap-mailbox-plan
-> credential-access-approval
-> imap-mailbox-operation-request-plan
-> imap-mailbox-adapter-readiness-plan
-> imap-mailbox-selection-plan
-> imap-mailbox-adapter-audit-plan
-> future read-only mailbox selection adapter, not implemented in v0.3.50
-> future header-only metadata scan, not implemented in v0.3.50
-> future non-secret adapter audit receipt writer, not implemented in v0.3.50
-> future message capture with separate approval
```

For beginners: this step is like designing the blank, safe receipt before
anyone is allowed to touch the real mailbox. It says what may be written down
after a future adapter runs, and it says which private mail details must stay
out of that receipt.
