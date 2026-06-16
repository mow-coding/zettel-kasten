# IMAP Mailbox Material Selection Record

Status: v0.3.68 approval-gated IMAP material selection record
Date: 2026-06-16

v0.3.68 adds the first write step after the IMAP material selection plan.

The command reads one existing non-secret IMAP header metadata scan execution
receipt, validates the same redaction and opaque-candidate boundaries as the
planning command, and records a human-reviewed selection by one-based candidate
index.

It still does not read message bodies, attachment bytes, or mail-derived text.

## Command

```bash
archive imap-mailbox-material-selection-record <archive-root> \
  --execution-receipt receipts/imap/adapter-executions/example.json \
  --selection-mode body_candidates \
  --selected-index 1 \
  --selected-index 3 \
  --reviewed-by human:me \
  --dry-run \
  --format json
```

Aliases:

```text
imap-material-selection-record
mailbox-material-selection-record
```

Use `--approve` instead of `--dry-run` only after the dry-run says
`record_state: record_ready`.

## Selection Indexes

`--selected-index` is a one-based candidate position from the validated
execution receipt.

For example:

```text
--selected-index 1 --selected-index 3
```

means "select candidate position 1 and candidate position 3." It does not echo
or write the underlying `imap-candidate:<sha256>` refs.

The command blocks if:

- no selected index is provided,
- an index is less than 1,
- an index is duplicated,
- an index is greater than the candidate-ref count in the execution receipt,
- the execution receipt fails the non-secret receipt validation.

## What It Writes

Approved mode writes one non-secret receipt under:

```text
receipts/imap/material-selections/
```

The receipt records:

- the execution receipt SHA-256,
- the selected future material lane,
- selected one-based candidate indexes,
- selected count,
- candidate pool count,
- the fact that candidate refs are not included.

It does not include the original execution receipt path or the candidate refs.

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
- echoes execution receipt paths, candidate refs, usernames, passwords, email
  addresses, subjects, senders, recipients, raw UIDs, Message-ID values,
  attachment names, local absolute paths, tokens, or secret values.

## Why This Exists

Future message body or attachment capture needs an auditable human choice, but
that choice should not require exposing raw IMAP UIDs, subjects, senders, or
candidate refs in public/debug output.

This record is the small bridge:

```text
validated header scan receipt -> human-selected candidate positions -> future
material approval gate
```
