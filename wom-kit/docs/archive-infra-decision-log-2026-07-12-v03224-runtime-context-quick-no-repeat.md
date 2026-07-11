# Archive Infrastructure Decision Log: v0.3.224 Runtime-Context Quick Handoff

Date: 2026-07-12
Status: accepted and implemented

## Context

v0.3.222 made `ai-start-here` quick by default, but CLI and MCP
`runtime-context` still constructed Doctor automatically. The bundled runtime
skill and start-here recommendation list could therefore route an AI back into
the same full archive scan that the quick entrypoint had just avoided.

## Decision

- Make CLI and MCP runtime-context quick by default.
- Keep complete validation behind explicit `--full-doctor` or
  `full_doctor: true`.
- Give explicit CLI full Doctor the shared content-free progress reporter.
- Report inspection mode, Doctor status, and observed broad reads.
- Preserve `first_commands` for compatibility, but mark runtime-context already
  included and expose separate completed/next command collections.
- Remove only the already-satisfied default runtime-context instruction from
  start-here's derived next-step list; never rewrite its source record.

## Consequences

An AI can enter through either start-here or runtime-context without an
unrequested all-archive scan. A complete health check remains available and
unchanged in validation scope, but it must be selected explicitly.

No archive schema, record, receipt, manifest, provider, credential, or write
boundary changes.
