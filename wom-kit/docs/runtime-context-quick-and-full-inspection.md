# Runtime Context Quick And Full Inspection

Status: quick/default and explicit full-Doctor contract implemented in v0.3.224

## Purpose

Runtime-context is an AI handoff packet, not an automatic complete archive
health check. An entering AI should be able to confirm the archive, local
authority, entrypoints, operating record, and safe next actions before paying
the cost of reading every zet and receipt.

## Quick Default

CLI:

```powershell
archive runtime-context <archive-root> --format json
```

MCP:

```text
archive_runtime_context with full_doctor omitted or false
```

Quick mode does not construct Doctor. It reports:

```text
inspection.mode: quick
inspection.full_doctor_run: false
doctor_summary.checked: false
```

It reads bounded identity, policy, canonical-entrypoint, version, authority,
and operational-context metadata. It does not enumerate every zet or receipt,
read zet bodies, read objet bytes, call a provider, access a credential store,
or write archive state. The result is not an archive-health claim.

## Explicit Full Doctor

CLI:

```powershell
archive runtime-context <archive-root> `
  --full-doctor `
  --progress `
  --format json
```

MCP:

```text
archive_runtime_context with full_doctor: true
```

Full mode keeps the complete Doctor validation path. CLI progress uses the same
content-free stage/count, heartbeat, fixed phase, and redaction contract as
`ai-start-here --full-doctor`. The result records Doctor severity counts and
observed broad reads. The service refuses a full-Doctor result when either the
diagnostics or read observations are missing, so a caller cannot report broad
reads as false merely by omitting evidence. MCP does not expose a progress
stream, so use the CLI or the separate Doctor tool when long-running progress
is required.

## No-Repeat Start-Here Handoff

`ai-start-here` already composes runtime-context into its result. It exposes:

```text
summary.runtime_context_included: true
summary.runtime_context_rerun_required: false
completed_commands
next_commands
remaining_ai_runtime_order
```

For compatibility, `first_commands` still contains the complete canonical
recommendation list. Its runtime-context row is marked:

```text
status: already_included
run_required: false
```

An AI should execute `next_commands`, not replay every item in
`first_commands`. The source `ops/operational-context.yml` record remains
unchanged. If that record contains the default sentence `Run runtime-context
first.`, start-here keeps it in the source record but does not copy the already
satisfied sentence into `next_safe_steps`.

## Compatibility

No archive migration is required. Scripts that relied on CLI or MCP
runtime-context to run Doctor implicitly must request full Doctor explicitly.
All paths remain read-only and local-path-redacted by default.
