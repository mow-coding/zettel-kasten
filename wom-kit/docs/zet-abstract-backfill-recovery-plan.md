# zet Abstract Backfill Recovery Plan

Status: read-only decision surface since v0.3.266; single-case executor available since v0.3.267

## Purpose

v0.3.265 made an interrupted abstract apply or revert transaction observable.
The archive-wide audit can tell whether all participants are still before the
operation, some changed, all changed without a receipt, a participant diverged,
or a verified receipt exists but cleanup stopped.

`zet-abstract-backfill-recovery-plan` turns that evidence into one fixed,
human-reviewable recommendation per retained journal. It does not execute the
recommendation.

## Command

```text
archive zet-abstract-backfill-recovery-plan <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-cases 100 --progress --format json
```

Alias:

```text
archive abstract-backfill-recovery-plan
```

`--dry-run` is required. The planner reuses the complete bounded receipt,
transaction-lock, journal, and current-canonical hash audit. It returns at most
500 cases and blocks instead of calling a truncated plan complete.

## Decision Matrix

| Evidence | Apply recommendation | Revert recommendation |
| --- | --- | --- |
| `prepared` | `cleanup_unstarted_transaction_evidence` | `cleanup_unstarted_transaction_evidence` |
| `partially_applied` | `rollback_uncommitted_apply_to_before` | `resume_revert_forward_and_finalize_receipt` |
| `fully_applied_receipt_missing` | `rollback_uncommitted_apply_to_before` | `finalize_revert_receipt` |
| `stale_completed` | `cleanup_verified_completed_evidence` | `cleanup_verified_completed_evidence` |
| `divergent` or `invalid` | `manual_forensic_hold` | `manual_forensic_hold` |
| deterministic receipt present but unverified | `manual_forensic_hold` | `manual_forensic_hold` |

The apply and revert directions differ because their private reconstruction
limits differ:

- apply rollback can remove the inserted `frontmatter.abstract` and verify the
  exact journaled before hash without storing the text elsewhere;
- after revert has removed an abstract, its text cannot be recreated from the
  journal or receipt because both intentionally store hashes rather than
  private abstract text;
- completing the approved revert forward remains reconstructible from any
  participants still at the journaled before state.

Since v0.3.267, every non-forensic case reports that the separate single-case
executor is implemented. The plan itself remains read-only and still grants no
write authority.

## Receipt And Lock Evidence

Each case reports:

- `basis_sha256`, the transaction handle already permitted by the older
  receipt/lock audit output;
- operation and observed state;
- before, after, divergent, and missing participant counts;
- `final_receipt_state`: `absent`, `verified`, `present_unverified`, or
  `unknown`;
- `expected_lock_state`: `present`, `missing`, `unsupported`, or `unknown`;
- a fixed recommendation and fixed reason code;
- the number of canonical or receipt writes that a future approved executor
  would need.

`verified` means the complete matching receipt lifecycle passed the existing
audit. An empty, malformed, external, or state-diverged file at the
deterministic receipt path is `present_unverified`; file existence never
becomes cleanup or finalization authority.

Lock content is never read. A missing lock is reported so a later executor can
require deliberate reacquisition instead of pretending the old exclusion still
exists.

## Approval And Execution Boundary

Every case reports:

```text
fresh_recovery_approval_required: true
current_state_revalidation_required: true
execution_implemented: true  # false only for manual_forensic_hold
safe_to_execute_now: false
```

The planner command never:

- modifies a canonical zet;
- creates, edits, replaces, or deletes a receipt;
- creates or removes a lock;
- removes or rewrites a journal;
- resumes an apply or revert automatically;
- serializes different transaction bases that happen to share participants.

Do not carry out the recommendation by hand. Retain the journal and lock, then
bind one non-forensic case to the separate
`zet-abstract-backfill-recover` command with the complete plan digest, exact
basis SHA-256, exact action, fresh approval, and archive-quiescence
affirmation. See [zet Abstract Backfill Recovery Executor](zet-abstract-backfill-recover.md).

## Privacy Boundary

The planner may read private journal ids, paths, reviewer metadata, receipt
metadata, and canonical bytes needed for hash validation. Its output does not
contain:

- journal or receipt paths;
- zet ids or paths;
- reviewer identity;
- proposal filename;
- body or abstract text;
- journal digest;
- lock content;
- absolute local paths.

It calls no model, provider, credential store, secret store, database, or
network.

## Result Meaning

- `no_recovery_needed`: no retained abstract transaction journal was found.
- `ready_for_human_recovery_review`: every returned case has a fixed
  non-forensic recommendation, but no write is implemented.
- `manual_forensic_hold`: at least one case is invalid, divergent, or has an
  unverified deterministic receipt.
- `blocked`: bounded source inspection or case coverage was incomplete.

This plan proves only that a bounded local decision was derived from current
hash evidence. It does not prove semantic abstract quality, external-editor
exclusion, approved recovery execution, remote backup, or Windows
sudden-power-loss durability.
