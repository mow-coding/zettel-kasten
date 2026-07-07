# Archive Infra Decision Log - v0.3.194 Doctor Result Capture

Date: 2026-07-08

Release: v0.3.194

## Context

Large strict doctor runs can now finish on real archives, but the final
diagnostics JSON may be too large for a terminal or AI chat transcript. When the
stdout stream is truncated, operators keep the exit code but lose the complete
diagnostic set.

## Decision

Add `archive doctor --output <path>` as a result-capture option. It writes the
full diagnostics JSON array to a file and switches stdout to a compact summary.
The path is archive-relative, so result capture stays in the archive's local
logs/workbench space instead of echoing or writing arbitrary local paths.

Add stdout-only filters:

- `--summary`
- `--errors-only`
- `--diagnostic-level ERROR,WARN`

The filters never change exit-code semantics. Doctor still fails on ERROR and
`--strict` still fails on WARN.

## Diagnostic Guidance

Add next-action hints to recurring strict diagnostics:

- `provenance.creation_mode` schema enum errors name the allowed values and route
  to a summary doctor rerun after correction.
- object-storage execution receipt/manifest link gaps route operators to
  preserve a full doctor JSON result and repair through the owning
  upload/adopt/reconcile workflow.
- BOM warnings point to `remint-reconcile --strip-bom` dry-run before approval.

## Consequences

- AI operators can preserve the full machine-readable result while keeping chat
  output small.
- The new options are additive and leave existing stdout contracts unchanged when
  unused.
- The output file may be large by design; operators should place it in a local
  logs/workbench location and review before sharing.
