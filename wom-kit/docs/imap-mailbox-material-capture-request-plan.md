# IMAP Mailbox Material Capture Request Plan

Status: v0.3.69 read-only IMAP material capture request planning checkpoint
Date: 2026-06-16

v0.3.69 adds the checkpoint after a human-reviewed IMAP material selection
receipt exists and before any future command reads message bodies, attachment
bytes, or mail-derived text.

The command reads one existing non-secret material selection receipt from
`receipts/imap/material-selections/`, validates that the selected lane permits
the requested future capture action, and returns the approval requirements for a
future live adapter.

It does not connect to IMAP and it does not read message material.

## Command

```bash
archive imap-mailbox-material-capture-request-plan <archive-root> \
  --material-selection-receipt receipts/imap/material-selections/example.json \
  --capture-action message_body_capture \
  --dry-run \
  --format json
```

Aliases:

```text
imap-material-capture-request-plan
mailbox-material-capture-request-plan
```

Capture actions:

- `message_body_capture`
- `attachment_capture`
- `derived_text_capture`

## What It Reads

The command reads only one archive-relative JSON receipt from:

```text
receipts/imap/material-selections/
```

It checks:

- receipt kind,
- lifecycle action,
- selection mode,
- selected one-based candidate indexes,
- selected count,
- candidate pool count,
- requested future capture action,
- redaction flags.

It does not read the original IMAP header scan execution receipt.

## What It Plans

The output says whether the request is
`ready_for_future_material_capture_after_approval`.

That means:

- the material selection receipt is valid,
- the requested capture action matches the selected future material lane,
- a future adapter would still need a separate execution approval,
- a future adapter would still need credential policy checks.

It does not mean message material was read.

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
- writes files,
- echoes material selection receipt paths, execution receipt paths, candidate
  refs, usernames, passwords, email addresses, subjects, senders, recipients,
  raw UIDs, Message-ID values, attachment names, local absolute paths, tokens,
  or secret values.

## Why This Exists

The IMAP flow now has three separate human-safe checkpoints:

```text
header scan receipt -> material selection record -> material capture request
```

This command is the third checkpoint. It lets a future body/attachment/derived
text adapter know whether it has enough reviewed metadata to ask for a real
execution approval, while still keeping message material closed today.
