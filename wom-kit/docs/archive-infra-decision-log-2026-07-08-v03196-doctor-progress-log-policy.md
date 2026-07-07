# Archive Infra Decision Log - v0.3.196 Doctor Progress-Log Policy

Date: 2026-07-08
Release: v0.3.196

## Context

v0.3.195 clarified that `doctor --output <path>` is archive-relative and that
the full doctor result JSON is a local diagnostic artifact, not an archive
receipt.

The same operator run showed a second ambiguity: `--progress-log logs/...` uses
the process current working directory, while `--output logs/...` uses the archive
root. Both behaviors are useful, but the difference must be visible in machine
summary output so an AI operator does not infer the wrong storage location.

## Decision

When a doctor progress log is requested, include a `progress_log` block in doctor
summary output.

For relative progress-log paths:

- `path_kind: cwd_relative`
- `relative_to: current_working_directory`
- `absolute_path_echoed: false`
- `contains: progress_events_jsonl`
- `tracking_policy: local_progress_artifact_not_archive_receipt`

For absolute progress-log inputs, do not echo the absolute local path. Report
`path: <absolute-progress-log-path>` and
`path_kind: absolute_input_redacted`.

## Consequences

- Operator summaries now distinguish the two path bases directly.
- Progress logs remain local artifacts and are not promoted to archive receipts.
- No archive migration is required.
- Default doctor behavior, progress-log write behavior, and exit-code semantics
  are unchanged.
