# Meeting Minutes: v0.3.68 IMAP Material Selection Record

Date: 2026-06-16

## Context

After v0.3.67, WOM-kit could read a redacted IMAP header metadata scan receipt
and plan a future material review lane without reading message bodies or
attachments.

The next safe step was to let a human choice become durable without exposing
candidate refs or message material.

## Decision

Add an approval-gated write command that records one-based candidate indexes
from a validated IMAP header metadata scan receipt.

The record should:

- require at least one selected index,
- block duplicate or out-of-range indexes,
- write only a non-secret material selection receipt,
- bind to the execution receipt by SHA-256,
- avoid writing candidate refs, execution receipt paths, message headers,
  bodies, attachment names, or attachment bytes.

## Implementation

Implemented `archive imap-mailbox-material-selection-record` with aliases:

- `archive imap-material-selection-record`
- `archive mailbox-material-selection-record`

Approved mode writes under:

```text
receipts/imap/material-selections/
```

The command still opens no IMAP connection, reads no environment variables,
opens no keyring/password manager, reads no message headers again, reads no
message bodies, reads no attachments, creates no derived text, starts no OAuth,
and calls no providers.

## Files Changed

- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/tests/test_cli.py`
- `wom-kit/docs/imap-mailbox-material-selection-record.md`
- `wom-kit/docs/releases/v0.3.68.md`
- `wom-kit/docs/capability-matrix.md`
- `wom-kit/tests/test_capability_matrix_docs.py`
- `README.md`
- `wom-kit/README.md`
- `CHANGELOG.md`

## Verification Plan

Run focused CLI tests, full CLI tests, capability documentation tests, MCP
tests, release readiness checks, public privacy checks, version checks, and
GitHub account preflight before publishing.
