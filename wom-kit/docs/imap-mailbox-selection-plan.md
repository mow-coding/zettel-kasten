# IMAP Mailbox Selection Plan

Status: v0.3.49 read-only mailbox selection planning baseline
Date: 2026-06-16

`imap-mailbox-selection-plan` adds the read-only planning step between IMAP
adapter readiness and any future mailbox scan.

It is not an IMAP client. It does not open a mailbox, search a mailbox, list
messages, or read message headers.

## Command

```bash
archive imap-mailbox-selection-plan <archive-root> \
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
  --max-messages 100 \
  --dry-run \
  --format json
```

Aliases:

```text
imap-mailbox-message-selection-plan
mailbox-selection-plan
```

MCP:

```text
imap_mailbox_selection_plan
```

Related adapter audit receipt preview added in v0.3.50:

```text
archive imap-mailbox-adapter-audit-plan <archive-root> --dry-run
MCP: imap_mailbox_adapter_audit_plan
```

Related adapter manifest preview, schema baseline, and local write baseline added by v0.3.54:

```text
archive imap-mailbox-adapter-manifest-plan <archive-root> --dry-run
MCP: imap_mailbox_adapter_manifest_plan
```

## What It Plans

The planner composes:

- `imap-mailbox-operation-request-plan`,
- credential policy state,
- a future non-secret mailbox selection rule.

Supported selection rules:

- `newest_first`
- `unread_first`
- `since_days_window`
- `human_review_queue`

The selector is a safe label only. Do not put real email addresses, private
mailbox names, subject text, sender names, recipient values, Message-ID values,
IMAP UID values, attachment names, provider URLs, local paths, or secrets in a
selector id.

## Selection States

The JSON output returns `selection_state`:

- `needs_human_approval`
- `ready_for_future_adapter_after_approval`
- `denied_by_human_decision`
- `denied_by_policy`
- `blocked`

Top-level `ok: true` means WOM-kit safely produced the selection plan. It does
not mean WOM-kit selected a mailbox or listed messages.

`live_execution_allowed_now` remains `false`.

## What It Does Not Echo

The planner does not echo:

- email addresses,
- username values,
- exact account refs,
- exact credential refs,
- exact mailbox refs,
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
- local absolute paths,
- secret values.

Safe public labels such as `gmail`, `naver`, `generic_imap`, `newest_first`,
and `mail-selection:recent-inbox` may appear.

## Closed Actions

`imap-mailbox-selection-plan` does not:

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
- write files or receipts,
- draft zets,
- mint zets.

## Safe Workflow

```text
imap-mailbox-plan
-> credential-access-approval
-> imap-mailbox-adapter-manifest-plan
-> imap-mailbox-operation-request-plan
-> imap-mailbox-adapter-readiness-plan
-> imap-mailbox-selection-plan
-> imap-mailbox-adapter-audit-plan
-> future read-only mailbox selection adapter, not implemented in v0.3.50
-> future header-only metadata scan, not implemented in v0.3.50
-> future non-secret adapter audit receipt writer, not implemented in v0.3.50
-> future message capture with separate approval
```

For beginners: this step is like writing down "when we are allowed to open the
mailbox later, choose at most 100 recent candidate messages by this boring
rule." It still does not press the login, search, or read button.
