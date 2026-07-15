# Decision Log: Preserve Canonical Bytes Before Revision

Date: 2026-07-15
Status: Accepted for v0.3.248

## Context

Ordinary revision receipts recorded complete before/after hashes but not the
previous bytes. That proved a change occurred while leaving recovery dependent
on a separately maintained private backup. This contradicted WOM's artifact
primacy at the exact point where an artifact was replaced.

## Decision

Every new approved ordinary canonical revision must, before replacement:

1. derive a SHA-256 object id from the exact prior canonical bytes;
2. write or verify those bytes in `objects/sha256/` without overwriting an
   existing destination;
3. register or verify one matching local object-manifest record;
4. bind the snapshot descriptor into the write-ahead lock; and
5. bind the same descriptor into a v0.2 immutable revision receipt.

The archive-wide revision audit verifies snapshot bytes and manifest evidence
for v0.2 receipts. v0.1 receipts remain valid legacy hash-only evidence because
the missing historical bytes cannot be invented after the fact.

## Consequences

- A newly corrected zet's exact prior bytes remain locally recoverable.
- A missing or changed snapshot prevents a new receipt from being treated as a
  healthy history event.
- Runtime rollback does not delete a verified snapshot; content addressing
  makes later reuse safe and deterministic.
- Git still tracks only text-free metadata. Snapshot content remains in the
  ignored object-byte store.

## Non-Goals

This decision does not declare remote backup complete, recreate bytes for old
v0.1 receipts, decide factual truth, auto-restore an old state, call a model or
provider, or add a UI.
