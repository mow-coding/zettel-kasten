# IMAP Mailbox Material Capture Approval Audit

Status: v0.3.72 read-only IMAP material capture approval audit checkpoint
Date: 2026-06-16

v0.3.72 adds a read-only audit checkpoint for material capture approval
receipts. It verifies that one approval receipt matches one material selection
receipt and the expected future capture action before any live adapter is
allowed to rely on that approval.

The command reads one non-secret material selection receipt and one non-secret
material capture approval receipt. It does not connect to IMAP and it does not
read message material.

## Command

```bash
archive imap-mailbox-material-capture-approval-audit <archive-root> \
  --material-selection-receipt receipts/imap/material-selections/example.json \
  --approval-receipt receipts/imap/material-capture-approvals/example.json \
  --capture-action message_body_capture \
  --expected-decision approve_once \
  --dry-run \
  --format json
```

Aliases:

```text
imap-material-capture-approval-audit
mailbox-material-capture-approval-audit
```

Expected decisions:

- `approve_once`
- `deny`
- `needs_review`

For future live material capture, the expected decision should be
`approve_once`. A `needs_review` receipt is never treated as live-ready.

## What It Reads

The command reads only:

```text
receipts/imap/material-selections/*.json
receipts/imap/material-capture-approvals/*.json
```

It checks:

- approval receipt kind,
- lifecycle action,
- schema version,
- archive id,
- expected decision,
- material selection receipt SHA-256,
- selected one-based candidate indexes,
- selected count,
- candidate pool count,
- selection mode,
- capture action,
- future-adapter action flags,
- redaction flags,
- closed-action flags.

It does not read the original IMAP header scan execution receipt.

## What It Returns

When the approval receipt matches the material selection receipt and expected
decision, the command returns:

```text
approval_receipt_verified_for_future_material_capture
```

It also returns whether future capture is authorized. That field is true only
when the audited receipt records `approve_once` and all checks pass.

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
- echoes approval receipt paths, material selection receipt paths, execution
  receipt paths, candidate refs, usernames, passwords, email addresses,
  subjects, senders, recipients, raw UIDs, Message-ID values, attachment names,
  local absolute paths, tokens, or secret values.

## Why This Exists

The IMAP material flow now has six separate human-safe checkpoints:

```text
header scan receipt -> material selection record -> material capture request -> material capture execution contract -> material capture approval receipt -> material capture approval audit
```

This command is the sixth checkpoint. It prevents a future body, attachment, or
derived-text adapter from trusting a stale, mismatched, or leaky approval
receipt before live message-material reads exist.
