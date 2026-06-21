# Notion Block Mirror Tree Fixture Plan

Status: v0.3.126 read-only reviewed block-mirror fixture checkpoint

`archive notion-block-mirror-tree-fixture-plan` builds a sanitized nested tree
fixture preview from reviewed Notion block mirror metadata.

It is for the gap where a local mirror already contains safe structural
metadata, but a human or AI agent previously had to write a custom fixture
builder by hand.

## Command

```powershell
archive notion-block-mirror-tree-fixture-plan <archive-root> `
  --mirror workbench/notion-block-mirror.sample.json `
  --source notion `
  --dry-run `
  --format json
```

Aliases:

```text
notion-nested-tree-fixture-plan
notion-mirror-tree-fixture-plan
```

MCP tool:

```text
notion_block_mirror_tree_fixture_plan
```

## Input Contract

The mirror fixture is archive-relative JSON:

```text
fixture_kind: notion_block_mirror_fixture
source: notion
generation_roots: reviewed generation root refs
minted_refs: optional refs already covered by zets
blocks: reviewed structural metadata records
```

Each block may provide direct `node_ref` / `parent_ref` values, or safe
metadata fields such as `id`, `parent_id`, `parent_type`, and `type`.

The command derives:

- `node_ref` from `id + node_kind`,
- `parent_ref` from `parent_id + parent_type`,
- `content_class` from `node_kind`,
- `source_status` from `source_status`, `in_trash`, `trashed`, or `archived`.

It does not read page titles or page bodies.

## Output

The command returns:

- `nested_tree_fixture_preview`,
- `nested_tree_plan_preview`,
- `mirror_summary`,
- privacy guards and closed-action flags.

The preview can be reviewed and then used with `notion-nested-tree-plan`,
`notion-ancestor-crawl-plan`, or `notion-ancestor-merge-plan`.

## Closed Actions

This command does not call Notion, start OAuth, open a Notion connection, read
real export directories, read page titles, read page bodies, read comments,
download media, write a fixture, write zets, mint pages, write edges, write
receipts, update object manifests, or echo provider URLs, local absolute paths,
raw export paths, page titles, page bodies, comment bodies, account ids, emails,
tokens, or secret values.
