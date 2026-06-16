# 2026-06-16 v0.3.71 IMAP Material Capture Approval Receipt

## Context

After v0.3.70 introduced the IMAP material capture execution contract, the next
safe step that did not require real mailbox beta feedback was a local approval
receipt gate. The user explicitly allowed waiting if real usage feedback was
needed, but this work remains pre-live and local-only.

## Decision

Add an approval-gated CLI checkpoint:

```text
archive imap-mailbox-material-capture-approval-plan <archive-root>
  --material-selection-receipt <archive-relative-json>
  --capture-action message_body_capture|attachment_capture|derived_text_capture
  --decision needs_review|approve_once|deny
  --dry-run|--approve --format json
```

Aliases:

```text
archive imap-material-capture-approval-plan
archive mailbox-material-capture-approval-plan
archive imap-mailbox-material-capture-approval
```

The command reuses the material capture execution contract and writes one
non-secret approval receipt under:

```text
receipts/imap/material-capture-approvals/
```

## Implementation Notes

- Added `imap_mailbox_material_capture_approval_plan` and receipt helpers in
  `wom-kit/src/wom_kit/archive_services.py`.
- Added the CLI command and aliases in `wom-kit/src/wom_kit/archive_cli.py`.
- Added CLI coverage for mode enforcement, approval preview, approval receipt
  writing, private-marker non-echoing, no message material reads, and
  mismatched capture-action blocking.
- Added public documentation, capability matrix coverage, release notes, and
  changelog entries for v0.3.71.
- Bumped package versions to `0.3.71`.

## Safety Boundary

v0.3.71 still does not implement live message body capture, attachment capture,
or mail-derived text extraction. The new command opens no IMAP connection,
reads no environment variables, opens no keyring or password manager, reads no
message headers, bodies, or attachments, creates no derived text, writes no
message material, and echoes no material selection receipt path, execution
receipt path, candidate refs, local paths, tokens, or secret values.

## Follow-Up

A future live material capture adapter must verify this approval receipt plus
credential policy before reading selected message material. That future work
will need real mailbox testing before being called complete.
