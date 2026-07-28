# zet Title Remap Recovery Plan

Status: v0.3.274 read-only interrupted-apply recovery decision and executor handoff

## Command

```text
archive zet-title-remap-recovery-plan <archive-root> \
  --dry-run \
  --max-receipts 5000 \
  --max-journals 100 \
  --max-cases 100 \
  --format json
```

Alias:

```text
archive title-remap-recovery-plan <archive-root> --dry-run --format json
```

`--dry-run` is mandatory. The command calls the bounded title-remap receipt
audit and writes or deletes nothing.

## Fixed Decisions

| Observed evidence | Recommended action |
|---|---|
| all participants remain at recorded before hashes | `cleanup_unstarted_title_transaction_evidence` |
| participants are split between recorded before/after hashes | `rollback_uncommitted_title_apply_to_before` |
| all participants are at recorded after hashes but no verified receipt exists | `rollback_uncommitted_title_apply_to_before` |
| the exact final receipt is independently verified and journal cleanup was interrupted | `cleanup_verified_completed_title_evidence` |
| a participant, receipt, snapshot, journal, or common lock cannot be safely verified | `manual_forensic_hold` |

The two rollback cases are uncommitted because no verified final receipt marks
the apply as committed. Their complete original canonical bytes already exist
as verified prior-byte snapshots. This plan remains read-only; v0.3.272 can
execute one reviewed case through the separate approval-gated command.

## Common Lock

One common title-remap lock serializes title writers. A retained journal whose
matching lock is absent reports that a later executor must reacquire the common
lock. A present orphaned or invalid lock is a forensic hold and must not be
deleted or replaced by hand.

## Output Boundary

The plan returns:

- the complete source audit digest and recovery plan digest;
- one content-free case SHA-256 per retained journal;
- before/after/divergent/missing participant counts;
- final-receipt and common-lock states;
- fixed recommended action and reason codes;
- the number of participant writes a later approved executor would need.

It does not return:

- old or new title text, title hashes, or title lengths;
- canonical body text;
- zet ids or private canonical paths;
- proposal, receipt, journal, lock, or snapshot paths;
- reviewer ids, provider values, secrets, or absolute local paths.

## Incomplete Evidence

If the source audit is incomplete or the requested case page would omit any
retained transaction, the plan is `blocked`. A partial list is not safe
authority for recovery.

Invalid snapshots, unverified final receipts, divergent participants, invalid
journals, and orphaned or invalid common locks are
`manual_forensic_hold`. Preserve all evidence.

Since v0.3.274 the same bounded audit can return a retained `operation:
revert` journal. This older planner always maps that case to
`manual_forensic_hold` with
`title_revert_hard_exit_recovery_not_implemented`. It never misroutes a revert
journal into the interrupted-apply cleanup or rollback executor.

## Executor Handoff And Revert Boundary

v0.3.272 implements the separate CLI-only
`zet-title-remap-recover` executor. It reruns the complete plan, binds the
reviewed plan digest, case SHA-256, and exact action, revalidates every
participant and snapshot, and requires fresh approval plus an
archive-quiescence affirmation.

The executor can clean prepared apply residue, roll an uncommitted apply back to
verified prior bytes, or clean exactly verified stale-completed residue. It
cannot execute `manual_forensic_hold`, resume an apply, create/finalize a
receipt, delete snapshots, or process a retained revert journal. v0.3.273
handles the separate read-only planning step for a clean completed receipt and
v0.3.274 adds its separate approval-gated writer. Hard-exit revert recovery
remains a later, dedicated boundary.

See also:

- [zet Title Remap Write](zet-title-remap-write.md)
- [zet Title Remap Receipt And Interruption Audit](zet-title-remap-receipt-audit.md)
- [zet Title Remap Recover](zet-title-remap-recover.md)
- [zet Title Remap Completed-Receipt Revert Plan](zet-title-remap-revert-plan.md)
- [Approved zet Title Remap Revert](zet-title-remap-revert.md)
