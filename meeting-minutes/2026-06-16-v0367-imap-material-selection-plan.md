# Meeting Minutes: v0.3.67 IMAP Material Selection Plan

Date: 2026-06-16

## Context

The user asked to keep moving through work that can be completed without more
live client feedback. The active priority remains mail intake, but broad mail
ingestion should not jump directly from a header scan receipt into message body
or attachment reads.

The previous public checkpoints already added:

- the first narrow approval-gated IMAP header metadata scan,
- a non-secret audit checkpoint for those execution receipts.

## Decision

Add a read-only planning checkpoint between the header scan receipt and any
future message material read.

The checkpoint should:

- read one existing archive-relative IMAP header metadata scan execution
  receipt,
- validate the receipt kind, lifecycle action, status, counts, opaque candidate
  refs, and redaction flags,
- report only aggregate planning fields for a future human review lane,
- keep message bodies, attachment bytes, and mail-derived text closed.

## Implementation

Implemented `archive imap-mailbox-material-selection-plan` with aliases:

- `archive imap-material-selection-plan`
- `archive mailbox-material-selection-plan`

The command supports read-only selection modes:

- `human_review_queue`
- `body_candidates`
- `attachment_candidates`
- `derived_text_candidates`

It writes no queue files in this release. It opens no IMAP connection, reads no
environment variables, opens no keyring/password manager, reads no headers,
bodies, or attachments, starts no OAuth, calls no providers, and echoes no
execution receipt path or candidate refs.

## Files Changed

- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/tests/test_cli.py`
- `wom-kit/docs/imap-mailbox-material-selection-plan.md`
- `wom-kit/docs/releases/v0.3.67.md`
- `wom-kit/docs/capability-matrix.md`
- `wom-kit/tests/test_capability_matrix_docs.py`
- `README.md`
- `wom-kit/README.md`
- `CHANGELOG.md`

## Verification Plan

Run focused CLI tests, capability documentation tests, full CLI tests, release
readiness checks, public privacy checks, version checks, and GitHub account
preflight before publishing.
