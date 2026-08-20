# Operational Context

Status: v0.3.117 AI operational context rehydration checkpoint

v0.3.278 extension: read-only AI command-path routing is included in the same
operational-context surface.

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
operational_context.action_routing
```

To inspect only this layer, run:

```powershell
archive operational-context <archive-root> --dry-run --format json
```

Introduced in v0.3.278 and extended through v0.3.294, this read-only output also
returns the same official
`wom-kit/ai-command-path-routing/v0.8` object as runtime-context and
ai-start-here. It routes index search through `archive search` and global
negative-claim planning through `archive objet-rediscovery-plan --dry-run`,
conservative inbox
shape review through `archive inbox-pipeline-audit`, and AI draft creation
through the separately bound `archive create-draft`. Explicit event membership
review routes through read-only add/removal plans. In v0.4.0 every membership
add, removal, or recovery approval returns
`compound_exact_human_approval_binding_required` before private target read or
mutation; there is no approved writer/recovery continuation. None infers
membership. A destination folder
alone is never write authorization. v0.3.284 advanced routing to v0.6 while
addition and removal share one global lock and a two-root retained-evidence
scan but keep operation-specific request, journal, receipt, and recovery
contracts as historical evidence. v0.3.293 advanced routing to v0.7 with the
operator-feedback plan and ledger sequence. Unknown completion evidence stays
in forensic hold. The inbox audit
proves no writer identity and performs no automatic repair. See
[AI Command-Path Routing](ai-command-path-routing.md).

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

New writes use exact UTF-8 bytes, so `written_record_sha256` matches the actual
on-disk record. Session handoff verification also recognizes older Windows
receipts that hashed newline-normalized text, labels that legacy hash basis,
and separately binds the current exact bytes.

Before ending an AI session, use the
[Session Handoff Checkpoint](session-handoff-checkpoint.md) to verify that this
record, its receipt, and the AI artifact inventory still agree.

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
