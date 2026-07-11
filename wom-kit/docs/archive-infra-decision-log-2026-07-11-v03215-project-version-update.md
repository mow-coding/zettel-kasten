# Decision Log: v0.3.215 Project Version Update

Date: 2026-07-11
Status: implemented

## Decision

Replace manual project source checkout and version-pin editing with one
dry-run-first, approval-gated, rollback-capable local transaction.

## Context

Version diagnostics could identify drift but could not repair it. Operators had
to fetch tags, detach the source mirror, and edit pins by hand, creating a
half-updated-state risk and leaving no bounded receipt.

## Consequences

- Dry-run performs local checks only; approval invokes configured Git transport.
- One atomic non-force fetch requests only origin/main and the exact target tag.
- Annotated-tag type, main ancestry, and all three source versions are verified
  before checkout.
- Dirty/ambiguous state and downgrade attempts fail closed without private
  filenames, paths, remotes, credentials, or raw Git stderr in output.
- The source checkout, recognized pins, and one project receipt are the entire
  durable write boundary. Archive knowledge is untouched.
- Same-root and parent-project archive layouts are resolved without escaping to
  an unrelated parent.
- Atomic writes use exclusive randomized temporary files, so a pre-existing
  local temporary file is not overwritten.
- Post-checkout failure restores source and pin state and verifies the restored
  worktree, not just HEAD; fetched refs may remain.
- Success requires process restart and a new version/import-origin check.
- v0.3.215 is an unavoidable one-time bootstrap boundary for older clients.
