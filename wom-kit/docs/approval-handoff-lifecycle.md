# Approval Handoff Lifecycle

Status: v0.3.150 approval handoff checkpoint

WOM now has a small, first-class surface for AI-to-human approval handoffs.

This is not a web UI. It is a CLI and AI-answer surface for moments when an
AI operator must stop, explain what is about to happen, and record the human
decision before a sensitive operation continues.

## Commands

Preview the policy:

```powershell
archive approval-handoff-plan <archive-root> `
  --dry-run `
  --format json
```

Preview a handoff metadata record:

```powershell
archive approval-handoff-record <archive-root> `
  --handoff-id imap_material_capture_review_20260625 `
  --operation-kind read_private_material `
  --target-ref target:imap-material-selection `
  --requested-action "Approve selected message body capture" `
  --status needs_review `
  --dry-run `
  --format json
```

Approve the metadata write:

```powershell
archive approval-handoff-record <archive-root> `
  --handoff-id imap_material_capture_review_20260625 `
  --operation-kind read_private_material `
  --target-ref target:imap-material-selection `
  --requested-action "Approve selected message body capture" `
  --status approved_once `
  --approve `
  --reviewed-by person:me `
  --format json
```

Aliases:

```powershell
archive handoff-plan <archive-root> --dry-run
archive human-approval-handoff-plan <archive-root> --dry-run
archive handoff-record <archive-root> ...
archive human-approval-handoff-record <archive-root> ...
```

## Storage

Approved metadata records go under:

```text
ops/approval-handoffs/<handoff-id>.yml
```

Receipts go under:

```text
receipts/approval-handoffs/
```

## Statuses

- `needs_review`: a human decision is required before the operation continues.
- `approved_once`: one future operation attempt may proceed if all other guards pass.
- `denied`: the operation must not proceed.
- `superseded`: a later handoff replaced this one.
- `resolved`: the operation is closed by a receipt, release, or decision.

## Operation Kinds

- `read_private_material`
- `write_archive_record`
- `external_provider_action`
- `publish_or_release`
- `credential_access`
- `derived_artifact_update`
- `other`

## Safety Boundary

The commands:

- do not execute the underlying operation,
- do not read private material,
- do not call providers,
- do not check network,
- do not read local secrets,
- do not echo target ref values,
- do not echo requested action values,
- do not echo local absolute paths, tokens, or secret values.

The record can store safe labels so a future command or human review can trace
what was approved, but the terminal and JSON summary deliberately avoid echoing
those values back.

## Still Future

- Command-specific adapters that require a matching approval handoff receipt.
- A shared operation status taxonomy across every JSON command.
- Automatic stale-approval detection when target metadata changes.
- A compact AI answer template for showing handoff state to a beginner user.
