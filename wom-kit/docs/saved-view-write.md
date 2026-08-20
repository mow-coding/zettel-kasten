# Saved-View Write And Exact Revert

Status: dry-run-only writer/revert in v0.4.0; v0.3.302 receipts are historical

Current boundary: `saved-view-write` and `saved-view-revert` approval fail with
`compound_exact_human_approval_binding_required` before private request/target
read or mutation. The plan and historical receipt/audit material below remain
useful, but no v0.4.0 approved command creates or deletes a view.

This command closes the gap between a read-only saved-view recommendation and
a persistent `views/*.yml` file. It is intentionally preview-first: an AI may
prepare a private request, but a human must review the real name and filters
before the exact plan can be approved.

## 1. Prepare The Private Request

Store one closed JSON object below
`.wom-scratch/private/saved-views/`. For example:

```json
{
  "schema": "wom-kit/saved-view-write-request/v0.1",
  "view_id": "view.ai.education",
  "name": "Education",
  "filters": {
    "facets.domain": "education"
  }
}
```

The request accepts one to eight scalar `facets.*` filters. Every key must be
a recognized navigation facet, every value must be safe bounded text, and the
combined filters must match at least one current non-redacted indexed zet.
Internal import bookkeeping facets are refused.

## 2. Preview Without Writing

```powershell
archive saved-view-write <archive-root> `
  --request .wom-scratch/private/saved-views/education.json `
  --dry-run `
  --format json
```

The plan binds the exact request bytes, canonical request, complete saved-view
authority, rendered YAML bytes, deterministic target path, match count, and
one `plan_sha256`. It does not echo the private view name, facet keys, facet
values, zettel titles, bodies, or absolute local paths.

## 3. Stop After The Fresh Plan

After a human opens the private request and verifies every name and filter,
stop. In v0.4.0 approval returns
`compound_exact_human_approval_binding_required` before reading the private
request/target or writing a view, lock, journal, or receipt. Historical
v0.3.302 receipts and `finalize_receipt` states remain audit evidence only.

## Exact Revert

Preview removal using the write receipt returned by the create command:

```powershell
archive saved-view-revert <archive-root> `
  --receipt receipts/views/<receipt>.saved-view-write.json `
  --dry-run `
  --format json
```

Keep revert in dry-run. v0.4.0 approval returns
`compound_exact_human_approval_binding_required` before reading the private
target or removing bytes; it writes no journal or revert receipt. Historical
v0.3 revert receipts remain readable but grant no current removal authority.

## Fail-Closed Authority

`view-zets`, `view-health`, `view-recommendation-plan`, this writer, and revert
share one strict direct `views/*.yml` authority scan. Invalid UTF-8 or YAML,
unsafe entries, oversized files, invalid ids or filters, and duplicate ids are
reported instead of silently skipped. `view-health` may still show safe
read-only diagnostics for parseable definitions, but its overall result stays
blocked until the authority is complete and unambiguous.

## Boundaries

- No MCP write tool is added. Persistent changes remain CLI-only.
- No existing human-authored view file is reformatted or appended to.
- No zettel, facet, object, index, provider, account, credential, or UI is
  changed.
- The request schema is
  `schemas/saved-view-write-request.schema.json`; write, revert, and journal
  evidence have separate closed schemas.
- Existing archive `AGENTS.md` files are never silently rewritten. New archive
  templates point AI operators to this official route.
