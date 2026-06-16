# IMAP Mailbox Material Capture Approval Plan

Status: v0.3.71 approval-gated IMAP material capture approval receipt checkpoint
Date: 2026-06-16

v0.3.71 adds the local approval receipt checkpoint after the material capture
execution contract is ready and before any future command reads selected
message bodies, attachment bytes, or mail-derived text.

The command reads one existing non-secret material selection receipt from
`receipts/imap/material-selections/`, reuses the material capture execution
contract validation, and previews or writes a non-secret approval receipt under
`receipts/imap/material-capture-approvals/`.

It does not connect to IMAP and it does not read message material.

## Command

```bash
archive imap-mailbox-material-capture-approval-plan <archive-root> \
  --material-selection-receipt receipts/imap/material-selections/example.json \
  --capture-action message_body_capture \
  --decision approve_once \
  --reviewed-by human:tester \
  --dry-run \
  --format json
```

To write the receipt after local human review:

```bash
archive imap-mailbox-material-capture-approval-plan <archive-root> \
  --material-selection-receipt receipts/imap/material-selections/example.json \
  --capture-action message_body_capture \
  --decision approve_once \
  --reviewed-by human:tester \
  --approve \
  --format json
```

Aliases:

```text
imap-material-capture-approval-plan
mailbox-material-capture-approval-plan
imap-mailbox-material-capture-approval
```

Decisions:

- `needs_review`
- `approve_once`
- `deny`

Capture actions:

- `message_body_capture`
- `attachment_capture`
- `derived_text_capture`

## What It Reads

The command reads only one archive-relative JSON receipt from:

```text
receipts/imap/material-selections/
```

It reuses the material capture execution contract, which checks:

- receipt kind,
- lifecycle action,
- selection mode,
- selected one-based candidate indexes,
- selected count,
- candidate pool count,
- requested future capture action,
- redaction flags.

It does not read the original IMAP header scan execution receipt.

## What It Writes

With `--approve`, the command writes one non-secret approval receipt under:

```text
receipts/imap/material-capture-approvals/
```

The receipt records:

- decision,
- reviewer label,
- capture action,
- material selection receipt SHA-256,
- selected one-based candidate indexes,
- selected count,
- future-adapter contract summary,
- redaction and closed-action flags.

The receipt does not record the material selection receipt path, execution
receipt path, candidate refs, or message material.

## What It Never Does

The command never:

- opens an IMAP connection,
- logs into mail,
- selects or searches a mailbox,
- reads the original execution receipt,
- reads message headers again,
- reads message bodies,
- reads attachment bytes,
- creates derived text,
- reads environment variables,
- opens an OS keyring,
- opens a password manager,
- starts OAuth,
- calls providers,
- writes message material,
- echoes material selection receipt paths, execution receipt paths, candidate
  refs, usernames, passwords, email addresses, subjects, senders, recipients,
  raw UIDs, Message-ID values, attachment names, local absolute paths, tokens,
  or secret values.

## Why This Exists

The IMAP material flow now has five separate human-safe checkpoints:

```text
header scan receipt -> material selection record -> material capture request -> material capture execution contract -> material capture approval receipt
```

This command is the fifth checkpoint. It gives a future body, attachment, or
derived-text adapter a human-reviewed approval artifact to require before live
message-material reads are implemented.
