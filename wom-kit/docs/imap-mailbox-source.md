# IMAP Mailbox Source

Status: v0.3.19 read-only source planning baseline
Date: 2026-06-14

This document defines the first WOM-kit boundary for treating email as a source
world.

Email is often primary evidence: decisions, receipts, attachments, notices, and
conversation trails arrive there before they become zets. The goal is not to let
an AI roam through a mailbox. The goal is to let a human register a mailbox
source safely, then later approve narrow reads and captures.

## Current Behavior

v0.3.19 adds the source type:

```text
imap_mailbox
```

It also adds:

```powershell
python cli\archive.py imap-mailbox-plan .\my-archive `
  --source-id imap:gmail-personal `
  --provider gmail `
  --account-ref imap:account:gmail-personal `
  --username-ref env:WOM_GMAIL_USERNAME `
  --auth-mode oauth_token_ref `
  --oauth-token-ref keyring:gmail-oauth `
  --dry-run `
  --format json
```

and the matching MCP tool:

```text
imap_mailbox_plan
```

Both are dry-run only. They write no files, open no network connection, perform
no login, read no message headers, read no message bodies, read no attachments,
send no email, delete no email, and change no message flags.

v0.3.46 adds a second dry-run step for the next gate:

```powershell
python cli\archive.py imap-mailbox-operation-request-plan .\my-archive `
  --source-id imap:gmail-personal `
  --provider gmail `
  --account-ref imap:account:gmail-personal `
  --username-ref env:WOM_GMAIL_USERNAME `
  --auth-mode oauth_token_ref `
  --oauth-token-ref keyring:gmail-oauth `
  --mailbox-ref imap:mailbox:inbox `
  --credential-id cred:gmail-mail-access `
  --operation header_metadata_scan `
  --approval-decision needs_review `
  --dry-run `
  --format json
```

and the matching MCP tool:

```text
imap_mailbox_operation_request_plan
```

This composes the mailbox source plan with `credential-policy-check` for
`mail_source_read`. It is still read-only: it does not connect, login, read
headers, read bodies, read attachments, retrieve secrets, start OAuth, or write
files.

v0.3.47 adds a read-only adapter readiness step:

```powershell
python cli\archive.py imap-mailbox-adapter-readiness-plan .\my-archive `
  --source-id imap:gmail-personal `
  --provider gmail `
  --account-ref imap:account:gmail-personal `
  --username-ref env:WOM_GMAIL_USERNAME `
  --auth-mode oauth_token_ref `
  --oauth-token-ref keyring:gmail-oauth `
  --mailbox-ref imap:mailbox:inbox `
  --credential-id cred:gmail-mail-access `
  --operation header_metadata_scan `
  --dry-run `
  --format json
```

and the matching MCP tool:

```text
imap_mailbox_adapter_readiness_plan
```

This checks the source plan, operation request package, and local Python module
readiness for a future adapter. It still opens no IMAP connection and reads no
mail.

v0.3.49 adds a read-only mailbox selection planning step:

```powershell
python cli\archive.py imap-mailbox-selection-plan .\my-archive `
  --source-id imap:gmail-personal `
  --provider gmail `
  --account-ref imap:account:gmail-personal `
  --username-ref env:WOM_GMAIL_USERNAME `
  --auth-mode oauth_token_ref `
  --oauth-token-ref keyring:gmail-oauth `
  --mailbox-ref imap:mailbox:inbox `
  --credential-id cred:gmail-mail-access `
  --operation header_metadata_scan `
  --selection-rule newest_first `
  --selector-id mail-selection:recent-inbox `
  --dry-run `
  --format json
```

and the matching MCP tool:

```text
imap_mailbox_selection_plan
```

This plans how a future adapter may choose candidate messages without listing
message ids, subjects, senders, headers, bodies, or attachments now.

## Provider Presets

The planning command is provider-neutral. It currently recognizes:

```text
gmail
naver
generic_imap
```

`gmail` defaults to:

```text
imap.gmail.com
993
SSL required
```

`naver` defaults to:

```text
imap.naver.com
993
SSL required
```

`generic_imap` requires the operator to provide `--imap-host`.

The command records provider policy notes, but it does not verify account
settings. Provider rules can change, so live setup must still follow current
provider documentation:

- Gmail IMAP user settings:
  <https://support.google.com/mail/answer/78892>
- Gmail IMAP/SMTP developer guidance:
  <https://developers.google.com/workspace/gmail/imap/imap-smtp>
- Google Workspace transition guidance away from less-secure app access:
  <https://knowledge.workspace.google.com/admin/sync/transition-from-less-secure-apps-to-oauth>
- Naver IMAP/SMTP settings:
  <https://help.naver.com/service/30029/contents/21344?lang=ko&osType=COMMONOS>
- Naver application password guidance:
  <https://help.naver.com/service/5640/contents/8584?lang=ko>

## Credential Refs Only

Do not pass real emails, usernames, app passwords, OAuth tokens, URLs, or local
paths.

Use references such as:

```text
env:WOM_GMAIL_USERNAME
keyring:gmail-oauth
secret:naver-app-password
wallet:mail-oauth-token
```

Account and mailbox labels are also references:

```text
imap:account:gmail-personal
imap:mailbox:inbox
```

These labels are intentionally boring. They let the archive talk about a mailbox
without publishing the human's actual email address, folder names, provider URL,
token, or local machine path.

## Registering The Source

After the plan is reviewed, the source type can be registered with the existing
source registration flow:

```powershell
python cli\archive.py add-source .\my-archive `
  --source-id imap:gmail-personal `
  --type imap_mailbox `
  --root-ref imap:account:gmail-personal `
  --approve `
  --reviewed-by person:me
```

Registration still does not connect to IMAP. In v0.3.19, `scan-source` fails
closed for `imap_mailbox` and tells the operator to run `imap-mailbox-plan`
first.

## Future Workflow

The intended sequence is:

1. Plan the mailbox source with refs only.
2. Register the `imap_mailbox` source after human review.
3. Prepare an operation request package with
   `imap-mailbox-operation-request-plan`.
4. Check adapter readiness with `imap-mailbox-adapter-readiness-plan`.
5. Plan a future mailbox selection rule with `imap-mailbox-selection-plan`.
6. Add a future header-only dry-run scan that selects the mailbox read-only and
   fetches safe message metadata only.
7. Add a future approved fetch that preserves each selected RFC822 message as a
   `.eml` source objet.
8. Add future MIME attachment capture as separate objets.
9. Add future derived-text extraction from `text/plain` and reviewed `text/html`
   parts.

Each later phase needs its own approval and privacy boundary. v0.3.49 can now
package the approval request, summarize adapter readiness, and plan a mailbox
selection rule, but it still does not implement reads, searches, message lists,
or captures.

## Closed Actions

v0.3.19 does not:

- ask the user for secrets in chat,
- store credentials in Git,
- start OAuth,
- connect to IMAP,
- login to Gmail, Naver, or a generic server,
- list message headers,
- read message bodies,
- read attachments,
- send email through SMTP,
- delete email,
- mark email read or unread,
- capture `.eml` files,
- derive text from messages,
- draft zets from email,
- mint zets from email.

The mail source is now a safe shape in the archive control plane.

Actual mail reading remains future, approval-gated work.
