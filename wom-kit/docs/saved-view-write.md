# Saved-View Write And Exact Revert

Status: v0.3.302 approval-gated saved-view lifecycle

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

## 3. Approve The Exact Fresh Plan

After a human opens the private request and verifies every name and filter:

```powershell
archive saved-view-write <archive-root> `
  --request .wom-scratch/private/saved-views/education.json `
  --expected-plan-sha256 sha256:<64-hex> `
  --approve `
  --reviewed-by person:<reviewer> `
  --affirm-view-reviewed `
  --format json
```

If the request, archive index, existing views, target, or receipt changed after
preview, the old plan is refused. The writer creates one deterministic
`views/generated-*.yml` file without overwriting an existing file, plus one
immutable content-free receipt under `receipts/views/`.

If the process created the exact view file but stopped before its receipt was
written, a new dry-run returns `finalize_receipt`. A human must review and
approve that new plan digest. Exact replay then converges.

## Exact Revert

Preview removal using the write receipt returned by the create command:

```powershell
archive saved-view-revert <archive-root> `
  --receipt receipts/views/<receipt>.saved-view-write.json `
  --dry-run `
  --format json
```

Approve only its exact fresh plan:

```powershell
archive saved-view-revert <archive-root> `
  --receipt receipts/views/<receipt>.saved-view-write.json `
  --expected-plan-sha256 sha256:<64-hex> `
  --approve `
  --reviewed-by person:<reviewer> `
  --format json
```

Revert removes only the unchanged writer-owned YAML bytes named by the
receipt. Any human edit, collision, malformed evidence, duplicate id, or
incomplete saved-view authority blocks removal. A short transaction journal
makes interruption resumable, and a separate immutable revert receipt proves
the completed removal.

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
