# 2026-06-16 v0.3.72 IMAP Material Capture Approval Audit

## Context

After v0.3.71 introduced a non-secret IMAP material capture approval receipt,
the next safe step that did not require live mailbox testing was an audit gate.
The audit proves that a future live adapter should not trust a mismatched,
stale, or leaky approval receipt.

## Decision

Add a read-only CLI checkpoint:

```text
archive imap-mailbox-material-capture-approval-audit <archive-root>
  --material-selection-receipt <archive-relative-json>
  --approval-receipt <archive-relative-json>
  --capture-action message_body_capture|attachment_capture|derived_text_capture
  --expected-decision needs_review|approve_once|deny
  --dry-run --format json
```

Aliases:

```text
archive imap-material-capture-approval-audit
archive mailbox-material-capture-approval-audit
```

## Implementation Notes

- Added `imap_mailbox_material_capture_approval_audit` in
  `wom-kit/src/wom_kit/archive_services.py`.
- Added the CLI command and aliases in `wom-kit/src/wom_kit/archive_cli.py`.
- Added CLI coverage for dry-run enforcement, approval receipt verification,
  expected-decision mismatch blocking, private-marker non-echoing, no writes,
  and no message material reads.
- Added public documentation, capability matrix coverage, release notes, and
  changelog entries for v0.3.72.
- Bumped package versions to `0.3.72`.

## Safety Boundary

v0.3.72 still does not implement live message body capture, attachment capture,
or mail-derived text extraction. The new command reads only non-secret material
selection and material capture approval receipts. It opens no IMAP connection,
reads no environment variables, opens no keyring or password manager, reads no
message headers, bodies, or attachments, creates no derived text, writes no
files, and echoes no approval receipt path, material selection receipt path,
execution receipt path, candidate refs, local paths, tokens, or secret values.

## Follow-Up

A future live material capture adapter should require this audit to pass before
using a material capture approval receipt. The live body/attachment/derived-text
adapter will still need real mailbox testing.
