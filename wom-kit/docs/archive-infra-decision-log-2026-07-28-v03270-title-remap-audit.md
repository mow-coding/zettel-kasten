# Archive Infra Decision Log - v0.3.270 Title Remap Evidence Audit

Date: 2026-07-28

Status: accepted for implementation

## Context

v0.3.269 can leave two kinds of durable private evidence:

- a completed immutable title-remap receipt;
- after a hard exit, a transaction journal and common write lock, possibly
  with canonical participants split between before and after hashes.

The writer can verify one known completed receipt on exact retry, but an
operator cannot yet ask one read-only command whether all title-remap evidence
in the archive is healthy or where an interrupted batch stopped.

## Decision

1. Add CLI-only read-only
   `archive zet-title-remap-receipt-audit --dry-run`, alias
   `title-remap-receipt-audit`.
2. Scan bounded title-remap receipts, retained transaction journals, and the
   one common title-remap write lock.
3. Verify every completed receipt against:
   - strict runtime document allowlists;
   - archive and proposal-digest filename binding;
   - current canonical after-file/title/body hashes;
   - exact prior-byte snapshot object and manifest evidence.
4. Classify a retained journal by current participant hashes:
   - `prepared`;
   - `partially_applied`;
   - `fully_applied_receipt_missing`;
   - `divergent`;
   - `stale_completed` when its final receipt is independently verified.
5. Verify every journal's strict schema/digest/archive/filename/final-receipt
   binding and all prior-byte snapshots.
6. Validate the common lock only as evidence. A journal without its lock, a
   lock without a matching valid journal, multiple journals behind one common
   lock, or an invalid lock is attention, never an invitation to delete it.
7. Output only counts, fixed states/codes, bounded problem rows, and a
   transaction-case SHA-256 handle. Do not echo title text/hash/length, zet
   id/path, receipt/journal/lock path, reviewer, proposal SHA, snapshot path,
   provider value, or absolute local path.
8. The command writes/deletes nothing, calls no provider/model, exposes no MCP
   method, and never performs recovery or receipt finalization.

## Consequences

Operators can distinguish a healthy completed title repair from an interrupted
or divergent batch without opening private evidence by hand. The audit result
becomes the factual input for a later single-case recovery planner/executor.
v0.3.270 itself cannot clean, resume, roll back, finalize, or revert anything.
