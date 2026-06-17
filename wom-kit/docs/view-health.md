# View Health

Status: v0.3.90 read-only saved view diagnostics
Date: 2026-06-17

`view-health` checks whether saved `views/*.yml` filters still match the
archive's indexed zet facets.

It exists because real archives can drift. A saved view may say:

```text
facets.domain: education
```

while the imported zets actually use different facet values. In that case
`view-zets` can correctly return zero zets, but the user still needs to know
why.

## Commands

CLI:

Command shape:

```text
archive view-health <archive-root> --dry-run
```

```powershell
python wom-kit\cli\archive.py view-health <archive-root> `
  --dry-run `
  --format json
```

MCP:

```text
view_health
```

Inputs:

- `archive_root`
- `dry_run`, which must be true
- optional `max_values`

## What It Reads

The command reads:

- saved view definitions under `views/*.yml`,
- the generated local SQLite index at `db/archive-index.sqlite`,
- indexed facet rows for non-redacted zets.

It does not read zettel bodies, object bytes, provider exports, or derived-text
bodies.

## Output Shape

The health report includes:

- saved view counts by `active`, `empty_result`, and `blocked`,
- one result row per saved view,
- normalized facet filters,
- per-filter `matching_zettel_count`,
- observed facet value samples for the keys used by saved views,
- next safe actions.

An `empty_result` view is not automatically wrong. It means the saved filters
currently match zero indexed non-redacted zets and should be reviewed against
the observed facet distribution.

## Privacy And Safety Boundaries

`view-health` is read-only.

It does not:

- write view files,
- rewrite zettel facets,
- run `archive index`,
- read zettel bodies,
- echo zettel titles,
- print absolute local paths,
- echo provider URLs,
- call provider APIs,
- read object bytes,
- create provider or presigned URLs.

Facet values are metadata and can be shown as distribution samples. Unsafe
facet values such as provider URLs, local paths, or secret-like strings are
redacted before output.

## Relationship To `view-zets`

Use `view-zets` when you already know which saved view or facet query you want
to execute.

Use `view-health` when a saved view returns zero zets, blocks, or looks stale.
It helps decide whether to rebuild the index, repair unsupported filters, or
edit `views/*.yml` after review.
