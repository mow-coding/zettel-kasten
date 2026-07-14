# Archive Infrastructure Decision Log

Date: 2026-07-14
Release: v0.3.238
Decision: Audit canonical revision receipts as chronological events before
implementing exact-byte restore writes.

## Context

The v0.3.236 audit reconstructed history by walking backward through unique
file hashes. The v0.3.237 restore planner made the next requirement visible:
an exact restore can legitimately create `A -> B -> A`. Hash-only traversal
would revisit the newest receipt and misclassify that valid repeated state as
a cycle.

## Decision

- Order each private canonical identity's receipts by normalized event time.
- Require unique event times and exact adjacent file, semantic, abstract, and
  body before/after states.
- Permit repeated states only when those chronological transitions remain
  complete.
- Continue blocking branch/replay evidence, partial state gaps, identity
  conflicts, and current canonical drift.
- Require a restore plan's selected receipt to equal the actual latest event,
  not merely an older receipt with a repeated matching after-state.
- Bind that latest event digest and receipt SHA into the content-free restore
  plan digest.
- Keep the release read-only. Implement no restore writer until this event
  interpretation passes focused and full regression tests.

## Consequences

The audit changes from linear hash traversal to bounded chronological sorting:
`O(receipt_files log receipt_files + revision_chains + lock_files)`. Each
receipt and lock is still opened once, each current canonical target is opened
at most once per private identity, and no per-receipt complete zet-tree scan or
quadratic pass is introduced.

This release proves local event-chain consistency only. It does not prove
facts, reconstruct missing text, write canonical bytes, create restore
receipts, synchronize backups, or authorize manual copying.
