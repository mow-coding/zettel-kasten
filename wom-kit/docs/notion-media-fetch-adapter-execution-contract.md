# Notion Media Fetch Adapter Execution Contract

Status: v0.3.132 read-only future media byte fetch adapter contract checkpoint

`archive notion-media-fetch-adapter-execution-contract` previews the contract
that a future credential-bounded Notion media byte fetch adapter must satisfy.

It is the safe bridge between:

```text
notion-nested-tree-plan identifies nested live content leaf pages
-> future credential-bounded adapter discovers media blocks from live page data
-> adapter refreshes expiring provider file refs and fetches bytes
-> adapter hashes bytes and preserves media as sha256 objets
-> adapter returns a sanitized notion_media_result_fixture
-> notion-media-result-verification-plan verifies manifest consistency
```

This command still does not call Notion. It does not retrieve secrets, refresh
signed file URLs, download media bytes, hash bytes, read page titles, read page
bodies, read comments, write fixtures, update object manifests, write receipts,
or mutate the archive.

## Command

```powershell
archive notion-media-fetch-adapter-execution-contract <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --source notion `
  --scope-leaf-ref page:fake:db2-nested-live-log `
  --credential-ref env:wom_notion_readonly `
  --dry-run `
  --format json
```

Aliases:

```text
notion-media-fetch-execution-contract
notion-nested-leaf-media-fetch-contract
```

MCP tool:

```text
notion_media_fetch_adapter_execution_contract
```

## What It Checks

The command reuses `notion-nested-tree-plan` and reports:

```text
contract_state
credential_summary
media_request_summary
scope_filter
execution_contract
execution_actor_contract
adapter_input_contract
adapter_output_contract
media_fetch_request_queue
current_capability
closed_actions
privacy_guards
```

The current fixture can identify candidate nested content leaf pages, but it
cannot know how many media blocks exist or whether those bytes are already
preserved. That requires future live page or block fetch plus byte hashing.

## Output Fixture Contract

The future adapter must return only a sanitized fixture:

```text
fixture_kind: notion_media_result_fixture
```

Required media fields:

```text
page_ref
block_ref
media_kind
object_id
sha256
size_bytes
ext
mime
source_status
preservation_status
review_status
```

Allowed preservation statuses:

```text
already_preserved
newly_preserved
fetch_failed
```

The output must not include provider URLs, signed URLs, media bytes, raw
provider responses, credential refs, page titles, page bodies, comments, local
absolute paths, account ids, emails, tokens, or secret values.

## Actor Boundary

The intended future live fetch subject is a WOM local credential-bounded adapter
process after human scope review and credential approval. The AI chat runtime
may plan, review, and verify only. Client-supplied fixtures are sanitized
safe-origin fallback input; the contract does not require client-side
hand-rolled provider crawling.

## Closed Actions

This command does not:

- call Notion,
- start OAuth,
- open a Notion connection,
- retrieve credential values,
- refresh signed provider file URLs,
- download media bytes,
- hash media bytes,
- read page titles,
- read page bodies,
- read comments,
- write media result fixtures,
- update object manifests,
- write receipts,
- write zets,
- write edges,
- echo exact credential refs, provider URLs, workspace URLs, local absolute
  paths, raw export paths, page titles, page bodies, comment bodies, account
  ids, emails, tokens, secret values, or media bytes.
