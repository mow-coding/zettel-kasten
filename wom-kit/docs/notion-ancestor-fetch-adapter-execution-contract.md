# Notion Ancestor Fetch Adapter Execution Contract

Status: v0.3.130 read-only future fetch adapter contract checkpoint

`archive notion-ancestor-fetch-adapter-execution-contract` previews the contract
that a future credential-bounded Notion ancestor fetch adapter must satisfy.

It is the safe bridge between:

```text
notion-ancestor-crawl-plan produces a scoped crawl_request_queue
-> future credential-bounded adapter fetches ancestor metadata
-> adapter returns a sanitized notion_ancestor_result_fixture
-> notion-ancestor-merge-plan merges and replans
```

This command still does not call Notion. It does not retrieve secrets, start
OAuth, open a Notion connection, read page titles, read page bodies, read
comments, download media, write fixtures, write receipts, or mutate the archive.

## Command

```powershell
archive notion-ancestor-fetch-adapter-execution-contract <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --source notion `
  --scope-generation-id DB1 `
  --credential-ref env:wom_notion_readonly `
  --dry-run `
  --format json
```

Aliases:

```text
notion-ancestor-fetch-execution-contract
notion-ancestor-crawl-adapter-execution-contract
```

MCP tool:

```text
notion_ancestor_fetch_adapter_execution_contract
```

## What It Checks

The command reuses `notion-ancestor-crawl-plan` and reports:

```text
contract_state
credential_summary
crawl_request_summary
scope_filter
execution_contract
adapter_input_contract
adapter_output_contract
current_capability
closed_actions
privacy_guards
```

If a safe credential ref is supplied, only its store class is reported. The
exact ref string and secret value are not echoed.

## Adapter Input Contract

The future adapter must consume the scoped `crawl_request_queue` produced by:

```text
archive notion-ancestor-crawl-plan --dry-run
```

Required request fields:

```text
request_id
source
request_reason
ancestor_ref
affected_leaf_refs
known_child_refs
max_depth
stop_conditions
required_return_fields
merge_target
```

Optional safe request fields:

```text
affected_generation_ids
affected_root_refs
lineage_refs_seen
lineage_depths_seen
```

## Adapter Output Contract

The future adapter must return only a sanitized fixture:

```text
fixture_kind: notion_ancestor_result_fixture
```

Required node fields:

```text
node_ref
parent_ref
node_kind
source_status
review_status
```

Optional node fields:

```text
content_class
mint_state
containment_source_ref
declared_generation_id
```

The next local command after receiving the fixture is:

```powershell
archive notion-ancestor-merge-plan <archive-root> `
  --tree <tree.json> `
  --ancestors <ancestor-result.json> `
  --source notion `
  --dry-run `
  --format json
```

## Closed Actions

This command does not:

- call Notion,
- start OAuth,
- open a Notion connection,
- retrieve credential values,
- read page titles,
- read page bodies,
- read comments,
- download media,
- write ancestor result fixtures,
- write receipts,
- write zets,
- write edges,
- update object manifests,
- echo exact credential refs, provider URLs, workspace URLs, local absolute
  paths, raw export paths, page titles, page bodies, comment bodies, account
  ids, emails, tokens, or secret values.

It only fixes the execution contract that a later live adapter must obey.
