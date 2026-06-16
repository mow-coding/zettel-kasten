# Connection Import Plan

Status: v0.3.79 read-only connection edge vocabulary checkpoint

`archive connection-import-plan` is a pre-import safety label for connection
evidence. It is meant to run before WOM writes any new `edges` to canonical
zets.

The first supported source is `notion`.

## Command

```powershell
archive connection-import-plan <archive-root> `
  --source notion `
  --connection-kind all `
  --dry-run `
  --format json
```

Supported connection kinds:

```text
relation_property
synced_block_reference
database_view_filter
internal_url_hyperlink
mention_page
comment_context
objet_embed
```

## What It Plans

The planner maps captured Notion connection evidence to WOM typed-edge
candidates:

| Notion evidence | WOM candidate edge type |
| --- | --- |
| relation/pre/post properties | `material`, `derived` |
| synced block reference | `semantic` |
| database view/filter result | `view_query` |
| internal Notion hyperlink | `semantic` |
| page mention | `mention` |
| page/block comment context | `comment_context` |
| file/embed/object reference | `embed` |

It also checks the current archive's `zettel-kasten/types.yml` and reports which
recommended edge types are allowed link types. The WOM-kit base and fake archive
types now define this connection vocabulary:

```text
material
derived
semantic
embed
mention
view_query
comment_context
```

This still does not write edges. It only means WOM can now name the connection
types before a future evidence parser or approval-gated edge writer exists.

## Dynamic Snapshot Rule

Database views and filters are dynamic. A view result can change after export,
and Notion API view management is limited. WOM should not treat a live or
exported view as a permanent edge list until a static snapshot is reviewed.

A safe snapshot records:

- `snapshot_id`,
- `source_system`,
- `source_export_ref`,
- `captured_at`,
- `captured_by`,
- `view_or_comment_ref`,
- `query_or_context_summary`,
- `result_refs`,
- `privacy_redactions`,
- `review_status`.

## Official Source Basis

This plan follows official Notion documentation:

- Relation properties are page references in a data source property:
  <https://developers.notion.com/reference/property-object>.
- Blocks represent Notion page content, including rich-text mentions:
  <https://developers.notion.com/reference/block>.
- Comments require comment capabilities and are listed separately from page
  content: <https://developers.notion.com/reference/list-comments> and
  <https://developers.notion.com/reference/capabilities>.
- Data source view management is not the same as row/page update work:
  <https://developers.notion.com/reference/update-a-data-source>.

## Closed Actions

This command does not:

- call Notion,
- start OAuth,
- open a Notion connection,
- read Notion export files,
- read comments,
- download media,
- write zets,
- write edges,
- write receipts,
- update object manifests,
- echo provider URLs, local absolute paths, page titles, comment bodies, account
  ids, emails, tokens, or secret values.

It only returns a read-only plan for future connection import and edge typing.
