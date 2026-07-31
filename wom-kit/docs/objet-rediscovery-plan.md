# Checked-Layer Objet Rediscovery Plan

Status: read-only CLI and MCP contract implemented in v0.3.294

## Why This Exists

`archive search` searches the current generated SQLite index. Its
`complete: true` value means only that the result set inside that index was not
truncated by the requested limit. It does not prove that:

- every live source was indexed with current searchable content;
- every private original-name record was checked;
- every zettel-to-objet edge was traversed;
- every approved external local store was searched;
- remote object availability was checked; or
- every unrecovered source reference was accounted for.

Therefore, an index result with zero rows is not enough to say that a file,
preserved original, or objet does not exist.

## CLI

```powershell
archive objet-rediscovery-plan <archive-root> <query> `
  --dry-run `
  --limit 20 `
  --count-total `
  --format json
```

Canonical machine form:
`archive objet-rediscovery-plan <archive-root> <query> --dry-run --count-total --format json`.

The structured result schema is:
`wom-kit/objet-rediscovery-plan/v0.1`.

`--dry-run` is required. A successful inspection returns process exit 0 even
though the evidence is intentionally incomplete:

```json
{
  "ok": true,
  "status": "search_incomplete",
  "rediscovery_complete": false,
  "negative_claim_supported": false
}
```

An invalid archive, missing or malformed index, read failure, pending SQLite
WAL or rollback-journal content, unsafe local directory boundary, or index
snapshot change returns a fixed `blocked` result and exit 1 without exposing
the underlying exception.

## MCP

The matching MCP tool is:

```text
objet_rediscovery_plan
```

It requires `archive_root`, `query`, and boolean `dry_run: true`. CLI and MCP
call the same service and preserve the same structured result. MCP transport
success does not change `status`, `rediscovery_complete`, or
`negative_claim_supported`.

## Fixed Layer Order

Every result, including `blocked`, lists these ten layer IDs in this exact
order:

| Layer ID | v0.3.294 evidence |
| --- | --- |
| `indexed_zettels` | Generated-index snapshot only. Current index-health does not prove searchable title/body freshness. |
| `indexed_object_manifests` | Generated-index snapshot only; manifest freshness is not proven. |
| `indexed_derived_text` | Generated-index snapshot only; derived-text manifest freshness is not proven. |
| `indexed_views` | Generated-index snapshot only; view freshness is not proven. |
| `indexed_source_records` | Generated-index snapshot only; source-map freshness is not proven. |
| `zettel_objet_edges` | `unchecked` until a reviewed zettel is selected for exact traversal. |
| `private_original_name_metadata` | `not_implemented`; reserved for the reviewed v0.3.295+ contract. |
| `approved_external_local_store` | `not_implemented`; no registration or scan lifecycle exists here. |
| `external_store_evidence` | `unchecked`; the existing local `backup-evidence` status is not run because it does not consume the submitted private query. |
| `unrecovered_source_references` | `not_implemented`; reserved for the v0.3.299 coverage contract. |

Each index channel receives its own bounded `limit + 1` probe even when an
earlier channel already fills the global result limit. An untruncated channel
is `checked_snapshot_only`; a truncated channel is `checked_truncated`.
`checked_match_count` is the exact index total when available and otherwise a
bounded lower bound summed across those channel probes; its companion
`checked_match_count_exact` keeps that distinction explicit.
`--count-total` can make the index-internal total exact, but it does not change
`truncated`, does not prove source freshness, and does not complete the other
layers.

## Privacy Boundary

The result is an evidence summary, not a private finder. JSON, text, and MCP
summaries do not return:

- the raw query or a query hash;
- result rows, snippets, titles, filenames, or body text;
- zettel, object, source, page, attachment, or block identifiers;
- local absolute paths;
- provider URLs, bucket/account/key locators;
- secrets, tokens, or credential values; or
- SQLite, YAML, decoder, permission, or path exception text.

Only safe fixed layer IDs, state labels, counts, reason codes, and static next
commands cross the output boundary.

## No-Write And No-External-Call Boundary

The plan does not rebuild the index; write a manifest, receipt, or metadata;
open objet bytes; scan an external directory; call a provider or network;
access a credential store; install a Runtime Skill; or modify `AGENTS.md`.
The static next-command list routes external evidence review to
`archive backup-evidence <archive-root> --dry-run`; naming that existing
read-only command does not mean this plan executed it.

The plan pins one dedicated immutable read transaction for the last complete
SQLite main-file snapshot and shares that connection across health, global
search, and all five channel probes, so it cannot mix multiple database
snapshots or create `-wal` or `-shm` sidecars. Because immutable reads would
ignore pending WAL contents and hot rollback recovery, a non-empty WAL or
rollback journal fails closed. The local zettel scan rejects changed or
reparse directory identities and missing, zero, or changed regular-file
identities on Windows, and blocks symlink, junction, or reparse directories
before descent; it does not reopen a checked path or turn a linked external
directory into an archive source. A main index that changes across the
complete inspection also fails closed.

Ordinary `archive search` is unchanged and keeps its existing transaction and
`complete == not truncated` contract.

## Follow-Up Release Boundary

v0.3.294 does not implement private original-name normalization, approval-
gated private metadata registration, approved external local-store lifecycle,
exact external object resolution, provider retrieval, or source-reference
coverage. Those remain separate v0.3.295-v0.3.299 review batches.

Decision:
[v0.3.294 checked-layer rediscovery decision](archive-infra-decision-log-2026-07-31-v03294-checked-layer-objet-rediscovery.md).
