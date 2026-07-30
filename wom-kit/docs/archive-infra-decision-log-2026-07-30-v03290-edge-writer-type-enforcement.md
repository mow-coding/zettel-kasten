# Decision Log — v0.3.290 Edge Writer Entity-Type Enforcement

Date: 2026-07-30

## Context

The generic edge writer checked that a requested edge type ID existed and that
its records resolved, but it did not enforce the selected active type record's
`from` and `to` entity-type lists. Endpoint resolution and vocabulary
membership therefore did not together prove that the relationship shape was
valid.

The policy batch routes candidate writes through the same single-edge gate, so
the missing check affected both manual single writes and approved batch rows.

## Decision

Treat endpoint-type validation as part of the shared single-edge preflight.

- The writer source entity type is `Zettel`.
- A resolved zet target is `Zettel`.
- A resolved manifested objet target is `OriginalObject`.
- The selected active registry record must have non-empty string lists for
  both `from` and `to`.
- Both resolved endpoint types must be allowed before any source or receipt
  write.
- An archive-local registry is authoritative when present. Invalid local
  records fail closed rather than falling back to the packaged definition.
- Batch writing inherits the same gate and cannot approve an incompatible
  row.
- Returned contract facts and blockers remain bounded and content-free.

Do not activate sequence semantics, alter vocabulary, infer relationships,
add a provider or MCP write route, or migrate existing edges.

## Consequences

- Active edge IDs are no longer sufficient by themselves to authorize a
  write.
- `continues` remains `Zettel -> Zettel`; an objet target is rejected.
- `embed` remains `Zettel -> OriginalObject`; a zet target is rejected.
- `format_variant` retains both already-declared target entity types.
- Malformed archive-local type records stop the write instead of silently
  borrowing a packaged contract.
- Every policy batch candidate uses the same endpoint-type safety decision as
  the manual writer.
- Existing archives need no automatic migration because vocabulary and stored
  data are unchanged.

Implementation detail and verification evidence are recorded in
`meeting-minutes/2026-07-30-v03290-edge-writer-type-enforcement-implementation.md`.
