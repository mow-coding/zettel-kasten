# 2026-06-16 v0.3.62 IMAP Header Metadata Scan

## Context

Users have been waiting for IMAP progress. The previous release defined the
execution contract but still kept all live execution closed.

The next safe step is not full mail ingestion. It is a very narrow live adapter
slice: header metadata scan only, with approval and a non-secret receipt.

## Decision

Add `imap-mailbox-header-metadata-scan`.

The command supports dry-run and approve modes. Approved mode is limited to
app-password auth through `env:` refs, read-only `INBOX`, UID search, limited
header fetch, opaque candidate refs, and a non-secret execution receipt.

## Safety Boundary

The command does not return usernames, passwords, environment variable names,
exact credential refs, exact mailbox refs, IMAP hosts, raw UIDs, Message-ID
values, subjects, senders, recipients, raw headers, bodies, attachments, or
local absolute paths.

OAuth, keyring retrieval, password-manager retrieval, message capture,
attachment capture, derived-text capture, and mailbox mutations remain future
work.
