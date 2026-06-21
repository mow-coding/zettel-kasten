# Notion Client Fixture Request Plan

Status: v0.3.128 read-only client fixture request checkpoint

`archive notion-client-fixture-request-plan` packages the minimal sanitized
fixture request contract needed for client Notion nested-tree verification.

It does not message the client and does not connect to Notion. It only answers:

```text
What safe, sanitized fixture should we ask for next?
Which fields are allowed?
Which fields must not be sent?
Which verification command should run after the fixture arrives?
```

## Command

```powershell
archive notion-client-fixture-request-plan <archive-root> `
  --source notion `
  --dry-run `
  --format json
```

If a local sanitized fixture already exists, the command can preview the current
verification state before deciding the next requested fixture:

```powershell
archive notion-client-fixture-request-plan <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --source notion `
  --dry-run `
  --format json
```

Aliases:

```text
notion-fixture-request-plan
notion-client-verification-request-plan
```

MCP tool:

```text
notion_client_fixture_request_plan
```

## Output

The command returns `request_package` with:

- accepted fixture kinds,
- minimal `notion_nested_tree_fixture` fields,
- minimal `notion_block_mirror_fixture` fields,
- minimal `notion_ancestor_result_fixture` fields,
- a redaction checklist,
- next verification commands.

When preview inputs are supplied, it also returns `verification_preview` from
`notion-client-issue-verification-plan`.

The `requested_next_fixture` field can be:

```text
notion_nested_tree_fixture
notion_block_mirror_fixture
notion_ancestor_result_fixture
none
```

## Redaction Boundary

The request package explicitly says not to include:

- page titles,
- page bodies,
- comments,
- media, attachment bytes, thumbnails, or OCR text,
- provider URLs,
- workspace URLs,
- local absolute paths,
- raw export paths,
- account ids,
- emails,
- tokens,
- secret values.

## Closed Actions

This command does not send client messages, call Notion, start OAuth, open a
Notion connection, read real export directories, read page titles, read page
bodies, read comments, download media, write request files, write or merge
fixture files, write zets, mint pages, write edges, write receipts, update
object manifests, or echo provider URLs, local absolute paths, raw export paths,
page titles, page bodies, comment bodies, account ids, emails, tokens, or secret
values.
