# Archive Infrastructure Decision Log: v0.3.274 Title Remap Revert

Date: 2026-07-28
Status: accepted and implemented

## Context

v0.3.273 can prove that one completed title-remap receipt has a clean,
deterministic, exact prior-byte compensation. Letter 101 still requires the
actual reviewed undo operation. Copying snapshots by hand would bypass
approval, serialization, receipt history, ordinary-failure rollback, and
hard-exit diagnosis.

## Decision

Implement CLI-only `zet-title-remap-revert` as an approval-gated compensating
transaction.

- Bind the exact immutable source-receipt SHA-256 and current revert-plan
  digest.
- Require a safe reviewer, explicit review of every title reversion, and
  explicit archive quiescence.
- Serialize with the same common title-remap write lock used by apply and
  interrupted-apply recovery.
- Recompute the complete plan under that exact owned lock.
- Restore only verified complete prior-byte snapshots.
- Preserve the source receipt and append one separate immutable revert
  receipt.
- Publish a private revert transaction journal before the first canonical
  write.
- Roll caught failures back to exact applied bytes.
- Extend the archive-wide audit to validate completed compensation pairs and
  classify retained revert journals.

## Consequences

Completed title changes can now be reversed without deleting their original
history. The resulting apply/revert pair remains independently auditable and
the plan binding is recomputable because the compensation receipt stores the
planner version and pre-revert complete history-audit digest.

Forced-termination evidence is durable but not automatically recovered.
Read-only revert recovery planning and its later approval-gated executor remain
separate future release boundaries.

## Standards Basis

- Git revert preserves the original commit and records a new inverse change:
  https://git-scm.com/docs/git-revert.html
- The compensating transaction pattern requires stored undo information,
  current-state revalidation, idempotence, and end-to-end audit:
  https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction
