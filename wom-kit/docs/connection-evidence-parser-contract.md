# Connection Evidence Parser Contract

Status: v0.3.80 read-only parser contract checkpoint

`archive connection-evidence-parser-contract` is the safety contract for a
future Notion connection evidence parser. It runs before any parser reads real
exports and before WOM writes candidate edges or durable edges.

The first supported source is `notion`.

## Command

```powershell
archive connection-evidence-parser-contract <archive-root> `
  --source notion `
  --connection-kind all `
  --dry-run `
  --format json
```

Aliases:

```text
connection-parser-contract
notion-connection-parser-contract
```

MCP tool:

```text
connection_evidence_parser_contract
```

## Accepted Input Lanes

The future parser may accept only safe, reviewed evidence lanes:

| Connection kind | Accepted evidence | Required safe fields |
| --- | --- | --- |
| `relation_property` | relation CSV rows or property snapshots | `source_export_ref`, `relation_source_ref`, `target_ref`, `relation_role`, `review_status` |
| `synced_block_reference` | synced block reference metadata or block snapshot refs | `source_export_ref`, `source_block_ref`, `synced_block_ref`, `direction_review_status` |
| `database_view_filter` | static data-source view/filter/query snapshot | `snapshot_id`, `source_export_ref`, `query_or_context_summary`, `result_refs`, `review_status` |
| `internal_url_hyperlink` | markdown or rich-text internal page-link metadata | `source_export_ref`, `source_page_ref`, `target_page_ref`, `link_context_ref`, `review_status` |
| `mention_page` | page mention metadata from rich-text or export markers | `source_export_ref`, `source_page_ref`, `mentioned_page_ref`, `mention_context_ref`, `review_status` |
| `comment_context` | comment mirror metadata without comment bodies | `snapshot_id`, `comment_context_ref`, `page_or_block_ref`, `result_refs`, `privacy_redactions`, `review_status` |
| `objet_embed` | object/embed refs from file blocks or resolved sha256 object refs | `source_export_ref`, `source_page_ref`, `object_id`, `review_status` |

Dynamic view/filter and comment-context evidence must include reviewed static
snapshots because their source context can change after export.

## Output Contract

A future parser may emit candidate edge records only. Required candidate fields:

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
```

`candidate_id` must be an opaque hash of safe refs and the connection kind. It
must not include page titles, comment bodies, provider URLs, local paths, account
ids, emails, tokens, or secret values.

This contract reuses the `connection-import-plan` mapping and the base WOM edge
vocabulary:

```text
material
derived
semantic
embed
mention
view_query
comment_context
```

## Parser Stages

A future parser must:

1. locate explicit, human-scoped evidence,
2. normalize provider refs into safe archive refs,
3. map evidence to WOM edge types,
4. require snapshots for dynamic view/filter and comment context evidence,
5. emit candidate records only,
6. wait for a later approval-gated writer before durable WOM edges exist.

## Official Source Basis

This contract follows official Notion documentation:

- Data source properties define schema columns, including `relation` and `files`:
  <https://developers.notion.com/reference/property-object>.
- Blocks represent page content and rich-text structures:
  <https://developers.notion.com/reference/block>.
- Comments are listed through separate comment endpoints and require connection
  capabilities: <https://developers.notion.com/reference/list-comments> and
  <https://developers.notion.com/reference/capabilities>.
- Data-source update work does not make a live view result a durable WOM edge
  list: <https://developers.notion.com/reference/update-a-data-source>.

## Closed Actions

This command does not:

- call Notion,
- start OAuth,
- open a Notion connection,
- read Notion export files,
- read comments,
- download media,
- execute a parser,
- write candidate edge records,
- write zets,
- write edges,
- write receipts,
- update object manifests,
- echo provider URLs, local absolute paths, raw export paths, page titles,
  comment bodies, account ids, emails, tokens, or secret values.

It only returns a read-only contract for the next parser implementation step.

For the first sanitized fixture-only parser, see
[Connection Evidence Fixture Parser](connection-evidence-fixture-parser.md).
