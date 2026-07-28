# Archive Infra Decision Log - v0.3.271 Title Remap Recovery Plan

Date: 2026-07-28

Status: accepted for implementation

## Context

v0.3.269 writes a private transaction journal and preserves verified complete
prior canonical bytes before its first title mutation. v0.3.270 can classify
that retained evidence, but it deliberately does not say which recovery
direction a later operator should review.

A recovery executor must not invent policy from a partial audit or expose
private title evidence. The decision must be fixed before a later write-capable
release is designed.

## Decision

1. Add CLI-only read-only
   `archive zet-title-remap-recovery-plan --dry-run`, alias
   `title-remap-recovery-plan`.
2. Reuse the complete bounded v0.3.270 receipt/journal/lock audit as the sole
   factual source. Block the plan if that audit is incomplete or recovery cases
   are truncated.
3. Apply this fixed decision matrix:
   - `prepared`:
     `cleanup_unstarted_title_transaction_evidence`;
   - `partially_applied` or `fully_applied_receipt_missing` with verified
     prior-byte evidence:
     `rollback_uncommitted_title_apply_to_before`;
   - `stale_completed` with the exact independently verified final receipt:
     `cleanup_verified_completed_title_evidence`;
   - invalid/divergent participants, invalid prior-byte snapshots, an
     unverified deterministic receipt, or an orphaned/invalid common lock:
     `manual_forensic_hold`.
4. A missing common lock is not the same as an invalid present lock. A later
   executor may reacquire an absent common lock only after exact state
   revalidation and an explicit quiescent-archive affirmation. It may not
   replace an orphaned or invalid present lock.
5. Output only a content-free case SHA-256, participant-state counts,
   fixed action/reason codes, a source audit digest, and a complete plan
   digest. Do not echo title text/hash/length, zet id/path, reviewer, proposal
   SHA, private evidence paths, provider values, or absolute local paths.
6. v0.3.271 writes and deletes nothing, creates no lock or receipt, calls no
   provider/model, exposes no MCP method, and implements neither the recovery
   executor nor approved title revert.

## Standards Cross-Check

SQLite's rollback-journal design preserves original content before data-file
mutation, serializes recovery with an exclusive lock, and removes hot-journal
evidence only after restoration is complete. PostgreSQL's WAL introduction
likewise documents the write-ahead rule that recovery records become durable
before corresponding data-file changes.

WOM is not a database and does not claim database-level atomicity. The narrow
adopted principle is to retain prior-state evidence before mutation, revalidate
the current state before recovery, serialize any later recovery executor, and
delete evidence only after the selected result is verified.

Primary references:

- https://sqlite.org/atomiccommit.html
- https://www.postgresql.org/docs/16/wal-intro.html

## Consequences

An operator can review one deterministic recovery direction per retained title
transaction without opening private journals by hand. No plan result is an
authorization to write. A later release must bind one case SHA-256 and the
complete plan digest, repeat all validation, require fresh human approval and
archive quiescence, and preserve every artifact on any uncertain outcome.
