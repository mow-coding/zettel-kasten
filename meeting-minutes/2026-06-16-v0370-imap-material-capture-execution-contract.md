# 2026-06-16 v0.3.70 IMAP Material Capture Execution Contract

## Context

The user asked to keep progressing on work that does not require new beta
tester feedback. The next safe IMAP step was to close the material-capture
planning ladder without implementing live body, attachment, or derived-text
mail reads.

## Decision

Add a read-only CLI checkpoint:

```text
archive imap-mailbox-material-capture-execution-contract <archive-root>
  --material-selection-receipt <archive-relative-json>
  --capture-action message_body_capture|attachment_capture|derived_text_capture
  --dry-run --format json
```

Aliases:

```text
archive imap-material-capture-execution-contract
archive mailbox-material-capture-execution-contract
```

The command reuses the existing material capture request validation and returns
the future live-adapter execution contract only when the request is ready.

## Implementation Notes

- Added `imap_mailbox_material_capture_execution_contract` in
  `wom-kit/src/wom_kit/archive_services.py`.
- Added the CLI command and aliases in `wom-kit/src/wom_kit/archive_cli.py`.
- Added CLI coverage for dry-run enforcement, ready contract output, private
  marker non-echoing, no writes, no material reads, and mismatched
  capture-action blocking.
- Added public documentation, capability matrix coverage, release notes, and
  changelog entries for v0.3.70.
- Bumped package versions to `0.3.70`.

## Safety Boundary

v0.3.70 still does not implement live message body capture, attachment capture,
or mail-derived text extraction. The new command opens no IMAP connection,
reads no environment variables, opens no keyring or password manager, reads no
message headers, bodies, or attachments, creates no derived text, writes no
files, and echoes no receipt paths, candidate refs, local paths, tokens, or
secret values.

## Follow-Up

Future live material capture work must use this contract as a release-blocking
test target and must still require separate human approval plus credential
policy checks before reading selected message material.
