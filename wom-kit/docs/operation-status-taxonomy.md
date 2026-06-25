# Operation Status Taxonomy

Status: v0.3.151 operation status taxonomy checkpoint

WOM now has a read-only status taxonomy for AI operators.

This is the first safe step toward command-wide envelope consistency. It tells
an AI how to classify command results before speaking to a human, especially
when a command returns some useful evidence but did not complete the whole job.

## Command

```powershell
archive operation-status-taxonomy <archive-root> `
  --dry-run `
  --format json
```

Aliases:

```powershell
archive status-taxonomy <archive-root> --dry-run
archive partial-success-taxonomy <archive-root> --dry-run
```

## Status Classes

- `succeeded`: the requested read-only or verification operation completed fully.
- `preview`: a dry-run preview or plan completed without writing.
- `written`: an approval-gated local write completed and receipts should name what changed.
- `no_change`: the operation was valid but idempotent and nothing needed to change.
- `partial`: some items completed but at least one requested item did not.
- `truncated`: the command intentionally omitted results because of limits, caps, or paging.
- `blocked`: preconditions or safety gates stopped the operation before it could run.
- `failed`: the command failed unexpectedly or an operation error occurred.

## AI Operator Rule

`partial`, `truncated`, `blocked`, and `failed` are not success.

If an output has `truncated=true`, `limit_hit=true`, `omitted_count>0`, or
`incomplete_count>0`, the AI should not say the task is fully complete. It
should explain the incomplete coverage, show blockers or next safe actions, and
ask for a narrower scope or continuation when needed.

## Safety Boundary

The command:

- reads no archive body text,
- echoes no zettel body text,
- echoes no source values,
- calls no providers,
- checks no network,
- echoes no local absolute paths, tokens, or secret values,
- writes nothing.

## Still Future

- Applying this taxonomy consistently across every JSON-producing command.
- Adding command-specific `status_class` fields where they are missing.
- Detecting stale approval handoffs when target metadata changes.
- Normalizing batch item status summaries across mint, retire, capture, fetch,
  and import commands.
