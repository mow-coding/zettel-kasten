# Notion Ancestor Fetch Adapter Run

Status: v0.3.134 approval-gated local Notion ancestor structure fetch checkpoint

`archive notion-ancestor-fetch-adapter-run` is the first local live Notion
ancestor fetch adapter.

It consumes the scoped `crawl_request_queue` from
`notion-ancestor-crawl-plan`, verifies a credential access approval receipt,
reads a Notion token from an approved `env:` reference inside the local CLI
process, calls the Notion API for parent-chain structure metadata, and writes a
sanitized `notion_ancestor_result_fixture`.

It is intentionally narrow. It does not read page titles, page bodies,
comments, media bytes, file URLs, workspace URLs, or raw provider responses,
and it does not mint zets or write edges.
More explicitly: it does not read page titles, does not read page bodies, and
does not download media bytes.

## Command

First write a local non-secret approval receipt:

```powershell
archive credential-access-approval <archive-root> `
  --credential-id cred:notion-readonly `
  --credential-ref env:WOM_NOTION_READONLY_TOKEN `
  --credential-kind provider_api_key `
  --provider notion `
  --action-kind cli_token_auth `
  --decision approve_once `
  --store-kind environment `
  --consumer wom:adapter:notion-ancestor-fetch `
  --reviewed-by human:me `
  --approve `
  --format json
```

Then preview the adapter run:

```powershell
archive notion-ancestor-fetch-adapter-run <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --output workbench/notion-ancestor-result.live.json `
  --source notion `
  --scope-ancestor-ref page:<32hex-notion-page-id> `
  --credential-id cred:notion-readonly `
  --credential-ref env:WOM_NOTION_READONLY_TOKEN `
  --credential-kind provider_api_key `
  --credential-provider notion `
  --approval-decision approve_once `
  --approval-receipt receipts/credentials/access-approvals/<receipt>.credential-access-approval.json `
  --dry-run `
  --format json
```

Run it only after reviewing the dry-run output:

```powershell
archive notion-ancestor-fetch-adapter-run <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --output workbench/notion-ancestor-result.live.json `
  --source notion `
  --scope-ancestor-ref page:<32hex-notion-page-id> `
  --credential-id cred:notion-readonly `
  --credential-ref env:WOM_NOTION_READONLY_TOKEN `
  --credential-kind provider_api_key `
  --credential-provider notion `
  --approval-decision approve_once `
  --approval-receipt receipts/credentials/access-approvals/<receipt>.credential-access-approval.json `
  --approve `
  --format json
```

Aliases:

```text
notion-ancestor-fetch-run
notion-ancestor-live-fetch
```

There is no MCP live execution tool for this command. MCP remains dry-run for
the Notion ancestor contract boundary.

## What It Writes

Approved execution writes:

```text
workbench/<chosen-output>.json
receipts/notion/ancestor-fetches/<receipt>.json
```

The fixture is merge-compatible and intentionally has only these top-level
fields:

```text
fixture_kind
source
nodes
```

Each fetched node contains only sanitized structure metadata:

```text
node_ref
parent_ref
node_kind
source_status
mint_state
review_status
```

The execution receipt records counts, stop conditions, policy state, and
redaction guarantees. It does not record the approval receipt path, exact
credential ref, environment variable name, token value, provider URLs, raw
provider responses, page titles, page bodies, comments, account ids, emails, or
media bytes.

## Recursive Stop Conditions

The adapter starts from each scoped `ancestor_ref` and follows parent refs
upward until one of these stop conditions applies:

```text
known_generation_root_ref_reached
space_or_workspace_root_reached
max_depth_reached
parent_ref_missing_or_ambiguous
unsafe_ref_or_provider_secret_detected
provider_fetch_failed_raw_error_redacted
```

When the fetched node's parent is already a known generation root in the local
tree fixture, the adapter stops without refetching that known root. This keeps
the output focused on missing ancestors and reduces merge conflicts.

## Next Step

After a successful run, merge the sanitized fixture in memory:

```powershell
archive notion-ancestor-merge-plan <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --ancestors workbench/notion-ancestor-result.live.json `
  --source notion `
  --dry-run `
  --format json
```

Then rerun `notion-ancestor-crawl-plan` on the reviewed merged fixture state if
remaining missing ancestors still exist.

## Closed Actions

This command still does not:

- start OAuth,
- open a browser session,
- read OS keyrings or password managers,
- read page titles,
- read page bodies,
- read comments,
- download media bytes,
- refresh file URLs,
- write zets,
- mint pages,
- write edges,
- update object manifests,
- expose a live MCP provider-call tool.

## Notion API Surface

The live structure fetch uses the same public API surfaces described by the
official Notion API docs:

- Retrieve a page: <https://developers.notion.com/reference/retrieve-a-page>
- Retrieve a block: <https://developers.notion.com/reference/retrieve-a-block>
- Parent object: <https://developers.notion.com/reference/parent-object>

The current adapter stores only sanitized parent-chain structure derived from
those responses. Page content and child block traversal remain outside this
command.
