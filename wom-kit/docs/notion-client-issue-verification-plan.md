# Notion Client Issue Verification Plan

Status: v0.3.127 read-only client issue verification checkpoint

`archive notion-client-issue-verification-plan` verifies a client Notion
nested-tree issue from sanitized local fixtures.

It does not connect to Notion. It answers a narrower question:

```text
Does the sanitized bundle reproduce the missing-ancestor issue?
If sanitized ancestors are supplied, does the merge close that issue?
```

## Command

```powershell
archive notion-client-issue-verification-plan <archive-root> `
  --tree workbench/notion-nested-tree.sample.json `
  --ancestors workbench/notion-ancestor-result.sample.json `
  --source notion `
  --dry-run `
  --format json
```

The command can also inspect a reviewed block mirror fixture:

```powershell
archive notion-client-issue-verification-plan <archive-root> `
  --mirror workbench/notion-block-mirror.sample.json `
  --source notion `
  --dry-run `
  --format json
```

Aliases:

```text
notion-tree-verification-plan
notion-nested-tree-verification-plan
```

MCP tool:

```text
notion_client_issue_verification_plan
```

## Input Contract

At least one of these must be supplied:

```text
--tree     sanitized notion_nested_tree_fixture
--mirror   reviewed notion_block_mirror_fixture
```

`--ancestors` is optional and currently requires `--tree`:

```text
--ancestors sanitized notion_ancestor_result_fixture
```

All paths must be archive-relative fixture paths. Absolute paths, provider URLs,
tokens, secret-like values, page titles, page bodies, comments, and media are
not accepted as fixture content.

## Output

The command returns:

- `verification_summary`,
- `base_tree_plan`,
- optional `mirror_tree_fixture_plan`,
- `ancestor_crawl_plan`,
- optional `ancestor_merge_plan`.

The top-level `plan_state` is one of:

```text
client_issue_reproduced_missing_ancestor_evidence_needed
client_issue_verified_closed_by_sanitized_ancestor_merge
client_issue_still_needs_more_sanitized_ancestor_evidence
no_missing_ancestor_issue_detected_in_sanitized_input
blocked
```

This lets a human or AI runtime tell whether the client issue is reproduced,
closed by sanitized ancestor evidence, still waiting for more ancestor evidence,
or absent from the sanitized input.

## Closed Actions

This command does not call Notion, start OAuth, open a Notion connection, read
real export directories, read page titles, read page bodies, read comments,
download media, write verification files, write or merge fixture files, write
zets, mint pages, write edges, write receipts, update object manifests, or echo
provider URLs, local absolute paths, raw export paths, page titles, page bodies,
comment bodies, account ids, emails, tokens, or secret values.
