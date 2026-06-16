# IMAP Mailbox Material Capture Execution Contract

Status: v0.3.70 read-only IMAP material capture execution contract checkpoint
Date: 2026-06-16

v0.3.70 adds the contract checkpoint after a material capture request is valid
and before any future command reads selected message bodies, attachment bytes,
or mail-derived text.

The command reads one existing non-secret material selection receipt from
`receipts/imap/material-selections/`, reuses the material capture request
validation, and returns the future live-adapter contract for the requested
capture action.

It does not connect to IMAP and it does not read message material.

## Command

```bash
archive imap-mailbox-material-capture-execution-contract <archive-root> \
  --material-selection-receipt receipts/imap/material-selections/example.json \
  --capture-action message_body_capture \
  --dry-run \
  --format json
```

Aliases:

```text
imap-material-capture-execution-contract
mailbox-material-capture-execution-contract
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

It checks the same facts as the request-plan gate:

- receipt kind,
- lifecycle action,
- selection mode,
- selected one-based candidate indexes,
- selected count,
- candidate pool count,
- requested future capture action,
- redaction flags.

It does not read the original IMAP header scan execution receipt.

## What It Describes

The output can return
`contract_ready_for_future_material_capture_implementation`.

That means:

- the material selection receipt is valid,
- the requested capture action matches the selected future material lane,
- the future adapter contract can be used as an implementation target,
- any future live adapter would still need a separate execution approval,
- any future live adapter would still need credential policy checks.

It does not mean message material was read.

The contract names:

- future execution mode: `future_local_cli`,
- allowed future action after implementation and approval,
- required future inputs,
- non-secret output receipt shape,
- output fields that must never include secrets, message refs, paths, or
  private mail metadata.

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

The IMAP material flow now has four separate human-safe checkpoints:

```text
header scan receipt -> material selection record -> material capture request -> material capture execution contract
```

This command is the fourth checkpoint. It gives a future body, attachment, or
derived-text adapter a testable implementation contract, while still keeping
message material closed today.
