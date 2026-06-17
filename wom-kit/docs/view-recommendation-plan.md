# View Recommendation Plan

Status: v0.3.97 read-only saved view recommendation checkpoint
Date: 2026-06-17

`view-recommendation-plan` is the safe next step after `view-health`.

Use it when saved views are empty or stale and the archive already has indexed
facet distributions. It proposes candidate saved-view filters from likely
navigation facets such as `subject`, `institution`, `record_type`,
`source_category`, and `domain`.

It does not edit `views/*.yml`.

## Commands

CLI:

Command shape:

```text
archive view-recommendation-plan <archive-root> --dry-run
```

```powershell
python wom-kit\cli\archive.py view-recommendation-plan <archive-root> `
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

After a human edits `views/*.yml`, run `archive index` and `view-health` again.
