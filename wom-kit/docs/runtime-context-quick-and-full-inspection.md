# Runtime Context Quick And Full Inspection

Status: quick/default and explicit full-Doctor contract implemented in v0.3.224;
actionable bounded findings implemented in v0.3.228

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
doctor_findings.checked: false
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
observed broad reads. Since v0.3.228 it also retains a bounded
`doctor_findings` result containing ERROR/WARN items, complete severity/code
counts, and suggested commands. INFO stays count-only. The service refuses a full-Doctor result when either the
diagnostics or read observations are missing, so a caller cannot report broad
reads as false merely by omitting evidence. MCP does not expose a progress
stream, so use the CLI or the separate Doctor tool when long-running progress
is required.

## Actionable Finding Boundary

A completed full run returns:

```text
doctor_findings.checked: true
doctor_findings.selected_levels: [ERROR, WARN]
doctor_findings.total
doctor_findings.returned
doctor_findings.truncated
doctor_findings.code_counts
doctor_findings.items
doctor_findings.suggested_commands
doctor_findings.suggested_commands_truncated
```

At most 100 individual findings and 20 unique suggested commands enter the
handoff packet. `code_counts` is calculated over every ERROR/WARN diagnostic,
including rows beyond the item cap. Items keep only diagnostic fields already
produced by Doctor: severity, code, message, archive-relative path, optional
hint, optional suggested command, and optional compatibility target. Local
absolute paths are converted to archive-relative paths when possible or
redacted. A message, hint, command, or compatibility target that still contains
an outside local path or provider URL after archive-root substitution is
replaced by `<sensitive-diagnostic-text-redacted>`. This keeps a small unhealthy
result actionable without copying the thousands of ordinary INFO rows into AI
context.

This is not a retroactive decoder. A saved v0.3.227 result that contains only
severity totals does not contain the discarded code/path/message evidence, so
it cannot truthfully reconstruct those absent values from that JSON. One new
Doctor run is required for an old count-only result; v0.3.228 preserves the
actionable findings from that new completed run.

## Current Long-Stage Progress

When `local-profile-secret-safety` is active, shared compact heartbeat
prioritizes its strict numeric aggregate:

```text
checked_files=N content_scanned=N local_profiles=N skipped_dirs=N
```

The older edge source-load aggregate stays in memory for its final summary but
does not replace the active stage name or counters. Unknown or path-bearing
local-profile progress text is rejected. Ordinary files reuse the directory
boundary already checked by `os.walk`; symlinks still require resolved
containment and ignored-target checks. Secret filename/content/profile rules
and read observations are unchanged.

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
