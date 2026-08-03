# Decision Log — Letter 105 Objet Rediscovery Release Train

- Date: 2026-07-30
- Status: accepted
- Related record:
  `meeting-minutes/2026-07-30-letter105-objet-rediscovery-intake.md`

## Context

Letter 105 confirms that a preserved object can be physically intact yet still
be falsely reported absent when an AI skips WOM's official search route,
original-name provenance was not indexed, an external local store is not
registered, or applicable search layers were not checked.

The reported tie-count contradiction is a separate bounded defect:
overview/catalog counts omit valid structured objet edge targets even though
the edge preview and `zettel-objet-links` can find them.

## Decision

Treat rediscovery as a multi-layer evidence problem rather than one broad
search patch.

1. Fix only structured tie-count consistency in v0.3.292.
2. Add read-only guidance readiness and feedback routing in v0.3.293.
3. Add a checked-layer rediscovery plan with fail-closed
   `search_incomplete` in v0.3.294 without changing the meaning of the existing
   `search.complete` field.
4. In v0.3.295, define private original-name/provenance and safe-label
   contracts before adding any writer or finder.
5. In v0.3.296, add only approval-gated private metadata writing, an immutable
   receipt, and replay/recovery.
6. In v0.3.297, add receipt-bound generated-index ingestion and freshness; in
   v0.3.298, add the bounded local private finder.
7. In v0.3.299, add source-reference coverage after applicable layers have
   stable states, and keep it independent from successful-object storage
   integrity.
8. Keep external-local-store trust registration and later one-object resolver
   access outside those private-metadata slices.

## Consequences

- SHA-256 remains object identity; human names are additive, provenance-bound
  aliases and never physical storage names.
- A zero-result index query cannot support a global absence claim.
- Existing `AGENTS.md` files are never overwritten without approval.
- No arbitrary external folder is scanned or opened.
- Private filenames, source identifiers, absolute paths, provider locators,
  and secret-like values remain out of generic/public projections.
- `storage_integrity: complete` and
  `source_reference_coverage: incomplete` may both be true.
- Each slice requires focused regressions, independent review, exact-predecessor
  rebase, complete suite, clean-wheel verification, and public artifact
  verification before beta semantic retesting.
- v0.3.295 supplies only schemas and pure in-memory reference behavior. The
  checked-layer private metadata state remains non-complete until the later
  writer, index, and finder releases exist.
- v0.3.298 completes the planned bounded local finder slice with exact
  generated-index equality and a scoped negative result. It does not complete
  source-reference, external-store, storage-integrity, or global absence
  coverage.
