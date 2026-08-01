# Decision Log - v0.3.295 Private Objet Metadata Contract

- Date: 2026-08-01
- Status: accepted
- Related release: v0.3.295

## Context

Letter 105 showed that an object may be preserved correctly but remain hard to
rediscover when a person remembers its original name instead of its SHA-256.
Putting private filenames directly into ordinary manifests, MCP results, or
the generated public-facing search surface would create a separate privacy
failure.

## Decision

Publish two closed Draft 2020-12 schemas and one pure reference module before
adding any writer or finder.

1. Keep SHA-256 as the only object identity.
2. Treat names as provenance-bound aliases.
3. Pin Unicode normalization and case-fold evidence to Unicode 17.0.0.
4. Decode an encoded component at most once and fail closed on unsafe input.
5. Keep extension, MIME, size, registry, and confusable evidence as separate
   axes; never infer stronger evidence from a filename suffix.
6. Separate private/restricted free-form projections from a structurally
   generic-only public projection.
7. Preserve ambiguity instead of choosing an input-order winner.
8. Keep all helpers in-memory and expose no new CLI, MCP, database, writer,
   migration, provider, or filesystem behavior.

## Consequences

- Later metadata writers and finders have a testable contract to reuse.
- Schema existence alone does not make the private rediscovery layer complete.
- Public output cannot gain a private filename field through a permissive
  branch.
- Search-key collision never becomes object equality.
- `unicodedata2==17.0.1` becomes a runtime dependency; the independent Draft
  validator remains test-only.
- The next release must implement its writer and receipt without absorbing the
  later index or finder authority.

## Follow-Up

v0.3.296 owns the approval writer and recovery, v0.3.297 owns receipt-bound
index ingestion/freshness, v0.3.298 owns the local private finder, and v0.3.299
owns source-coverage versus storage-integrity reporting.
