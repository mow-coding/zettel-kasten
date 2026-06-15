# IMAP Mailbox Adapter Preflight Plan

Status: v0.3.55 read-only IMAP adapter preflight baseline
Date: 2026-06-16

`imap-mailbox-adapter-preflight-plan` is the final read-only gate before a
future live IMAP adapter could be implemented or invoked.

It is not an IMAP client. It does not open a mailbox.

## Command

```bash
archive imap-mailbox-adapter-preflight-plan <archive-root> \
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
  --approval-decision approve_once \
  --approval-receipt receipts/credentials/access-approvals/<receipt>.json \
  --dry-run \
  --format json
```

Aliases:

```text
imap-mailbox-adapter-execution-preflight
mailbox-adapter-preflight
```

MCP:

```text
imap_mailbox_adapter_preflight_plan
```

## What It Composes

The preflight combines:

- `imap-mailbox-adapter-readiness-plan`,
- adapter manifest status from `config/imap-adapters/`,
- `imap-mailbox-selection-plan`,
- `imap-mailbox-adapter-audit-plan`,
- approval receipt verification through the IMAP operation request package.

`preflight_state` returns:

- `ready_for_future_adapter_after_approval`
- `blocked`

The preflight is ready only when:

- the adapter manifest status is `present_and_schema_valid`,
- the request package is `ready_for_future_adapter_after_approval`,
- the approval receipt is supplied and verified,
- the selection plan is `ready_for_future_adapter_after_approval`,
- the adapter audit receipt preview is ready.

## What It Does Not Do

The preflight does not:

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
- write files or receipts.

`live_execution_allowed_now` remains `false`.

## What It Does Not Echo

The preflight does not echo:

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
- schema validation issue values from a user-edited manifest,
- local absolute paths,
- secret values.

Safe public labels such as `gmail`, `naver`, `generic_imap`,
`header_metadata_scan`, `newest_first`, and `local-imap` may appear.

## Meaning

This command is a preflight, not execution permission.

A future live adapter must verify the same manifest, approval receipt,
selection plan, and audit boundary again at execution time.
