# Notion Ancestor Fetch Adapter Execution Contract

Status: v0.3.131 read-only future fetch adapter actor-contract checkpoint

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
v0.3.131 clarifies the execution subject: the live fetch subject is a future
WOM local credential-bounded adapter process, not the AI chat runtime and not a
requirement that a client hand-roll provider crawling.

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
execution_actor_contract
adapter_input_contract
adapter_output_contract
current_capability
closed_actions
privacy_guards
```

If a safe credential ref is supplied, only its store class is reported. The
exact ref string and secret value are not echoed.

## Execution Subject Boundary

The intended live path is:

```text
human operator reviews scope and approves credential ref
-> credential broker resolves the approved ref outside AI context
-> future WOM local credential-bounded adapter process calls the provider
-> adapter writes only a sanitized notion_ancestor_result_fixture
-> notion-ancestor-merge-plan consumes the fixture
```

The current release does not execute that path yet. Its current live fetch
execution subject is:

```text
none_contract_preview_only
```

The future live fetch execution subject is:

```text
future_wom_local_credential_bounded_adapter_process
```

The AI chat runtime may plan, review, and verify. It must not become the live
provider fetch subject, must not receive credential values, and must not
hand-roll provider crawling. Client-supplied `notion_ancestor_result_fixture`
files are accepted only as sanitized safe-origin input or fallback evidence;
they are not a requirement that the client or client-side AI directly crawl a
provider with private session tokens.

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
