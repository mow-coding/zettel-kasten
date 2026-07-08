# Archive Infra Decision Log - v0.3.197 Reconcile Next-Action Guidance

Date: 2026-07-08
Release: v0.3.197

## Context

After v0.3.196, an operator ran:

```text
archive retire-draft-reconcile <archive-root> --zettel-id <id> --dry-run --format json
```

The dry-run succeeded and correctly classified the drift as `content_change` with
`content_change_ack_required: true`, but the JSON did not expose a top-level
status or suggested next action. That left the human-facing operator summary
dependent on external instructions.

## Decision

Add machine-readable next-action guidance to both reconcile dry-run surfaces:

- `remint-reconcile`
- `retire-draft-reconcile`

Dry-run JSON now includes:

- `status`
- `overall_status`
- `suggested_next_action`
- `would_write`
- `approval_would_write`
- `approval_requires_content_changed_ack`
- `next_safe_actions`

For `content_change`, the guidance explicitly says to review content evidence
outside the redacted JSON summary before any approve run, and only then use
`--content-changed-ack` if the change is intentional.

## Consequences

- Operators can answer "what next?" from the command result itself.
- Classification behavior is unchanged.
- Approval gates are unchanged.
- Dry-runs still write nothing.
- Text-mode `retire-draft-reconcile` now prints the same next safe actions when
  present.
