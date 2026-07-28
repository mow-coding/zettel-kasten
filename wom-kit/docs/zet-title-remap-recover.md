# zet Title Remap Recover

Status: v0.3.272 approval-gated single-case interrupted-title recovery

## Boundary

This command executes one fixed action from a complete
`zet-title-remap-recovery-plan`. It is CLI-only and is not an MCP tool.

It does not:

- choose a recovery direction;
- accept a proposal path, zet id, canonical path, title, or receipt path;
- resume an uncommitted title apply;
- create or finalize a title-remap receipt;
- delete or modify a verified completed receipt;
- delete prior-byte snapshots;
- revert a completed title change.

Since v0.3.274 completed-title revert is a separate command. This interrupted
apply executor still never executes or cleans a retained revert journal.
v0.3.275 adds a separate read-only decision plan for those journals, not new
authority for this executor.

## Preview

```text
archive zet-title-remap-recover <archive-root> \
  --case-sha256 sha256:<journal-bytes-digest> \
  --expected-plan-digest sha256:<complete-plan-digest> \
  --expected-action <fixed-action> \
  --dry-run \
  --format json
```

Alias:

```text
archive title-remap-recover <archive-root> ... --dry-run
```

Preview reruns the complete bounded plan and writes nothing. It succeeds only
when exactly one case SHA exists, the plan digest is unchanged, the expected
action matches, and that action is implemented.

## Approval

```text
archive zet-title-remap-recover <archive-root> \
  --case-sha256 sha256:<journal-bytes-digest> \
  --expected-plan-digest sha256:<complete-plan-digest> \
  --expected-action <fixed-action> \
  --approve \
  --reviewed-by person:<safe-reviewer-id> \
  --affirm-recovery-reviewed \
  --affirm-archive-quiescent \
  --format json
```

Approval requires all three human fields. The archive-quiescent affirmation
means the original title writer has stopped and no editor or other title writer
is active.

## Executable Actions

| Fixed action | Approved behavior |
|---|---|
| `cleanup_unstarted_title_transaction_evidence` | Verify every participant remains at its prior hash and every snapshot is intact, then remove only the matching common lock and transaction journal. |
| `rollback_uncommitted_title_apply_to_before` | Restore only participants currently at recorded after hashes from their verified complete prior-byte snapshots, reverify the whole batch at before hashes, then remove matching transaction evidence. |
| `cleanup_verified_completed_title_evidence` | Reverify the exact immutable final receipt and all after hashes, preserve the receipt byte-for-byte, then remove only matching transaction residue. |

`manual_forensic_hold` is never executable.

## Serialization And Revalidation

An approved run:

1. acquires a cross-platform non-blocking recovery-executor guard;
2. regenerates the complete plan under that guard;
3. finds exactly one private journal by its content-free case SHA-256;
4. rejects an invalid present common lock or a lock belonging to another case;
5. reacquires the common write lock only if it is genuinely absent;
6. revalidates journal bytes, participant hashes, prior-byte snapshots, and
   final-receipt state;
7. verifies each participant immediately before and after a safe-direction
   write;
8. reverifies the complete final participant state;
9. removes the matching common lock first and transaction journal second.

Removing the lock first is intentional. If the process stops before journal
cleanup, the retained journal has a missing lock that a fresh approved run can
reacquire. Deleting the journal first could leave an orphaned lock without the
private evidence needed to verify it.

## Interruption And Retry

Successful prior-byte restores are not reversed when a later restore fails.
The transaction journal and common lock remain. A hard exit releases the
operating-system recovery guard, while the durable journal and lock continue
to describe the interrupted state.

After any incomplete recovery:

1. stop writers and editors;
2. run a new `zet-title-remap-recovery-plan --dry-run`;
3. review its new counts, case, action, and plan digest;
4. supply a new approval.

A stale plan digest is rejected.

## Privacy

Output may include only the content-free case SHA, complete plan digest, fixed
action/state codes, counts, and write/cleanup booleans. It never echoes title
text/hash/length, body text, zet ids/paths, proposal SHA, journal/receipt/lock/
snapshot paths, reviewer ids, provider values, secrets, or absolute local
paths. It calls no provider or model and reads no secret store or environment
credential.

See also:

- [zet Title Remap Recovery Plan](zet-title-remap-recovery-plan.md)
- [zet Title Remap Receipt And Interruption Audit](zet-title-remap-receipt-audit.md)
- [zet Title Remap Write](zet-title-remap-write.md)
- [zet Title Remap Completed-Receipt Revert Plan](zet-title-remap-revert-plan.md)
- [Approved zet Title Remap Revert](zet-title-remap-revert.md)
- [zet Title Remap Revert Recovery Plan](zet-title-remap-revert-recovery-plan.md)
