# IMAP Mailbox Adapter Readiness Plan

Status: v0.3.47 read-only adapter readiness baseline
Date: 2026-06-15

`imap-mailbox-adapter-readiness-plan` checks whether WOM-kit has the local
planning pieces needed before a future IMAP mailbox adapter can be implemented
or invoked.

It is not an IMAP client. It does not open a mailbox.

## Command

```bash
archive imap-mailbox-adapter-readiness-plan <archive-root> \
  --source-id imap:gmail-personal \
  --provider gmail \
  --account-ref imap:account:gmail-personal \
  --username-ref env:WOM_GMAIL_USERNAME \
  --auth-mode oauth_token_ref \
  --oauth-token-ref keyring:gmail-oauth \
  --mailbox-ref imap:mailbox:inbox \
  --credential-id cred:gmail-mail-access \
  --operation header_metadata_scan \
  --dry-run \
  --format json
```

Aliases:

```text
imap-mailbox-adapter-plan
mailbox-adapter-readiness
```

MCP:

```text
imap_mailbox_adapter_readiness_plan
```

Related request package:

```text
archive imap-mailbox-operation-request-plan <archive-root> --dry-run
MCP: imap_mailbox_operation_request_plan
```

Related adapter manifest preview:

```text
archive imap-mailbox-adapter-manifest-plan <archive-root> --dry-run
MCP: imap_mailbox_adapter_manifest_plan
```

Related mailbox selection plan:

```text
archive imap-mailbox-selection-plan <archive-root> --dry-run
MCP: imap_mailbox_selection_plan
```

Related adapter audit receipt preview:

```text
archive imap-mailbox-adapter-audit-plan <archive-root> --dry-run
MCP: imap_mailbox_adapter_audit_plan
```

## What It Checks

The planner composes the existing read-only request package and adds a local
runtime readiness summary.

It checks:

- whether the IMAP source refs can pass `imap-mailbox-plan`,
- whether `imap-mailbox-operation-request-plan` can build a request package,
- whether the requested operation label is supported,
- whether the Python runtime has the standard modules expected by a future
  adapter, currently `imaplib` and `email`,
- which approval and adapter-manifest gates are still required.

Supported future operation labels:

- `header_metadata_scan`
- `message_rfc822_capture`
- `attachment_capture`
- `derived_text_capture`

These are readiness labels only. v0.3.47 still does not implement the live
adapter that would perform them.

## Readiness States

The JSON output returns `readiness_state`:

- `ready_for_request_package`
- `ready_for_future_adapter_after_approval`
- `denied_by_human_decision`
- `denied_by_policy`
- `blocked`

Top-level `ok: true` means the readiness planner could safely produce the
adapter-readiness summary. It does not mean WOM-kit has connected to the
mailbox.

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
- message headers,
- message bodies,
- attachment names,
- approval receipt paths,
- local absolute paths,
- secret values.

Safe public labels such as `gmail`, `naver`, `generic_imap`, `imaplib`,
`email`, `keyring`, and `env` may appear.

## Required Gates

Before any future live adapter can run, WOM still needs:

- `imap-mailbox-plan`,
- `imap-mailbox-operation-request-plan`,
- `credential-policy-check`,
- a human approval receipt,
- a credential adapter manifest,
- an IMAP adapter manifest,
- `imap-mailbox-adapter-manifest-plan`,
- a read-only mailbox selection rule,
- `imap-mailbox-selection-plan`,
- `imap-mailbox-adapter-audit-plan`,
- a non-secret adapter audit receipt after execution.

## Closed Actions

`imap-mailbox-adapter-readiness-plan` does not:

- open an IMAP connection,
- attempt login,
- select a mailbox,
- read message headers,
- read message bodies,
- read attachments,
- create derived text,
- retrieve credential values,
- open a password manager, keyring, browser password store, or secret manager,
- start OAuth,
- send email,
- delete email,
- change message flags,
- write files or receipts,
- draft zets,
- mint zets.

It is a readiness planner, not a mailbox adapter.
