# Notion Ancestor Crawl Plan

Status: v0.3.125 read-only missing ancestor crawl request checkpoint

`archive notion-ancestor-crawl-plan` packages the missing ancestor refs reported
by `archive notion-nested-tree-plan` into a reviewed crawl request queue.

It is the safe bridge between:

```text
nested tree plan reports untraceable leaves
-> ancestor crawl request queue
-> future provider adapter fetches ancestors
-> sanitized tree merge
-> nested tree plan runs again
```

This command does not call Notion. It does not read page titles, page bodies,
comments, media, or real source exports. It only reads the same sanitized
archive-internal tree fixture used by `notion-nested-tree-plan`.

## Command

```powershell
archive notion-ancestor-crawl-plan <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --source notion `
  --dry-run `
  --format json
```

Aliases:

```text
notion-nested-ancestor-crawl-plan
notion-parent-chain-crawl-plan
```

MCP tool:

```text
notion_ancestor_crawl_plan
```

## What It Returns

The command first runs the nested tree planner. Then it groups hold-queue leaves
with:

- `reason=missing_parent_record` and a `missing_ancestor_ref`,
- `reason=no_known_generation_root`, where the rootless leaf itself becomes the
  crawl seed.

Each `crawl_request_queue` item includes:

```text
request_id
ancestor_ref
affected_leaf_refs
known_child_refs
suggested_direction
max_depth
stop_conditions
required_return_fields
merge_target
write_status
```

The required return fields for a future adapter are sanitized metadata only:

```text
node_ref
parent_ref
node_kind
source_status
review_status
```

`content_class` is optional because v0.3.125 can derive a conservative
classification from `node_kind` when the fixture omits it.

## Fixture And Truncation Safety

The source fixture remains archive-relative. Absolute paths, parent-directory
segments, local paths, provider URLs, token-like values, and secret-like values
are rejected.

If the nested tree fixture is larger than `--max-items`, the command blocks.
It does not return a partial crawl queue, because a partial tree could hide
missing ancestors and make an incomplete migration look successful.

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
- write or merge a fixture,
- write zets,
- mint pages,
- write edges,
- write receipts,
- update object manifests,
- echo provider URLs, local absolute paths, raw export paths, page titles,
  page bodies, comment bodies, account ids, emails, tokens, or secret values.

It only returns the request contract that a later credential-bounded provider
adapter can consume.
