# Decision Log: Before-Snapshot Restore Proposal Bridge

Date: 2026-07-15
Status: implemented for v0.3.249

## Decision

Add a CLI-only, approval-gated command that turns one verified v0.2 canonical
revision before-snapshot into an independent private restore proposal.

## Context

v0.3.248 preserved exact prior canonical bytes and made audit verify them, but
the restore planner still required a human or AI operator to place the bytes in
private scratch manually. The missing bridge made preserved history harder to
use and invited unsafe hand-copy shortcuts.

## Consequences

- Dry-run verifies the receipt, complete history, snapshot bytes, and manifest
  record, then binds a SHA-derived destination into a plan digest.
- Approval creates no canonical or durable metadata change; it creates only a
  reproducible private working copy.
- The destination is never overwritten.
- The proposal must not share storage identity with the immutable snapshot.
- The existing restore plan, human review, and approved restore writer remain
  the only route to a canonical state change.
- Legacy v0.1 receipts cannot use the bridge because they did not bind preserved
  prior bytes.
