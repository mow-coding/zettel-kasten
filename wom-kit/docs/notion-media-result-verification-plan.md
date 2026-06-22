# Notion Media Result Verification Plan

Status: v0.3.132 read-only media result fixture verification checkpoint

`archive notion-media-result-verification-plan` verifies a sanitized
`notion_media_result_fixture` against `objects/manifests/files.jsonl`.

It is the local verification step after a future credential-bounded media fetch
adapter emits byte-hash evidence.

## Command

```powershell
archive notion-media-result-verification-plan <archive-root> `
  --media-result workbench/notion-media-result.sample.json `
  --source notion `
  --dry-run `
  --format json
```

Aliases:

```text
notion-media-result-verify-plan
notion-media-preservation-verification-plan
```

MCP tool:

```text
notion_media_result_verification_plan
```

## What It Verifies

The verifier reads only:

```text
workbench/notion-media-result.sample.json
objects/manifests/files.jsonl
```

It checks:

- `fixture_kind: notion_media_result_fixture`,
- source consistency,
- media row required fields,
- `object_id` / `sha256` format and agreement,
- preservation statuses: `already_preserved`, `newly_preserved`, `fetch_failed`,
- whether non-failed media object ids are present in
  `objects/manifests/files.jsonl`.

It reports:

```text
verification_summary
item_results
current_capability
closed_actions
privacy_guards
```

## Boundary

The verifier does not prove bytes by downloading them. It does not hash media bytes.
It trusts that a future credential-bounded adapter already fetched and hashed
bytes before producing the fixture. This command only checks the sanitized
fixture and local manifest consistency.

It does not call providers, refresh signed URLs, download media bytes, hash
media bytes, read object bytes, update object manifests, write receipts, write
zets, write edges, or echo provider URLs, local absolute paths, page titles,
page bodies, comments, account ids, emails, tokens, secret values, or media
bytes.
