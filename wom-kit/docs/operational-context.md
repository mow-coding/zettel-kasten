# Operational Context

Status: v0.3.117 AI operational context rehydration checkpoint

WOM archives preserve zets, receipts, manifests, and source maps. An AI runtime
also needs one small operating-memory record so it can recover the current
mission after a session reset or context compression.

That record lives at:

```text
ops/operational-context.yml
```

It is not a replacement for zets or receipts. It is the AI-facing handoff layer
for mission, scope, state, gotchas, and reviewed decisions.

## Read It

At session start, run:

```powershell
archive runtime-context <archive-root> --format json
```

The result includes:

```text
operational_context.record
operational_context.session_start_injection
```

To inspect only this layer, run:

```powershell
archive operational-context <archive-root> --dry-run --format json
```

## Update It

Stage a candidate YAML file inside the archive, for example:

```text
workbench/operational-context.next.yml
```

Then preview:

```powershell
archive operational-context <archive-root> --record workbench/operational-context.next.yml --dry-run --format json
```

After human review, approve:

```powershell
archive operational-context <archive-root> --record workbench/operational-context.next.yml --approve --reviewed-by <actor> --format json
```

Approved writes replace `ops/operational-context.yml` and create a receipt under
`receipts/operational-context/`.

## Record Shape

```yaml
schema: wom-kit/operational-context/v0.1
mission:
  summary: Keep the current archive mission visible to AI runtimes after context compression.
  scope:
    - Active work that must not be demoted into history.
  non_goals:
    - Work the AI must not claim or perform.
state:
  phase: current phase label
  completed:
    - Reviewed completed item.
  in_progress:
    - Current active item.
  next:
    - Next safe action.
  blocked:
    - Waiting condition, if any.
gotchas:
  - Important mistake to avoid.
decisions:
  - Reviewed owner decision.
rehydration:
  session_start:
    - Read operational_context.session_start_injection before broad archive reads.
  on_demand_commands:
    - archive runtime-context <archive-root> --format json
    - archive operational-context <archive-root> --dry-run --format json
```

## Privacy Boundary

Operational context values must not contain provider URLs, local absolute paths,
email-like account labels, tokens, passwords, or secret-like values. The command
blocks unsafe candidate values before any approved write.

This feature:

- reads one archive-internal YAML record,
- writes only when `--approve --reviewed-by` is used,
- writes an approval receipt,
- calls no providers,
- reads no secrets,
- exposes no MCP write tool.
