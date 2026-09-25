# IMAP Mailbox Adapter Execution Contract

Status: removed in v0.4.44 (superseded)

`archive imap-mailbox-adapter-execution-contract` no longer exists. It was one step of the v0.3.19 to v0.3.72
plan toward a future IMAP adapter that would scan headers, select messages and
then capture bodies and attachments. That end-to-end goal now runs as one
command, so the whole chain was removed (owner decision 2026-09-25: a feature
replaced by a better one is removed, not kept closed).

Use instead:

1. `archive add-source <archive-root> ... --type imap_mailbox` to
   register the mailbox.
2. `archive imap-mailbox-message-fetch <archive-root> --source-id <id>
   --batch-id <id> --imap-host <host> --username-ref env:NAME
   --app-password-ref env:NAME --dry-run`, then `--approve`.
3. `archive source-intake-batch <archive-root> --manifest <written request>`
   to capture the fetched `.eml` files as objets.

See [IMAP Mailbox Source](imap-mailbox-source.md). Receipts written by the
removed commands stay readable as plain JSON; nothing reads or rewrites them.
