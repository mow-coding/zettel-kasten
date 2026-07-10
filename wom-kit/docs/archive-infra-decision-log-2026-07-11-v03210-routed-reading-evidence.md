# Decision Log: v0.3.210 Routed Reading Evidence

Date: 2026-07-11
Status: implemented

## Decision

Expose per-item seeded-walk reasons through an opt-in `routed_reading`
projection, while preserving `reading` as the compact exhaustive projection.
Bind strict chain progress to snapshot file-entry identity rather than zet id.

## Context

The v0.3.208 order was deterministic but did not say which passage introduced
each item. Adding verbose route metadata to every normal reading item increased
the 10,000-node estimate from about 1.41 million to 2.58 million tokens. A
compact route shape still costs more than normal reading, so route explanation
must remain an explicit tradeoff.

Duplicate zet ids also preserve multiple file nodes but make an id-only chain
digest ambiguous. Snapshot path-order identity distinguishes those file entries
without returning paths or the identity list.

## Consequences

- Normal `reading` payload size and page count remain unchanged.
- `routed_reading` requires seeded order and reports compact route evidence.
- Continuation schema v0.3 forces in-flight strict passes to restart.
- Entry identities and workload estimates are process-local cached evidence,
  never a persisted map, route ledger, receipt, or security proof.
