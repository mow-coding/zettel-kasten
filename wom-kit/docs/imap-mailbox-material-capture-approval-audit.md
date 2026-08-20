# IMAP Mailbox Material Capture Approval Audit

Status: v0.4.0 read-only legacy-unbound advisory audit
Date: 2026-06-16

v0.3.72 adds a read-only audit checkpoint for material capture approval
receipts. It may structurally compare one approval receipt with one material
selection receipt, but no live adapter may rely on the result. The result is
`legacy_unbound`/advisory and `future_capture_authorized` always remains false.

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

`approve_once`, `deny`, and `needs_review` are historical metadata values. None
is treated as live-ready in v0.4.0.

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

When legacy metadata matches, the command returns an advisory structural
classification rather than execution authority:

```text
legacy_unbound
```

`future_capture_authorized` remains false even when the audited receipt records
`approve_once` and every structural check passes.

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

This command is a historical checkpoint audit. It prevents any future body,
attachment, or derived-text adapter from treating legacy metadata as current
authority.
