# zet Title Remap Recovery Plan

Status: v0.3.271 read-only interrupted-title recovery decision

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
as verified prior-byte snapshots. v0.3.271 only reports that fixed decision; it
does not restore those bytes.

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

## No Executor Or Revert

v0.3.271 cannot:

- create, replace, or delete a common lock;
- restore canonical bytes;
- resume a title apply;
- create or finalize a receipt;
- delete a transaction journal;
- revert a completed title-remap receipt.

A later single-case executor must rerun the complete plan, bind the reviewed
plan digest and case SHA-256, revalidate every participant and snapshot,
require fresh approval plus an archive-quiescence affirmation, and preserve all
evidence on any uncertain result.

See also:

- [zet Title Remap Write](zet-title-remap-write.md)
- [zet Title Remap Receipt And Interruption Audit](zet-title-remap-receipt-audit.md)
