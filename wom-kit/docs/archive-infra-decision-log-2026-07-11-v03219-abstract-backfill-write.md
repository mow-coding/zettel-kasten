# Archive Infrastructure Decision Log: v0.3.219 Abstract Backfill Write

Date: 2026-07-11
Status: accepted and implemented

## Context

v0.3.218 could prove that private proposed abstracts matched exact current
canonical zet bytes, but deliberately had no write authority. Manual bulk edits
would discard the proposal hash, human-review attribution, all-or-nothing
behavior, and durable revision evidence.

## Decision

- Keep planning and writing as separate commands.
- Require exact proposal SHA-256 on preview and approval.
- Require a safe reviewer id plus an explicit all-abstracts-reviewed
  affirmation for every new write.
- Rerun planning and revalidate every canonical exact-byte hash before writing.
- Add only `frontmatter.abstract`; do not update `updated_at` or normalize the
  rest of the file.
- Snapshot exact canonical bytes in bounded memory and restore every attempted
  target if an item or receipt operation fails in-process.
- Write one deterministic private receipt last. Store ids/paths and hashes, but
  no body or abstract text.
- Treat a matching receipt/current-state pair as idempotent `already_applied`.
- Use a private per-proposal lock against concurrent WOM writers.

## Consequences

The archive gains an auditable route for filling first-read gaps without
turning AI-generated summaries into automatic canonical truth. Public output
stays content-free while the private receipt preserves enough evidence to audit
which exact bytes changed.

Rollback requires exact source snapshots, so one canonical file is capped at
16 MiB and one batch at 256 MiB. The transaction handles runtime failures but
is not crash-safe: WOM writes no body-bearing recovery journal, and an external
editor is not locked. A later release may add receipt audit and deterministic
one-field rollback, but must not claim forced-termination recovery without a
separate durable design.
