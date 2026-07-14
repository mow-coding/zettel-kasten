# Archive Infrastructure Decision Log: v0.3.237 Canonical Revision Restore Plan

Date: 2026-07-14
Decision: accepted for v0.3.237

## Context

Canonical revision receipts intentionally retain before/after hashes without
copying old knowledge text. This protects privacy and keeps receipts compact,
but means a receipt cannot itself perform a revert. Automatic reconstruction
from hashes would be impossible and unsafe.

## Decision

- Add CLI-only, read-only `zet-revision-restore-plan`.
- Require separately recovered complete old zet bytes under private restore
  scratch.
- Require the archive-wide revision receipt audit to be healthy first.
- Bind the current canonical file to the selected receipt's complete `after`
  state and the recovered proposal to its complete `before` state.
- Reapply current publication and quality policy to the historical bytes.
- Bind the audit digest, receipt, both states, restore delta, and policy results
  into one plan digest.
- Echo no private identity, path, filename, text, reviewer, provider value, or
  secret.
- Add no MCP tool and no writer in this release.

## Consequences

WOM now has an evidence-preserving bridge between a hash-only history and
privately recovered old content. A later AI session can prove that the proposed
old bytes are the exact reviewed predecessor without inventing memory or
editing canonical state.

The plan remains a stop point. A future restore writer needs a new approval
digest, explicit human review, serialization with the ordinary revision
writer, atomic exact-byte restore, immutable restore receipt, rollback, and
interruption recovery.
