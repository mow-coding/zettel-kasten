# Archive Infra Decision Log - v0.3.195 Doctor Output Policy

Date: 2026-07-08

Release: v0.3.195

## Context

The v0.3.194 `doctor --output` option successfully preserved full diagnostics
without flooding stdout. A follow-up observation showed that operators could
still confuse `--output logs/...` with CWD-relative output, especially because
`--progress-log` predates this option and writes through its existing path
contract.

The same run also surfaced `mint_retired_draft_sha_mismatch` diagnostics whose
`suggested_command` was useful but whose `hint` was still empty.

## Decision

Keep existing path behavior stable, but make `doctor --output` summaries
explicit:

- `path_kind: archive_relative`
- `relative_to: archive_root`
- `absolute_path_echoed: false`

Add a tracking policy field:

- `tracking_policy: local_diagnostic_artifact_not_archive_receipt`

Add a human-readable `git_guidance` string that says not to commit the result by
default.

For `mint_retired_draft_sha_mismatch`, add a hint that routes operators through
`retire-draft-reconcile --dry-run` before any approval.

## Consequences

- Operators can locate `--output` files without relying on absolute local path
  echoes.
- Full doctor result files remain local diagnostic artifacts rather than
  canonical receipts or feedback records.
- Existing scripts that use `--progress-log` or default `doctor` output are not
  changed.
