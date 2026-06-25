# Operator Feedback Lifecycle

Status: v0.3.149 approval-gated metadata checkpoint

WOM now gives operator-generated tool feedback a separate lifecycle surface.

This is for feedback, bug reports, and retrospectives created while an AI
operator is running an archive for a human. Those records are meaningful, but
they are not the user's own knowledge objects. They should not be tracked only
as loose files in user content folders.

## Commands

Preview the policy:

```powershell
archive operator-feedback-plan <archive-root> `
  --dry-run `
  --format json
```

Preview a metadata record:

```powershell
archive operator-feedback-record <archive-root> `
  --feedback-id agent_operator_retro_20260623 `
  --feedback-ref feedback:agent-operator-retro `
  --status delivered `
  --dry-run `
  --format json
```

Approve the metadata write:

```powershell
archive operator-feedback-record <archive-root> `
  --feedback-id agent_operator_retro_20260623 `
  --feedback-ref feedback:agent-operator-retro `
  --status resolved `
  --resolved-in v0.3.149 `
  --approve `
  --reviewed-by person:me `
  --format json
```

Aliases:

```powershell
archive feedback-plan <archive-root> --dry-run
archive ops-feedback-plan <archive-root> --dry-run
archive feedback-record <archive-root> ...
archive feedback-register <archive-root> ...
```

## Storage

Approved metadata records go under:

```text
ops/feedback/<feedback-id>.yml
```

Receipts go under:

```text
receipts/operator-feedback/
```

## Statuses

- `draft`: feedback exists but has not been sent or recorded as delivered.
- `delivered`: feedback was delivered to the project team or relay channel.
- `acknowledged`: the project team confirmed receipt.
- `resolved`: a release or decision closed the feedback.
- `archived`: feedback is kept for history and no active action remains.

## Safety Boundary

The commands:

- do not read feedback bodies,
- do not copy or move feedback body files,
- do not submit feedback externally,
- do not call providers,
- do not check network,
- do not echo feedback ref values,
- do not echo title values,
- do not echo local absolute paths, tokens, or secret values.

## Still Future

- Real feedback submission to a project-maintainer channel.
- Inbox migration helpers for existing loose feedback files.
- A feedback status board.
- Cross-archive feedback relay receipts.
- Automatic issue or release-note linking.
