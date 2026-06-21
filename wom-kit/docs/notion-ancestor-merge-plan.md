# Notion Ancestor Merge Plan

Status: v0.3.126 read-only sanitized ancestor merge and replan checkpoint

`archive notion-ancestor-merge-plan` merges sanitized ancestor result nodes into
a nested tree fixture preview and immediately replans the nested tree in memory.

It is the local half of the loop:

```text
notion-nested-tree-plan reports untraceable leaves
-> notion-ancestor-crawl-plan packages missing ancestors
-> a future credential-bounded adapter returns sanitized ancestor nodes
-> notion-ancestor-merge-plan merges and replans
-> recovery_queue / hold_queue / structure_skip_queue are recomputed
```

## Command

```powershell
archive notion-ancestor-merge-plan <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --ancestors workbench/notion-ancestor-result.sample.json `
  --source notion `
  --dry-run `
  --format json
```

Aliases:

```text
notion-nested-tree-merge-plan
notion-ancestor-result-merge-plan
```

MCP tool:

```text
notion_ancestor_merge_plan
```

## Input Contract

The base tree fixture must be a `notion_nested_tree_fixture`.

The ancestor result fixture must be:

```text
fixture_kind: notion_ancestor_result_fixture
source: notion
nodes: sanitized ancestor nodes
```

Ancestor nodes use the same safe fields as nested tree nodes:

```text
node_ref
parent_ref
node_kind
source_status
review_status
content_class        optional
mint_state           optional
containment_source_ref optional
declared_generation_id optional
```

Conflicting duplicate `node_ref` metadata blocks the merge preview. Unchanged
duplicate ancestors are counted and skipped.

## Output

The command returns:

- `merge_summary`,
- `merged_tree_fixture_preview`,
- `nested_tree_plan_after_merge`.

If the ancestor nodes close a missing parent chain, the previously untraceable
leaf can move out of `hold_queue` and into `recovery_queue` or
`structure_skip_queue` according to the same nested tree planner rules.

## Closed Actions

This command does not call Notion, start OAuth, open a Notion connection, read
real export directories, read page titles, read page bodies, read comments,
download media, write or merge fixture files, write zets, mint pages, write
edges, write receipts, update object manifests, or echo provider URLs, local
absolute paths, raw export paths, page titles, page bodies, comment bodies,
account ids, emails, tokens, or secret values.
