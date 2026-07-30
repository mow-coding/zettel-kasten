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
4. Define private original-name/provenance and safe-label contracts before
   adding any writer or finder.
5. Add approval-gated private metadata registration and search only after that
   contract is stable.
6. Separate external-local-store trust registration from later one-object
   resolver access.
7. Add source-reference coverage only after all applicable layers have stable
   states, and keep it independent from successful-object storage integrity.

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
