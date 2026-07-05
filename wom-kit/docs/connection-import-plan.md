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
notion_containment
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
| child page/database/view nesting | `contains` |

It also checks the current archive's `zettel-kasten/types.yml` and reports which
recommended edge types are allowed link types. The WOM-kit base and fake archive
types now define this connection vocabulary:

```text
material
derived
semantic
embed
mention
contains
supersedes
view_query
comment_context
```

This still does not write edges. It only means WOM can now name the connection
types before a future evidence parser or approval-gated edge writer exists.
`supersedes` is especially for reviewed version-chain evidence where a newer
zet replaces an older one.

`contains` is for structural nesting: a parent page or zet contains a child
page, child database, collection view, or equivalent nested archive object. It
must not be silently downgraded to `view_query`, `references`, `material`, or
`inherited_by`. If a future import finds evidence that does not fit the active
edge vocabulary, the parser or AI runtime should report a model gap and ask for
a developer decision before writing durable edges.

For the next pre-parser safety gate, see
[Connection Evidence Parser Contract](connection-evidence-parser-contract.md).

## Keeping a vendored `types.yml` in sync with the base (`base-link-types`)

An archive that vendored its own `zettel-kasten/types.yml` permanently shadows the
WOM-kit base: `load_allowed_link_types` returns the local set and never falls back to
the base once a local file exists. So base link types added after the archive vendored
its file — for example `continues` (added to the base in v0.3.168) — become invisible in
that archive and their edges fail the `allowed_edges` check.

Since v0.3.173, `archive migrate --target base-link-types (--dry-run | --approve)
[--reviewed-by <actor>] [--format json]` pulls the missing base link types into the
archive-local `types.yml`. It is append-only and no-clobber:

- It appends every base id missing from the archive (a strict superset of the
  recommended-9 connection-edge set above — it also covers `continues` and any other
  base-only id). After a sync, `migrate --target link-types-v0.3` is a no-op; after a
  prior `link-types-v0.3` migrate, sync adds only the non-recommended remainder.
- It never removes, renames, reorders, or overwrites an existing entry. An archive that
  customized a base id keeps its own entry (reported under `present_not_overwritten`).
- `--reviewed-by` is required with `--approve`. It writes a receipt
  (`receipt_kind: base_link_types_sync`) under `receipts/migrations/`, is atomic with
  rollback, and is idempotent (a second run with nothing missing is a clean no-op).
- There is **no `--revert`**: it is forward-only append.

Honesty boundary: if the archive has NO local `types.yml`, sync writes nothing — the
archive already inherits all current and future base link types, and adding a local
`types.yml` would permanently freeze that inheritance. When it does write, it normalizes
the whole `types.yml` via `safe_dump` (comments, anchors, flow-style, and key ordering
may be normalized), exactly like the sibling `link-types-v0.3` migration; existing
entries are preserved by value/id, and surrounding formatting is not byte-preserved. It
copies base entry shapes as of the release (a snapshot, not a live link).

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
