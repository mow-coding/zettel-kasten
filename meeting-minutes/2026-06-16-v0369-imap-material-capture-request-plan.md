# Meeting Minutes: v0.3.69 IMAP Material Capture Request Plan

Date: 2026-06-16

## Context

After v0.3.68, WOM-kit could write a non-secret material selection receipt with
human-selected one-based candidate indexes. The next useful step was not to
read message bodies yet. It was to validate whether that selection receipt is
ready to support a future material capture request.

## Decision

Add a read-only request gate that validates one material selection receipt and
checks the requested future material action:

- `message_body_capture`
- `attachment_capture`
- `derived_text_capture`

The command should return readiness for a future adapter only when the selected
lane in the receipt authorizes the requested capture action.

## Implementation

Implemented `archive imap-mailbox-material-capture-request-plan` with aliases:

- `archive imap-material-capture-request-plan`
- `archive mailbox-material-capture-request-plan`

The command reads one non-secret selection receipt from:

```text
receipts/imap/material-selections/
```

It does not read the original execution receipt, open IMAP, read environment
variables, open keyring/password managers, read headers, read bodies, read
attachments, create derived text, call providers, or write files.

## Files Changed

- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/tests/test_cli.py`
- `wom-kit/docs/imap-mailbox-material-capture-request-plan.md`
- `wom-kit/docs/releases/v0.3.69.md`
- `wom-kit/docs/capability-matrix.md`
- `wom-kit/tests/test_capability_matrix_docs.py`
- `README.md`
- `wom-kit/README.md`
- `CHANGELOG.md`

## Verification Plan

Run focused CLI tests, full CLI tests, capability documentation tests, MCP
tests, release readiness checks, public privacy checks, version checks, and
GitHub account preflight before publishing.
