# Connection Evidence Fixture Parser

Status: v0.3.81 read-only sanitized fixture parser checkpoint

`archive connection-evidence-parse-fixture` is the first parser-shaped checkpoint
for Notion connection evidence. It reads only a sanitized JSON fixture inside an
archive root and returns candidate edge previews. It does not read real Notion
exports.

## Command

```powershell
archive connection-evidence-parse-fixture <archive-root> `
  --evidence workbench/connection-evidence.sample.json `
  --source notion `
  --connection-kind all `
  --dry-run `
  --format json
```

Aliases:

```text
connection-evidence-parser-fixture
notion-connection-evidence-parser-fixture
```

MCP tool:

```text
connection_evidence_parse_fixture
```

## Fixture Boundary

The fixture path must be archive-relative. Absolute paths, parent-directory
segments, local paths, provider URLs, token-like values, and secret-like values
are rejected.

The fake archive includes:

```text
workbench/connection-evidence.sample.json
```

That fixture uses only safe refs such as `zet:fake:*`, `page:fake:*`,
`block:fake:*`, `snapshot:fake:*`, and `sha256:<hex>`. It includes no page
titles, raw URLs, local paths, account ids, emails, comment bodies, tokens, or
secret values.

## Output

The parser returns candidate edge previews with:

```text
candidate_id
connection_kind
edge_type
source_ref
target_ref
confidence
snapshot_ref
review_status
evidence_ref
write_status
```

`write_status` is always `not_written` in this release.

The sample fixture covers:

- `relation_property` -> `material` and `derived`,
- `synced_block_reference` -> `semantic`,
- `database_view_filter` -> `view_query`,
- `internal_url_hyperlink` -> `semantic`,
- `mention_page` -> `mention`,
- `comment_context` -> `comment_context`,
- `objet_embed` -> `embed`.

## Closed Actions

This command does not:

- call Notion,
- start OAuth,
- open a Notion connection,
- read real source export files,
- read comments,
- download media,
- write candidate edge records,
- write zets,
- write edges,
- write receipts,
- update object manifests,
- echo provider URLs, local absolute paths, raw export paths, page titles,
  comment bodies, account ids, emails, tokens, or secret values.

It reads one sanitized archive-internal fixture and returns read-only candidate
edge previews for test coverage.
