# Archive Infrastructure Decision Log: v0.3.221 Abstract Receipt Audit

Date: 2026-07-11
Status: accepted and implemented

## Context

v0.3.219 and v0.3.220 can validate one known apply/revert lifecycle. Over time,
an AI operator could forget an old receipt, miss orphan evidence, or overlook a
lock left by forced termination. Listing every healthy receipt in JSON would
create a new context and token burden.

## Decision

- Add one archive-wide read-only audit for supported abstract revision receipts
  and recognized scratch locks.
- Require every applied receipt to verify either current applied state or one
  valid deterministic revert/current-reverted pair.
- Block malformed/diverged source evidence and orphan revert receipts.
- Read lock filenames only. Treat completed-operation residue as a warning and a
  lock without matching completion evidence as an unresolved blocker.
- Scan all inputs inside hard receipt/lock bounds, but collapse healthy outcomes
  into counts plus one audit digest.
- Return only bounded problem rows identified by kind, sorted index, hashes, and
  codes; echo no private path/content/reviewer value.
- Never clean locks, repair zets, or rewrite immutable evidence automatically.

## Consequences

An AI can now check that the abstract-revision subsystem is closed and locally
consistent without loading every healthy receipt into its context. Operators
still decide how to investigate and remove stale locks.

The audit is not semantic quality review, crash recovery, external-editor
locking, or remote backup verification. Archives with more than 5,000 supported
receipts or locks need a future paged audit rather than a false complete claim.
