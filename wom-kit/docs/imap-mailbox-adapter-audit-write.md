# IMAP Mailbox Adapter Audit Write

Status: v0.3.56 approval-gated local audit receipt write baseline
Date: 2026-06-16

`imap-mailbox-adapter-audit-write` records one non-secret local audit receipt
for a future IMAP mailbox adapter outcome.

It is not an IMAP client. It does not open a mailbox. It is a receipt writer.

## Command

Dry-run preview:

```bash
archive imap-mailbox-adapter-audit-write <archive-root> \
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
  --reviewed-by person:me \
  --dry-run \
  --format json
```

Approved local write:

```bash
archive imap-mailbox-adapter-audit-write <archive-root> \
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
  --reviewed-by person:me \
  --approve \
  --format json
```

Alias:

```text
mailbox-adapter-audit-write
```

There is no MCP live write tool for this command.

## What It Writes

With `--approve`, WOM-kit writes exactly one new JSON receipt under:

```text
receipts/imap/adapter-audits/
```

The receipt contains safe labels only:

- audit receipt id and archive-relative receipt path,
- adapter id,
- provider label,
- operation label,
- selection rule label,
- safe selector id,
- result status,
- reviewer label and timestamp,
- closed-action flags showing that no live mail action happened.

The command refuses replay if the same audit receipt already exists.

## What It Does Not Do

The audit write command does not:

- open an IMAP connection,
- attempt login,
- select or search a mailbox,
- list candidate messages,
- read IMAP UIDs,
- read Message-ID values,
- read headers,
- read bodies,
- read attachments,
- create derived text,
- retrieve credential values,
- open a password manager, keyring, browser password store, or secret manager,
- start OAuth,
- call providers,
- send email,
- delete email,
- change flags,
- expose an MCP write tool.

## What It Does Not Echo

The command does not echo:

- email addresses,
- username values,
- exact account refs,
- exact credential refs,
- exact mailbox refs,
- IMAP host values,
- provider URLs,
- message ids,
- subjects,
- sender or recipient values,
- message headers,
- message bodies,
- attachment names,
- approval receipt paths,
- selection receipt paths,
- local absolute paths,
- tokens,
- secret values.

## Meaning

This receipt is an audit record, not permission to read mail.

A future live IMAP adapter must still verify manifest, approval, selection,
credential policy, and preflight gates before mailbox access.
