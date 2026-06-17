# Index Health

Status: v0.3.91 read-only generated index drift check
Date: 2026-06-17

`index-health` checks whether the generated local SQLite index still matches
the live zettel files.

The index is disposable and rebuildable. Commands such as `view-zets`,
`view-health`, `related-zets`, and `search` depend on it, so stale index rows
can make a real archive look emptier or older than it is.

## Commands

CLI:

Command shape:

```text
archive index-health <archive-root> --dry-run
```

```powershell
python wom-kit\cli\archive.py index-health <archive-root> `
  --dry-run `
  --format json
```

MCP:

```text
index_health
```

Inputs:

- `archive_root`
- `dry_run`, which must be true
- optional `max_items`

## What It Checks

The command compares:

- live zettel archive-relative paths,
- indexed zettel paths,
- live and indexed `zettel_id`, `status`, and `kind`,
- zettel files modified after `db/archive-index.sqlite`.

It can report:

- `live_zettels_missing_from_index`,
- `index_has_paths_missing_from_live_zettels`,
- `indexed_zettel_metadata_differs_from_live_frontmatter`,
- `live_zettel_modified_after_index`,
- `archive_index_missing`.

## Safety Boundary

`index-health` is read-only.

It does not:

- rebuild the index,
- write files,
- edit zettels,
- read object bytes,
- call provider APIs,
- echo zettel body text,
- echo zettel titles,
- print absolute local paths,
- echo provider URLs.

It returns only archive-relative sample paths and basic drift counters.

## Relationship To `archive index`

Use `index-health` to decide whether the generated index is stale.

Use `archive index` to rebuild the index after review. Rebuilds remain explicit;
`index-health` never runs them automatically.
