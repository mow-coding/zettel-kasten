# Decision Log: v0.3.302 Saved-View Lifecycle

Date: 2026-08-07
Status: implemented and locally verified; remote release gates pending

## Context

WOM v0.3.301 can read, execute, diagnose, and recommend saved views but has no
official persistent writer. AI runtime guidance forbids direct persistent YAML
edits, so the workflow ends at a recommendation. Existing discovery also skips
unreadable or malformed YAML and does not establish archive-wide id uniqueness.

## Decision

Add a CLI-only saved-view create/revert lifecycle and make saved-view authority
inspection fail closed.

- A create request is a closed JSON Schema 2020-12 object stored under the
  archive's private scratch area.
- Only bounded scalar `facets.*` filters on recognized navigation axes are
  accepted in this batch.
- The current archive index must exist and every selected filter must match at
  least one current non-redacted indexed zet.
- Approval binds the request digest, complete view-authority digest, rendered
  bytes, deterministic target, and fresh plan digest.
- The writer creates a dedicated no-overwrite file; it never rewrites a human
  view file or appends to a nested `saved_views` list.
- A global saved-view lock serializes create, receipt-finalization, and revert.
- A matching writer-owned file with a missing receipt can finalize that receipt
  after fresh review; exact replay converges; every collision or drift blocks.
- Revert deletes only exact unchanged writer-owned bytes and writes a separate
  immutable receipt. It never restores or rewrites another view file.
- Ordinary output and receipts expose fixed classifications, counts, hashes,
  and archive-relative generated paths, not view names or facet values.

## Consequences

AI operators gain an official preview/approval path instead of direct YAML
mutation. Existing valid view files remain compatible. Previously hidden
corrupt or duplicate authority becomes visible and may block view operations
until a human repairs it. No MCP write tool, index rebuild, zettel mutation,
provider call, UI, background worker, or taxonomy inference is added.

## Local Verification

The release candidate passed the complete four-shard unittest manifest on the
Windows release machine: 2,278 tests passed and 24 environment-dependent tests
were skipped. The explicit pytest-native Win32, writer-authority, and
saved-view lifecycle suites passed 129 tests. Release-readiness hygiene,
package-resource synchronization, shard completeness, source and packaged
surface checks, and focused privacy, schema, routing, interruption, replay,
and exact-revert tests also passed. GitHub pull-request CI, branch-rule
activation, the annotated tag, the public wheel, and an isolated token-free
install remain separate remote release gates.
