# IMAP Mailbox Operation Request Plan

Status: v0.3.46 read-only request package baseline
Date: 2026-06-15

`imap-mailbox-operation-request-plan` composes the safe request package before
any future IMAP mailbox adapter runs.

It is not a mailbox scan, login, OAuth flow, message capture, attachment
capture, or derived-text extraction command. It is the step that says:

```text
This is the mailbox operation being requested.
These are the mailbox source refs and credential approval gates.
Nothing live has run yet.
```

## Command

```bash
archive imap-mailbox-operation-request-plan <archive-root> \
  --source-id imap:gmail-personal \
  --provider gmail \
  --account-ref imap:account:gmail-personal \
  --username-ref env:WOM_GMAIL_USERNAME \
  --auth-mode oauth_token_ref \
  --oauth-token-ref keyring:gmail-oauth \
  --mailbox-ref imap:mailbox:inbox \
  --credential-id cred:gmail-mail-access \
  --operation header_metadata_scan \
  --max-messages 100 \
  --approval-decision needs_review \
  --dry-run \
  --format json
```

Aliases:

```text
imap-mailbox-request-plan
mailbox-operation-request-plan
```

MCP:

```text
imap_mailbox_operation_request_plan
```

Related adapter readiness check added in v0.3.47:

```text
archive imap-mailbox-adapter-readiness-plan <archive-root> --dry-run
MCP: imap_mailbox_adapter_readiness_plan
```

That v0.3.47 checkpoint still ended at a future IMAP adapter, not implemented in v0.3.47.

Related selection planning check added in v0.3.49:

```text
archive imap-mailbox-selection-plan <archive-root> --dry-run
MCP: imap_mailbox_selection_plan
```

## What It Composes

The request package reuses existing read-only gates:

- `imap-mailbox-plan`
- `credential-policy-check` for `mail_source_read`
- approval receipt verification when `approve_once` is requested

Supported future operation labels:

- `header_metadata_scan`
- `message_rfc822_capture`
- `attachment_capture`
- `derived_text_capture`

These are request labels only. v0.3.46 still does not implement the live
adapter that would perform them.

## Request States

The JSON output returns `request_state`:

- `needs_human_approval`
- `ready_for_future_adapter_after_approval`
- `denied_by_human_decision`
- `denied_by_policy`
- `blocked`

Top-level `ok: true` means the request package was safely produced and is either
waiting for human approval or has a verified approval receipt. It does not mean
that WOM-kit has read the mailbox.

`live_execution_allowed_now` remains `false`.

## Approval Receipt Rule

When `--approval-decision approve_once` is used, an
`--approval-receipt <archive-relative-path>` must be supplied and verified.

The output does not echo the approval receipt path. It only returns booleans
such as:

```text
approval_receipt_supplied
approval_receipt_verified
approval_receipt_path_echoed
future_adapter_has_verified_receipt
```

A future live IMAP adapter must verify the same receipt again before doing
anything.

## What It Does Not Echo

The planner does not echo:

- email addresses,
- username values,
- exact account refs,
- exact credential refs,
- exact mailbox refs,
- IMAP host values,
- provider URLs,
- message headers,
- message bodies,
- attachment names,
- approval receipt paths,
- local absolute paths,
- secret values.

Safe public labels such as `gmail`, `naver`, `generic_imap`,
`mail_source_read`, `keyring`, and `env` may appear.

## Closed Actions

`imap-mailbox-operation-request-plan` does not:

- open an IMAP connection,
- attempt login,
- select a mailbox,
- read message headers,
- read message bodies,
- read attachments,
- create derived text,
- send email,
- delete email,
- change message flags,
- retrieve credential values,
- open a password manager, keyring, browser password store, or secret manager,
- start OAuth,
- write files or receipts,
- draft zets,
- mint zets.

It is an approval request package for a future adapter, not the adapter itself.

## Safe Workflow

```text
imap-mailbox-plan
-> credential-access-approval
-> imap-mailbox-operation-request-plan
-> imap-mailbox-adapter-readiness-plan
-> imap-mailbox-selection-plan
-> future IMAP adapter, not implemented in v0.3.49
-> future non-secret adapter audit receipt
```

For beginners: this is like preparing a signed checklist before anyone is
allowed to open the mailbox. The checklist can say "ready after approval," but
it still does not press the login or read button.
