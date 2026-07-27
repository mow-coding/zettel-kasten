# Archive Infra Decision Log - v0.3.266 Abstract Recovery Plan

Date: 2026-07-27

Status: accepted for implementation

## Context

v0.3.265 records an approved abstract apply or revert transaction before its
first canonical mutation and classifies retained evidence as `prepared`,
`partially_applied`, `fully_applied_receipt_missing`, `divergent`, or
`stale_completed`. Detection alone intentionally grants no recovery authority.

The next safe rung is a deterministic read-only decision surface. Implementing
canonical recovery in the same change would hide unresolved authority,
reconstruction, idempotency, and concurrency choices inside write code.

## Decision

Add `archive zet-abstract-backfill-recovery-plan <archive-root> --dry-run`
(alias `archive abstract-backfill-recovery-plan`). It reuses the bounded
receipt/lock/journal audit evidence and emits one privacy-safe case per retained
journal, subject to an explicit case limit.

The action matrix is:

- `prepared` -> `cleanup_unstarted_transaction_evidence`;
- interrupted apply -> `rollback_uncommitted_apply_to_before`;
- partial revert -> `resume_revert_forward_and_finalize_receipt`;
- fully applied revert without a receipt ->
  `finalize_revert_receipt`;
- `stale_completed` -> `cleanup_verified_completed_evidence`;
- `divergent`, `invalid`, or any present-but-unverified deterministic final
  receipt -> `manual_forensic_hold`.

The planner reports only a recommendation. Every case has
`execution_implemented: false`, `safe_to_execute_now: false`, and
`fresh_recovery_approval_required: true`.

## Why Apply Rolls Back But Revert Moves Forward

Apply rollback is reconstructible without stored private text: removing the
inserted `frontmatter.abstract` can be verified against the journal's before
hash. Revert rollback is not generally reconstructible because the removed
abstract text is intentionally absent from journals and receipts. The
reconstructible safe direction for an interrupted approved revert is forward:
remove the field from remaining before-state participants and then publish the
deterministic text-free revert receipt.

The final write executor is not part of this release and must independently
prove that reconstruction, approval, lock acquisition, immediate participant
revalidation, receipt ownership, rollback, and retry behavior are correct.

## Receipt And Lock Interpretation

A final receipt is `verified` only when the complete existing receipt lifecycle
audit accepts it. A file merely occupying the deterministic receipt path is
`present_unverified` and forces manual hold. This prevents an empty, malformed,
external, or drifted receipt from being treated as authorization.

The expected basis lock is reported as evidence only. Its content remains
unread. A missing lock does not authorize recovery; a future executor must
decide whether and how to reacquire it.

## Privacy Boundary

The basis SHA-256 is the public case handle because the older receipt/lock
surface already permits that hash. The planner does not emit private paths,
zettel identifiers, reviewer identity, proposal filename, abstract/body text,
journal digest, lock content, or absolute paths.

## Explicit Non-Goals

- no canonical write or rollback;
- no receipt creation, replacement, or deletion;
- no journal or lock cleanup;
- no automatic recovery on normal apply/revert startup;
- no cross-basis participant locking;
- no recovery for other multi-zet writers;
- no claim of Windows sudden-power-loss durability.

## Consequences

Operators and a later executor receive one stable, reviewable policy for every
observed journal state without mutating the archive. The subsequent write
release can be reviewed against this contract instead of inventing its recovery
direction inside exception handling.

## Implementation Outcome

The accepted decision is implemented in v0.3.266 with:

- a strict dry-run CLI command and alias;
- independently bounded journal cases rather than a recovery list that can be
  starved by earlier receipt/lock problem rows;
- explicit `verified`, `absent`, `present_unverified`, and `unknown` final
  receipt states;
- expected lock-state reporting without lock-content reads;
- fixed action/reason codes and future write counts;
- an all-false write boundary and unimplemented execution boundary.

Verification passed the 28-test abstract-backfill group, the complete
120-test/3,395-subtest documentation suite, all four release-readiness gates,
the complete repository suite at 1,554 passed plus 13 skipped and 4,254
subtests, and an isolated v0.3.266 wheel smoke with 108 entries and 93 packaged
resources.
