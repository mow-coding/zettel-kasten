# zet Abstract And Live Catalog Contract

Status: implemented CLI baseline in v0.3.204; MCP/host baseline in v0.3.205; scale/token baseline in v0.3.206; compact strict reading in v0.3.207; seeded exhaustive order in v0.3.208; separate first-read readiness in v0.3.209; routed order evidence in v0.3.210

## Purpose

WOM keeps local zet files as canonical memory. A host LLM application should be
able to enumerate that local memory without depending on a generated map or
silently stopping at an arbitrary top-k limit.

This contract adds two compatible pieces:

- optional canonical `abstract` frontmatter for a compact first read;
- read-only `archive zet-catalog` for deterministic, paged enumeration.

Goal, loop, task branching, and completion UI remain responsibilities of the
host LLM application. WOM provides local memory and coverage evidence.

## Abstract Field

New or revised zets may store:

```yaml
abstract: A compact, human-reviewable account of what this zet contributes.
```

The field is optional in v0.3.204 and is limited to 360 characters. Existing
archives require no migration.

`archive create-draft --abstract <text>` writes the field into the inbox draft.
It blocks blank, over-limit, private-locator, local-path, account-identifier, or
secret-like values before writing.

The catalog classifies first-read text honestly:

| `abstract_status` | Meaning |
| --- | --- |
| `explicit` | The zet has `frontmatter.abstract`. |
| `compatibility_field` | A prior optional `gist`, `summary`, `description`, or `overview` field supplied the compact text. |
| `missing` | No compact frontmatter text exists. The catalog does not read the body to invent one. |
| `redacted` | The zet exists but its content-bearing first-read fields are suppressed. |
| `frontmatter_unreadable` | The file exists but its frontmatter could not be parsed. |

The one-zet `read-zettel --section overview` compatibility surface may still
derive a gist from the first safe body paragraph. The archive-wide catalog does
not use that fallback because its contract is frontmatter-only enumeration.

## Live Catalog

```powershell
archive zet-catalog <archive-root> `
  --status canonical `
  --page-size 200 `
  --cursor 0 `
  --dry-run `
  --format json
```

Aliases:

```text
zettel-catalog
abstract-catalog
```

The default scope is every file under `zettels/`, sorted by archive-relative
path. `--status draft` selects `inbox/`; `--status all` selects both.

Every response includes:

- total, returned, remaining, and next-cursor counts;
- explicit `complete` and `truncated` booleans;
- a local snapshot id;
- abstract-state counts across the declared scope;
- each returned zet's safe title, abstract, facets, complete frontmatter edge
  projection, and tie counts;
- privacy and closed-action fields.

Continue a multi-page read with both values from the prior page:

```powershell
archive zet-catalog <archive-root> `
  --cursor <next-cursor> `
  --expected-snapshot-id <snapshot-id> `
  --dry-run `
  --format json
```

If local catalog evidence changes between pages, the command returns the
`catalog_snapshot_changed` blocker and no page items. Restart from cursor 0.

## Snapshot Honesty

The v0.3.204 snapshot hashes:

- archive-relative path;
- file size and mtime;
- safe frontmatter projection evidence, including abstract identity and edge
  count.

It does not hash zet body content. The output therefore reports:

```text
basis: path_size_mtime_frontmatter_projection
frontmatter_projection_hashed: true
body_content_hashed: false
```

This is change detection for a multi-page abstract pass, not proof that every
body byte remained unchanged.

## Local-First Boundary

The catalog:

- reads local frontmatter directly;
- requires no generated SQLite index;
- reads and echoes no zet body text;
- reads no objet bytes;
- calls no provider;
- reads no secrets;
- writes no files;
- creates no WOM-owned goal or loop state.

The generated index may become an optional accelerator later, but a missing or
stale index must never make local zet nodes disappear from discovery.

## MCP And Host Runtime

v0.3.205 exposes the same read-only catalog through MCP:

```json
{
  "name": "zet_catalog",
  "arguments": {
    "archive_root": "<archive-root>",
    "status": "canonical",
    "cursor": 0,
    "page_size": 200
  }
}
```

The MCP page-size ceiling is 1,000. A host must follow `next_cursor` with the
returned `snapshot.id` as `expected_snapshot_id` until `complete` is true. A
changed snapshot blocks continuation rather than combining two local states.

MCP `read_zettel` accepts `section: overview`, `document`, `body`, `details`, or
`all`. The compatibility default remains `body`; host reading instructions use
`overview` first. MCP `create_draft_zettel` accepts the same optional bounded
`abstract` as the CLI.

Runtime context, AI start-here, archive `AGENTS.md` templates, and the shipped
runtime skill all state the same order:

1. enumerate every canonical abstract and complete every page;
2. use abstracts, ties, and edges to choose body-reading order;
3. read a zet overview before its document or body;
4. never call a search result or truncated page exhaustive coverage.

Goal and loop remain host-application UI/UX. WOM supplies local memory,
passages between zet nodes, and explicit completion evidence.

## Workload And Token Budget

v0.3.206 adds `workload_estimate` for the declared scope and returned page:

- abstract character count and estimated abstract tokens;
- items-only JSON character count and UTF-8 byte count;
- estimated items-only JSON tokens.

The method is `unicode_character_count_divided_by_4_heuristic`. It is not a
provider-reported token count, excludes the response envelope, and excludes zet
bodies. Hosts should treat it as a transparent planning estimate.

CLI `--max-estimated-tokens <n>` and MCP `max_estimated_tokens` stop a page
before its estimated items-only JSON exceeds the requested budget. One item is
still returned when that item exceeds the budget by itself, so a host loop
cannot get stuck without advancing its cursor.

## MCP Session Snapshot

For large MCP passes, the first page materializes safe catalog items in process
memory. Intermediate pages read that same snapshot without rescanning every
file. Before the page that would make `complete: true`, MCP re-enumerates local
paths and file metadata. If the resulting snapshot differs, it returns
`catalog_snapshot_changed` and no completing items; the host restarts at cursor
0. The cache is process-local, bounded by archive/status scopes, not persisted,
not authoritative, and not a generated map.

CLI calls remain independent processes and live-verify each invocation.

See [zet Catalog Scale And Token Budget](zet-catalog-scale-and-token-budget.md)
for reproducible synthetic benchmark commands and interpretation boundaries.

## Compact Reading Projection

v0.3.207 adds `projection=reading` for the host's archive-wide first pass. Each
item keeps id, status, title, kind, updated time, abstract state, facets, tie
summary, and every safe frontmatter edge. It omits full-only path, created time,
abstract-source/truncation bookkeeping, per-item body-read flags, and repeated
warnings. `projection=full` remains the compatibility default.

## Strict Contiguous Coverage

Use `coverage_mode=strict` from cursor 0. Every later call must pass the prior
page's `coverage.continuation_token`. The checksum-validated token binds the
snapshot, status filter, projection, deterministic order, expected next cursor,
covered prefix count, and chain hash.

`coverage.complete` still means that the current page reached the scope end.
Only `coverage.archive_wide_coverage_claim_ready: true` means a strict
cursor-zero chain reached the end without a skipped cursor and passed snapshot
validation.

That field proves node visitation, not abstract completeness. v0.3.209 adds
`archive_wide_abstract_reading_claim_ready` for complete non-redacted
first-read availability and `archive_wide_followup_resolution_ready` for safe
unique id-based follow-up. See
[zet Catalog Readiness Signals](zet-catalog-readiness-signals.md).

The token is stateless, contains no body text or local path, and is never
persisted. It prevents accidental continuation drift; because it uses an
unkeyed checksum, it is not a signature, attestation, security credential, or
receipt. See [Contiguous Node Reading](zet-catalog-contiguous-reading.md).

## Seeded Connection Reading Order

When the host goal or human already provides verified zet ids, v0.3.208 can
start with `order=seeded_connection_walk` and repeated start ids. Safe incoming
and outgoing zet edges become undirected reading passages for breadth-first
ordering only. Stored edge direction and meaning remain unchanged.

The seed-connected prefix comes first. Then every unvisited component and
isolated node follows in archive-relative path order. Missing seeds block rather
than falling back silently. No relevance model, body search, generated map, or
provider call participates. See
[Seeded Connection Reading Order](seeded-connection-reading-order.md).

When that seeded order needs an item-by-item explanation, use the opt-in
`routed_reading` projection. Normal `reading` stays smaller. See
[Seeded Reading Route Evidence](seeded-reading-route-evidence.md).
