# IMAP Mailbox Header Scan Receipt Audit

Status: v0.3.63 approval-gated IMAP header scan receipt audit
Date: 2026-06-16

v0.3.63 adds the checkpoint after the first live IMAP header metadata scan.

The command reads one existing non-secret execution receipt from
`receipts/imap/adapter-executions/`, checks that it really is a redacted
`imap_mailbox_header_metadata_scan` receipt, and can write a separate audit
receipt under `receipts/imap/adapter-execution-audits/`.

It does not connect to IMAP again.

## Command

```bash
archive imap-mailbox-header-scan-receipt-audit <archive-root> \
  --execution-receipt receipts/imap/adapter-executions/example.json \
  --reviewed-by human:me \
  --dry-run \
  --format json
```

Aliases:

```text
imap-header-scan-receipt-audit
mailbox-header-scan-audit
```

Use `--approve` instead of `--dry-run` only after the dry-run says
`audit_state: audit_ready`.

## What It Checks

The audit verifies that the execution receipt:

- has `receipt_kind: imap_mailbox_header_metadata_scan`,
- has `lifecycle_action: imap_mailbox_header_metadata_scan`,
- reports a valid execution status,
- stores only counts and opaque `imap-candidate:<sha256>` refs,
- marks candidate refs as opaque hashes,
- has all sensitive redaction flags set to `false`.

Sensitive redaction flags include credential values, credential refs,
environment variable names, IMAP host values, mailbox refs, raw UID values,
Message-ID values, headers, bodies, attachment names, attachment bytes, and
local absolute paths.

## What It Writes

Approved mode writes one non-secret audit receipt under:

```text
receipts/imap/adapter-execution-audits/
```

The audit receipt records:

- the execution receipt SHA-256,
- execution status,
- candidate count,
- headers fetched count,
- candidate-ref count,
- a digest of the opaque candidate-ref list,
- the redaction-check result.

It does not include the original execution receipt path or the candidate refs
themselves.

## What It Never Does

The command never:

- opens an IMAP connection,
- logs into mail,
- selects or searches a mailbox,
- reads message headers again,
- reads message bodies,
- reads attachments,
- reads environment variables,
- opens an OS keyring,
- opens a password manager,
- starts OAuth,
- calls providers,
- echoes usernames, passwords, email addresses, subjects, senders, recipients,
  headers, raw UIDs, Message-ID values, local absolute paths, or secret values.

## Why This Exists

The first live IMAP header metadata scan creates the earliest bridge from
provider mail into WOM-kit records. This audit command makes that bridge
reviewable before later work, such as body capture or derived-text extraction,
is allowed to build on it.
