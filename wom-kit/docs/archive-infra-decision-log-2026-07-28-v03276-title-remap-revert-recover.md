# Archive Infrastructure Decision Log: v0.3.276 Title Revert Recover

Date: 2026-07-28
Status: accepted and implemented

## Context

v0.3.275 maps each complete retained title-revert transaction to one fixed
safe-direction decision. A process can still stop before the first canonical
restore, between participant restores, after every restore but before the
compensation receipt, or after the receipt but before evidence cleanup.

The interrupted-apply executor cannot be reused: its policy direction is to
undo an uncommitted apply, while a reviewed compensation must continue only
toward verified prior bytes.

## Decision

Add the separate CLI-only `zet-title-remap-revert-recover` executor.

- Bind one exact revert-journal SHA-256, the complete current plan digest, and
  the plan's fixed action.
- Choose exactly one of read-only preview or explicit approval.
- Require a safe reviewer id, recovery-reviewed affirmation, and
  archive-quiescent affirmation for approval.
- Serialize apply and revert recovery executors with the same non-blocking
  operating-system guard, then regenerate the complete plan under that guard.
- Locate all private evidence internally; accept no journal, receipt, snapshot,
  zet, title, or canonical path from the command line.
- Reacquire the common write lock only when absent and reject invalid or
  other-case locks.
- Execute only the four fixed non-forensic actions from v0.3.275.
- Continue a partial compensation only toward verified prior-byte snapshots and never
  reverse already restored participants after failure.
- Reconstruct the original deterministic compensation receipt from the
  original journal and immutable source apply receipt.
- Preserve an existing verified compensation receipt byte-for-byte.
- Remove the matching common lock before the journal only after final state
  and receipt verification.
- Retain remaining evidence and require a fresh plan and approval after every
  incomplete run.
- Keep `manual_forensic_hold` non-executable and keep the older interrupted-
  apply executor closed to revert cases.

## Approval Evidence Decision

The reconstructed compensation receipt must remain byte-for-byte equivalent to
the receipt the original approved revert would have produced. Therefore it
retains the original revert authorization.

The new recovery approval gates execution but v0.3.276 does not persist it in a
second immutable receipt. This limitation is explicit in the result and public
operator guide. A separate recovery-authorization receipt is deferred to a
later audit-hardening release rather than being mixed into the compensation
receipt or falsely claimed.

## Consequences

Operators can safely finish or clean one reviewed compensation transaction
without opening or hand-editing private evidence. Hard exits and cleanup
failures converge through a new plan instead of attempting an unsafe rollback
of successful compensation steps.

No provider/model call or MCP write surface is added. Prior-byte snapshots and
the immutable source apply receipt are never deleted.

## Standards Basis

- Git records a revert as a distinct compensating operation while preserving
  the original history:
  https://git-scm.com/docs/git-revert.html
- The compensating transaction pattern calls for state-aware, resumable,
  idempotent compensation steps and retained recovery evidence:
  https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction

WOM does not claim database transaction atomicity. It applies the narrower
discipline of durable prior-state evidence, exclusive recovery coordination,
fresh state revalidation, safe-direction retry, and cleanup only after
verified completion.
