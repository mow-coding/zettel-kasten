# View Recommendation Plan

Status: v0.4.0 read-only recommendation; v0.3.302 writer evidence is historical
Date: 2026-06-17

`view-recommendation-plan` is the safe next step after `view-health`.

Use it when saved views are empty or stale and the archive already has indexed
facet distributions. It proposes candidate saved-view filters from likely
navigation facets such as `subject`, `institution`, `record_type`,
`source_category`, and `domain`.

It does not edit `views/*.yml`. In v0.4.0 `saved-view-write` and
`saved-view-revert` approval return
`compound_exact_human_approval_binding_required` before private request/target
reads or mutation. They write no view, journal, or receipt.

## Commands

CLI:

Command shape:

```text
archive view-recommendation-plan <archive-root> --dry-run
```

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli view-recommendation-plan <archive-root> `
  --dry-run `
  --format json
```

MCP:

```text
view_recommendation_plan
```

Inputs:

- `archive_root`
- `dry_run`, which must be true
- optional `max_values`
- optional `max_recommendations`

## What It Reads

The planner reuses `view-health` signals:

- saved view definitions under `views/*.yml`,
- the generated local SQLite index at `db/archive-index.sqlite`,
- indexed facet rows for non-redacted zets,
- static facet role classification.

It does not read zettel bodies, object bytes, provider exports, or derived-text
bodies.

## Output Shape

The plan returns:

- saved view health summary counts,
- navigation/internal/unknown facet key counts,
- candidate single-facet saved views,
- suggested `view.ai.<axis>.<value>` ids,
- suggested `facets.<key>: <value>` filters,
- match counts from the generated index,
- whether that key/value pair is already used by an existing saved view filter.

Facet values are metadata and can be shown when safe. Unsafe values such as
provider URLs, local paths, or secret-like strings are redacted before output.

## Privacy And Safety Boundaries

`view-recommendation-plan` is read-only.

It does not:

- write view files,
- rewrite zettel facets,
- rebuild the index,
- read zettel bodies,
- echo zettel titles,
- print absolute local paths,
- echo provider URLs,
- call provider APIs,
- read object bytes,
- create provider or presigned URLs.

The recommendation is a proposal for human review. It does not decide the final
archive taxonomy.

## Relationship To `view-health`

Use `view-health` to diagnose whether saved views are active, empty, or blocked.

Use `view-recommendation-plan` when you want candidate replacement or expansion
filters based on actual indexed navigation facets.

After reviewing a recommendation, a private `saved-view-write-request/v0.1`
may be prepared only for dry-run validation or historical audit. In v0.4.0
`archive saved-view-write --approve` is unavailable and returns
`compound_exact_human_approval_binding_required`; an AI must not directly edit
persistent view YAML. See
[Saved-View Write And Exact Revert](saved-view-write.md).
