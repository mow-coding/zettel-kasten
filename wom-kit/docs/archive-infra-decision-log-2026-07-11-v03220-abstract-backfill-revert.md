# Archive Infrastructure Decision Log: v0.3.220 Abstract Backfill Revert

Date: 2026-07-11
Status: accepted and implemented

## Context

v0.3.219 made abstract backfill auditable and transactional, but a later removal
would otherwise require manual frontmatter edits. Manual removal would lose the
source receipt binding, exact-before proof, human removal authority, and
whole-batch rollback behavior.

## Decision

- Make the immutable applied receipt, not the disposable proposal, the revert
  authority input.
- Require the exact source receipt SHA-256 for audit and approval.
- Prove the inverse by removing only the deterministic first `abstract:` line
  and requiring the reconstructed bytes to equal `before_file_sha256`.
- Block the complete batch on any canonical drift after application.
- Keep dry-run audit separate from a new attributed human removal approval.
- Preserve the source receipt and write one immutable text-free revert receipt
  last.
- On runtime failure, restore every attempted target to its exact applied bytes.
- Treat a matching revert receipt/current-state pair as no-write
  `already_reverted`.
- Put the advisory per-receipt lock under private `.wom-scratch/`, not in the
  durable receipt directories.

## Consequences

WOM can now audit and reverse this one canonical interpretation without storing
body snapshots in receipts or trusting a regenerated proposal. The applied and
revert receipts preserve both human decisions.

The operation is deliberately narrow. It is not a general revision engine, does
not merge later edits, does not lock external editors, and does not recover from
forced termination. Reapplication requires a newly reviewed proposal byte
sequence and new proposal hash rather than deleting old evidence.
