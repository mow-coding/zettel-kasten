# Decision Log: Actionable Full-Doctor Results And Current-Stage Progress

Date: 2026-07-13
Decision: accepted for v0.3.228

## Context

A completed runtime-context full-Doctor run returned accurate severity totals,
but the result retained no individual ERROR/WARN code, path, message, hint, or
suggested command. Once that process ended, the missing details could not be
recovered from the count-only JSON. Running another broad Doctor solely to
identify already-counted findings is costly on a large local archive.

The same run also exposed a progress-routing conflict. A preserved aggregate
from the earlier edge-receipt phase remained active while
`local-profile-secret-safety` was doing the current work. Internal events had
fresh file counts, but the shared heartbeat kept displaying stale edge counts.

## Decision

- Add a top-level `doctor_findings` result to runtime-context and AI start-here.
- Preserve complete severity and diagnostic-code counts for ERROR/WARN.
- Preserve at most 100 detailed findings and at most 20 deduplicated suggested
  commands, with explicit truncation flags. INFO remains count-only.
- Keep archive-contained paths relative and replace outside absolute paths with
  `<local-path-redacted>` when local-path redaction is enabled.
- Replace diagnostic text that still contains an outside local path or provider
  URL with `<sensitive-diagnostic-text-redacted>`.
- State plainly that an older count-only result cannot truthfully reconstruct
  details that it never stored. One new full-Doctor run is required to capture
  that old evidence; later completed results do not need a second broad run.
- While `local-profile-secret-safety` is active, make its current
  `checked_files`, `content_scanned`, `local_profiles`, and `skipped_dirs`
  counts take precedence over the preserved edge-source aggregate.
- Reuse the resolved boundary of an already-checked walked directory for
  ordinary files. Keep individual resolved-containment and ignored-target
  checks for symlinks.
- Ship a temporary synthetic benchmark that reads no real archive, calls no
  provider or credential store, and writes no persistent files.

## Consequences

One completed full-Doctor result is now sufficient for an AI operator to name
and plan repairs for ERROR/WARN findings without immediately repeating the
broad scan. Progress reflects the stage that is actually consuming time. The
local-profile scan avoids repeated path-resolution work for ordinary files
without weakening symlink or directory-boundary checks.
