# Notion Nested Tree Plan

Status: v0.3.125 read-only nested child-page recovery checkpoint

`archive notion-nested-tree-plan` plans recovery for Notion pages nested inside
other pages. It is for the gap where a database-row import is already safe, but
deeper `parent=page` child pages may have been missed.

This command reads only a sanitized archive-internal tree fixture. It does not
read real Notion exports, page titles, page bodies, comments, or media.

## Command

```powershell
archive notion-nested-tree-plan <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --source notion `
  --dry-run `
  --format json
```

Aliases:

```text
notion-nested-page-tree-plan
notion-child-page-recovery-plan
```

MCP tool:

```text
notion_nested_tree_plan
```

## What It Checks

The fixture must use safe refs and explicit review signals:

```text
generation_roots  -> known DB1/DB2/DB3 or equivalent generation roots
nodes             -> node_ref, parent_ref, node_kind, optional content_class
minted_refs       -> refs already covered by current archive zets
```

For each leaf node, WOM-kit walks the parent chain until it reaches a known
generation root. If the chain reaches a missing parent, WOM-kit reports the leaf
as `untraceable` instead of guessing a generation from a partial local mirror.

The command separates:

- `recovery_queue`: live content leaves that are missing and have a trusted
  generation assignment,
- `hold_queue`: leaves with missing ancestors, ambiguous generation, or unknown
  content classification,
- `structure_skip_queue`: structure, template, or view-container leaves that
  should not become canonical zets by default.

## v0.3.125 Safety Updates

`content_class` is now optional. When it is omitted, WOM-kit derives a
conservative class from `node_kind` without reading titles or bodies:

```text
page / child_page              -> content
database / child_database      -> structure
data_source                    -> structure
collection_view / view         -> view_container
```

An explicit `content_class` can still override the derived class. Dangerous
conflicts such as `child_database + content` are routed to human review instead
of recovery. `source_status=trashed` is normalized to `trash`.

Multiple generation roots may now share the same `generation_id` when their
`root_ref` values are unique. This supports one logical generation with many
physical database roots.

If the fixture has more nodes than `--max-items`, the command blocks instead of
returning a partial success. The result includes a truncation receipt with the
declared count, remaining count, and first unprocessed safe ref.

For missing ancestors, prefix-like `root_ref` / `parent_ref` mismatches are
reported as warnings. The planner still uses exact matching and does not
silently expand short refs.

## Fixture Boundary

The fixture path must be archive-relative. Absolute paths, parent-directory
segments, local paths, provider URLs, token-like values, and secret-like values
are rejected.

The fake archive includes:

```text
workbench/notion-nested-tree.sample.json
```

That fixture uses only safe refs such as `database:fake:*`, `page:fake:*`, and
`block:fake:*`. It includes no page titles, page bodies, raw URLs, local paths,
account ids, emails, comment bodies, tokens, or secret values.

## Closed Actions

This command does not:

- call Notion,
- start OAuth,
- open a Notion connection,
- read real source export files,
- read page titles,
- read page bodies,
- read comments,
- download media,
- write zets,
- mint pages,
- write edges,
- write receipts,
- update object manifests,
- echo provider URLs, local absolute paths, raw export paths, page titles,
  page bodies, comment bodies, account ids, emails, tokens, or secret values.

It only returns a read-only recovery plan so a later reviewed parser or import
workflow can avoid both missed content leaves and structure/template pollution.

For a read-only request queue that packages missing ancestor refs for a future
credential-bounded adapter, use:

```powershell
archive notion-ancestor-crawl-plan <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --source notion `
  --dry-run `
  --format json
```
