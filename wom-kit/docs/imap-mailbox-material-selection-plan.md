# IMAP Mailbox Material Selection Plan

Status: v0.3.67 read-only IMAP material selection planning checkpoint
Date: 2026-06-16

v0.3.67 adds the checkpoint after an IMAP header metadata scan receipt exists
and before any future command reads message bodies, attachment bytes, or
mail-derived text.

The command reads one existing non-secret execution receipt from
`receipts/imap/adapter-executions/`, validates that it is a redacted
`imap_mailbox_header_metadata_scan` receipt, and returns a plan for the next
human review lane.

It does not connect to IMAP again, and it does not read message material.

## Command

```bash
archive imap-mailbox-material-selection-plan <archive-root> \
  --execution-receipt receipts/imap/adapter-executions/example.json \
  --selection-mode body_candidates \
  --dry-run \
  --format json
```

Aliases:

```text
imap-material-selection-plan
mailbox-material-selection-plan
```

Selection modes:

- `human_review_queue`
- `body_candidates`
- `attachment_candidates`
- `derived_text_candidates`

## What It Reads

The command reads only one archive-relative JSON receipt from:

```text
receipts/imap/adapter-executions/
```

It checks:

- receipt kind,
- lifecycle action,
- execution status,
- candidate count,
- headers fetched count,
- opaque `imap-candidate:<sha256>` ref shape,
- redaction flags.

The candidate refs are validated but not echoed.

## What It Plans

The output describes:

- the selected future material lane,
- the candidate pool count,
- whether future body capture, attachment capture, or derived-text capture is
  being requested for a later approval step,
- the fact that a human review step is still required before material reads.

This is still a plan. It writes no review queue file in v0.3.67.

## What It Never Does

The command never:

- opens an IMAP connection,
- logs into mail,
- selects or searches a mailbox,
- reads message headers again,
- reads message bodies,
- reads attachment bytes,
- creates derived text,
- reads environment variables,
- opens an OS keyring,
- opens a password manager,
- starts OAuth,
- calls providers,
- writes queue files,
- echoes execution receipt paths, candidate refs, usernames, passwords, email
  addresses, subjects, senders, recipients, raw UIDs, Message-ID values,
  attachment names, local absolute paths, tokens, or secret values.

## Why This Exists

The first live IMAP header scan is intentionally narrow. The next useful step
is not broad ingestion. The next useful step is a human-guided choice:

```text
Which message candidates are allowed to become body, attachment, or
mail-derived-text work?
```

This command creates that planning checkpoint while keeping message material
closed.
