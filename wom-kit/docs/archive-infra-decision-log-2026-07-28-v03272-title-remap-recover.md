# Archive Infra Decision Log - v0.3.272 Title Remap Recover

Date: 2026-07-28

Status: accepted for implementation

## Context

v0.3.269 preserves complete prior canonical bytes and publishes a private
transaction journal before title writes. v0.3.270 audits retained evidence,
and v0.3.271 fixes one privacy-safe recovery action per journal. The remaining
interrupted-write gap is execution.

An executor must not infer policy, accept private paths from the command line,
replace uncertain locks, or turn a stale plan into authority.

## Decision

1. Add CLI-only `zet-title-remap-recover`, alias
   `title-remap-recover`; expose no MCP method.
2. Bind exactly one journal-byte case SHA-256, the complete current plan
   digest, and the exact fixed action. Choose exactly one of dry-run or
   approve.
3. Require a safe reviewer id, recovery-reviewed affirmation, and explicit
   archive-quiescent affirmation for approval.
4. Serialize executors with a non-blocking operating-system recovery guard and
   regenerate the complete plan under that guard.
5. Preserve a valid common title write lock that matches the selected journal.
   Create it with exclusive-create semantics only when absent. Block an invalid
   present lock or a lock bound to another case.
6. Execute only:
   - `cleanup_unstarted_title_transaction_evidence`: prepared evidence
     cleanup with zero canonical writes;
   - `rollback_uncommitted_title_apply_to_before`: uncommitted partial/full
     apply rollback to verified prior-byte snapshots;
   - `cleanup_verified_completed_title_evidence`: verified stale-completed
     residue cleanup that preserves the immutable receipt byte-for-byte.
7. Never execute `manual_forensic_hold`, resume an uncommitted apply, create or
   finalize a receipt, delete snapshots, or revert a completed title change.
8. Verify each source immediately before write, each target immediately after
   write, and the whole final participant state before evidence cleanup.
9. Delete the matching common lock before the journal. If journal cleanup then
   fails, a fresh plan can safely report and reacquire the missing lock.
10. On any incomplete write or cleanup, retain remaining evidence and require a
    fresh plan and fresh approval.

## Standards Cross-Check

SQLite's atomic-commit documentation preserves original state before mutation,
serializes recovery, and removes rollback evidence only after restoration.
PostgreSQL's WAL introduction documents the same narrow write-ahead principle.

Python documents `os.O_CREAT | os.O_EXCL` and `os.fsync` on Unix and Windows.
It documents Unix `fcntl.flock(..., LOCK_EX | LOCK_NB)` and Windows
`msvcrt.locking(..., LK_NBLCK, ...)` as non-blocking lock primitives that
raise `OSError` when unavailable.

Primary references:

- https://sqlite.org/atomiccommit.html
- https://www.postgresql.org/docs/16/wal-intro.html
- https://docs.python.org/3/library/os.html
- https://docs.python.org/3/library/fcntl.html
- https://docs.python.org/3.13/library/msvcrt.html

WOM does not claim database-level atomicity. It adopts only the relevant
discipline: durable prior-state evidence, exclusive recovery coordination,
state revalidation, safe-direction retry, and evidence cleanup after verified
completion.

## Consequences

Operators can now recover one reviewed interrupted title transaction without
opening private journals or manually editing canonical files. A hard exit may
leave a smaller unfinished restore set, but the durable journal and common lock
remain and the old plan becomes invalid. Completed-title revert remains a
separate design and release boundary.
