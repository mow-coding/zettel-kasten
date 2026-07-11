# Upgrade Guide

[한국어 업그레이드 가이드](UPGRADE.ko.md)

This guide explains how to move between public `zettel-kasten` / `zet` versions.

The project is versioned because archive rules, zettel metadata, object manifests, provenance records, and future `ZET` sharing envelopes must be understandable across users and tools.

## Quick Rule

```text
PATCH upgrade -> documentation, validation, or compatible fixes
MINOR upgrade -> compatible new features or optional fields
MAJOR upgrade -> breaking protocol/schema changes
```

Before upgrading a real archive:

1. Read the target version note in `wom-kit/docs/releases/`.
2. Back up the private archive repository and object manifests.
3. Run `archive doctor --strict`.
4. Run migration commands in dry-run mode first when available.
5. Commit private archive changes only after reviewing generated receipts.

The archive should never silently rewrite memory.

## Current Safe Process And Upgrade Check

Today, WOM-kit relies on release notes, backups, `archive doctor --strict`, and
human review for real archive upgrades.

The following read-only check is available:

```text
archive upgrade-check <archive-root> --dry-run --format json
```

It reports doctor, recovery-plan, restore-drill, and upgrade-readiness signals.
It writes nothing, returns `would_change: []`, does not run migration commands,
does not call providers, and is not a migration engine.
The top-level `ok` means the check ran; use `upgrade_readiness.status`
(`ready`, `warnings`, or `blocked`) to decide whether a real upgrade is blocked,
needs more review, or is ready for manual review.

## Frontmatter v0.3 Migration

The current v0.3 frontmatter contract requires these nested fields:

```text
provenance.created_by
provenance.created_in
provenance.source
provenance.derived_from
visibility.scope
visibility.allowed_archives
visibility.source_visibility
```

If an archive was authored from older `wom-kit/zettel-kasten-rules/v0.2-draft`
guidance, run the migration preview before strict v0.3 validation:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run --format json
```

After reviewing the planned per-field changes on a backup or sandbox copy, apply
the migration with:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --approve --format json
```

The migration is dry-run-first. It only rewrites archive-contained Markdown
zettel frontmatter under `inbox/` and `zettels/`. Clean legacy source objects
are preserved in `source_refs`; ambiguous, unsafe, secret-like, or external path
values block for manual review instead of being guessed.

Use a sandbox copy or backup before testing a real archive upgrade:

1. Copy or back up the private archive control plane.
2. Confirm the object manifests and local objet store are preserved.
3. Read the target release note.
4. Run `archive upgrade-check <archive-root> --dry-run --format json`.
5. Run `archive doctor --strict`.
6. Rebuild generated search with `archive index`.
7. Run a small `archive search` smoke test.
8. Apply any available migration dry-run before a real migration.
9. Commit private archive changes only after reviewing outputs and receipts.

For project-folder work, remember that temporary intake staging is not the
archive of record. Preserve originals as objets, source maps, manifests, zets,
and receipts before any cleanup.

## v0.3.215 Project Version Update

v0.3.215 adds the first approval-gated source-mirror and version-pin updater.
It does not migrate or rewrite archive zets.

Preview without network or writes:

```text
archive project-version-update <project-or-archive-root> --target vX.Y.Z --dry-run --progress --format json
```

After reviewing a clean preview, approve one transaction:

```text
archive project-version-update <project-or-archive-root> --target vX.Y.Z --approve --reviewed-by <actor> --progress --format json
```

Approval atomically fetches only configured `origin/main` and the exact target
tag, requires an annotated tag on that main history, verifies all three package
version files, checks out the tag detached, aligns recognized pins, and writes a
project metadata receipt. Dirty or ambiguous state blocks. A failure after
checkout restores the original checkout and exact prior pin bytes; fetched refs
may remain as non-canonical discovery state.

The current Python process is never reloaded. After success, start a new process
from the project mirror and run `archive version <root> --format json` before
claiming the target runtime is active. The check verifies configured-origin
provenance but not a cryptographic tag signature.

Bootstrap limit: installations older than v0.3.215 do not contain this command.
They need one final existing/manual verified update to v0.3.215; use the command
for later releases.

## v0.3.214 Large-Command Progress And Bounded Output

v0.3.214 adds no migration and rewrites no zet. Long `ai-start-here`,
`upgrade-check`, and CLI `zet-catalog` runs can opt into content-free liveness:

```text
archive ai-start-here <archive-root> --dry-run --progress --format json
archive upgrade-check <archive-root> --dry-run --progress --format json
archive zet-catalog <archive-root> --coverage-mode strict --cursor 0 --dry-run --progress --format json
```

Progress goes only to stderr. The final result remains on stdout. Optional
`--output .wom-scratch/diagnostics/<name>.json` stores the full JSON result and
prints only a compact stdout summary. It creates a private scratch file, not an
archive record or receipt; it refuses overwrite and should not be committed.

Catalog progress makes each live scan visible but does not persist a cache or
remove the full scan performed by a new CLI process. Existing archives and
callers that omit both options behave as before.

## v0.3.213 Local Sovereignty Authority

v0.3.213 adds no migration and rewrites no zet. It adds a read-only
`local-sovereignty` contract and exposes the same `storage_authority` model in
runtime, start-here, recovery, and upgrade-check output.

Local reviewed WOM state is canonical. GitHub, object storage, and external
databases are backup/replica layers. Existing provider bindings are not changed
and the command performs no live backup audit. `ai-start-here` schema advances
to v0.2; callers that validate that result schema should accept the new field
and version.

## v0.3.212 Compact Strict Continuations

v0.3.212 adds optional `--response-profile continuation` after the first page
of a strict catalog pass. Cursor zero must remain `full`; retain its scope-wide
abstract, identity, order, scan, and workload diagnostics. Later compact pages
keep items, readiness, snapshot, token, chain, session, warning, and privacy
fields while omitting repeated diagnostics.

Catalog schema advances to v0.8. Continuation schema remains v0.3 because the
response profile does not change item selection, order, cursor, or chain
identity. Existing callers remain full by default, and in-flight v0.3.211
strict passes may opt into compact responses on their next nonzero cursor.
Existing archives require no migration and no zet is rewritten.

## v0.3.211 Response Envelope Budget

v0.3.211 adds response-size measurement and optional
`--response-envelope-reserve-tokens`. Existing calls keep items-only
`max_estimated_tokens` semantics. When a reserve is provided, WOM subtracts it
from that value and uses the remainder as the effective items budget.

Catalog schema advances to v0.7; continuation schema remains v0.3, so an
in-flight strict pass may change its page size, item budget, or reserve without
restarting. Measurements are heuristic and exclude their own block, CLI pretty
whitespace, and MCP/JSON-RPC framing. Existing archives require no migration.

## v0.3.210 Routed Reading Evidence

v0.3.210 adds `projection=routed_reading` for seeded connection order. Normal
`projection=reading` remains the compact default. Routed reading is valid only
with `order=seeded_connection_walk` and verified start zet ids.

Catalog schema advances to v0.6. Strict continuation schema advances to v0.3
because chain hashes now distinguish snapshot file entries instead of relying
only on zet ids. Restart any v0.3.209 in-flight strict pass at cursor zero.
Tokens remain transient, checksum-based drift guards rather than signatures or
receipts. Existing archives require no migration and no zet is rewritten.

## v0.3.209 First-Read Readiness Signals

v0.3.209 adds no migration and does not rewrite existing zets. Catalog output
schema advances to v0.5 while the strict continuation-token schema remains
v0.2.

After a strict pass, interpret the three signals separately:

- `archive_wide_coverage_claim_ready`: every selected file node was visited;
- `archive_wide_abstract_reading_claim_ready`: every non-redacted node also
  supplied readable first-read text;
- `archive_wide_followup_resolution_ready`: every node has a readable, safe,
  unique frontmatter id for id-only follow-up.

A false abstract or follow-up signal is a review gap, not an automatic repair
request. Do not generate missing abstracts or rewrite ids without human review.

## v0.3.208 Seeded Exhaustive Reading Order

v0.3.208 adds optional `--order seeded_connection_walk` and repeated
`--start-zettel-id` (MCP: `order`, `start_zettel_ids`). Existing path order
remains the default and archives require no migration.

Use seeds only when the host goal or human already provides verified zet ids.
The command blocks missing seeds instead of guessing. Seed-connected nodes come
first, then every disconnected component follows, so this changes order but
never narrows coverage.

Continuation-token schema advances to v0.2 to bind the seed-list fingerprint.
Restart any v0.3.207 in-flight strict pass at cursor 0 after upgrading; tokens
are transient and are not archive records.

## v0.3.207 Compact Reading And Strict Coverage

v0.3.207 adds optional `projection=reading` and `coverage_mode=strict` to CLI
and MCP catalog calls. Existing callers keep `projection=full` and
`coverage_mode=page`; no archive migration is required.

For archive-wide AI reading, start strict mode at cursor 0. Every continuation
must pass the prior page's `coverage.continuation_token`. Only
`archive_wide_coverage_claim_ready: true` proves that this strict chain reached
the end. The older `complete` field still means the requested page reached the
scope end and must not be treated as contiguous-pass proof by itself.

The token is checksum validated and stateless. It is not a signature,
attestation, security credential, or receipt.

## v0.3.206 Catalog Scale And Token Budget

v0.3.206 adds workload estimates and optional `max_estimated_tokens` to CLI and
MCP catalog pages. Existing archives and callers require no migration; omitting
the option preserves item-count pagination.

Token estimates cover catalog item JSON only. They use a transparent
four-characters-per-token heuristic and are not provider-reported usage. MCP
keeps a process-local materialized snapshot for intermediate pages and
revalidates local file metadata before returning the completing page. Restart
at cursor 0 if that check reports `catalog_snapshot_changed`.

## v0.3.205 Host-AI Abstract Reading

v0.3.205 exposes the v0.3.204 live catalog through MCP and adds a `section`
argument to MCP `read_zettel`. Existing clients that omit `section` keep the
previous `body` default. Existing archives require no migration.

Host applications should call `zet_catalog`, follow `next_cursor` with the
same `snapshot.id` until `complete: true`, and request
`read_zettel(section: "overview")` before broader body reads. If the snapshot
changes, restart at cursor 0 rather than mixing archive states.

## v0.3.204 Optional Abstract

v0.3.204 adds optional `frontmatter.abstract` and the read-only live
`zet-catalog`. Existing archives require no migration and no zet is rewritten.

New or revised drafts may add a compact abstract with:

```text
archive create-draft <archive-root> --title <title> --abstract <text> --body <body>
```

Old zets without the field appear as `abstract_status: missing`. Review and
revise them gradually; do not bulk-generate or silently write abstracts only to
make the catalog look complete.

## Public Versions

| Version | Status | Upgrade note |
| --- | --- | --- |
| `v0.3.208` | current public pre-release | `wom-kit/docs/releases/v0.3.208.md` |
| `v0.3.207` | superseded public pre-release | `wom-kit/docs/releases/v0.3.207.md` |
| `v0.3.206` | superseded public pre-release | `wom-kit/docs/releases/v0.3.206.md` |
| `v0.3.205` | superseded public pre-release | `wom-kit/docs/releases/v0.3.205.md` |
| `v0.3.204` | superseded public pre-release | `wom-kit/docs/releases/v0.3.204.md` |
| `v0.3.203` | superseded public pre-release | `wom-kit/docs/releases/v0.3.203.md` |
| `v0.3.202` | superseded public pre-release | `wom-kit/docs/releases/v0.3.202.md` |
| `v0.3.201` | superseded public pre-release | `wom-kit/docs/releases/v0.3.201.md` |
| `v0.3.200` | superseded public pre-release | `wom-kit/docs/releases/v0.3.200.md` |
| `v0.3.199` | superseded public pre-release | `wom-kit/docs/releases/v0.3.199.md` |
| `v0.3.198` | superseded public pre-release | `wom-kit/docs/releases/v0.3.198.md` |
| `v0.3.197` | superseded public pre-release | `wom-kit/docs/releases/v0.3.197.md` |
| `v0.3.196` | superseded public pre-release | `wom-kit/docs/releases/v0.3.196.md` |
| `v0.3.195` | superseded public pre-release | `wom-kit/docs/releases/v0.3.195.md` |
| `v0.3.194` | superseded public pre-release | `wom-kit/docs/releases/v0.3.194.md` |
| `v0.3.193` | superseded public pre-release | `wom-kit/docs/releases/v0.3.193.md` |
| `v0.3.192` | superseded public pre-release | `wom-kit/docs/releases/v0.3.192.md` |
| `v0.3.191` | superseded public pre-release | `wom-kit/docs/releases/v0.3.191.md` |
| `v0.3.190` | superseded public pre-release | `wom-kit/docs/releases/v0.3.190.md` |
| `v0.3.189` | superseded public pre-release | `wom-kit/docs/releases/v0.3.189.md` |
| `v0.3.188` | superseded public pre-release | `wom-kit/docs/releases/v0.3.188.md` |
| `v0.3.187` | superseded public pre-release | `wom-kit/docs/releases/v0.3.187.md` |
| `v0.3.186` | superseded public pre-release | `wom-kit/docs/releases/v0.3.186.md` |
| `v0.3.7` | superseded public pre-release | `wom-kit/docs/releases/v0.3.7.md` |
| `v0.3.6` | superseded public pre-release | `wom-kit/docs/releases/v0.3.6.md` |
| `v0.3.5` | superseded public pre-release | `wom-kit/docs/releases/v0.3.5.md` |
| `v0.3.4` | superseded public pre-release | `wom-kit/docs/releases/v0.3.4.md` |
| `v0.3.3` | superseded public pre-release | `wom-kit/docs/releases/v0.3.3.md` |
| `v0.3.2` | superseded public pre-release | `wom-kit/docs/releases/v0.3.2.md` |
| `v0.3.1` | superseded public pre-release | `wom-kit/docs/releases/v0.3.1.md` |
| `v0.3.0` | superseded public pre-release | `wom-kit/docs/releases/v0.3.0.md` |
| `v0.2.60` | superseded public pre-release | `wom-kit/docs/releases/v0.2.60.md` |
| `v0.2.59` | superseded public pre-release | `wom-kit/docs/releases/v0.2.59.md` |
| `v0.2.58` | superseded public pre-release | `wom-kit/docs/releases/v0.2.58.md` |
| `v0.2.57` | superseded public pre-release | `wom-kit/docs/releases/v0.2.57.md` |
| `v0.2.56` | superseded public pre-release | `wom-kit/docs/releases/v0.2.56.md` |
| `v0.2.55` | superseded public pre-release | `wom-kit/docs/releases/v0.2.55.md` |
| `v0.2.54` | superseded public pre-release | `wom-kit/docs/releases/v0.2.54.md` |
| `v0.2.53` | superseded public pre-release | `wom-kit/docs/releases/v0.2.53.md` |
| `v0.2.52` | superseded public pre-release | `wom-kit/docs/releases/v0.2.52.md` |
| `v0.2.51` | superseded public pre-release | `wom-kit/docs/releases/v0.2.51.md` |
| `v0.2.50` | superseded public pre-release | `wom-kit/docs/releases/v0.2.50.md` |
| `v0.2.49` | superseded public pre-release | `wom-kit/docs/releases/v0.2.49.md` |
| `v0.2.48` | superseded public pre-release | `wom-kit/docs/releases/v0.2.48.md` |
| `v0.2.47` | superseded public pre-release | `wom-kit/docs/releases/v0.2.47.md` |
| `v0.2.46` | superseded public pre-release | `wom-kit/docs/releases/v0.2.46.md` |
| `v0.2.45` | superseded public pre-release | `wom-kit/docs/releases/v0.2.45.md` |
| `v0.2.44` | superseded public pre-release | `wom-kit/docs/releases/v0.2.44.md` |
| `v0.2.43` | superseded public pre-release | `wom-kit/docs/releases/v0.2.43.md` |
| `v0.2.42` | superseded public pre-release | `wom-kit/docs/releases/v0.2.42.md` |
| `v0.2.41` | superseded public pre-release | `wom-kit/docs/releases/v0.2.41.md` |
| `v0.2.40` | superseded public pre-release | `wom-kit/docs/releases/v0.2.40.md` |
| `v0.2.39` | superseded public pre-release | `wom-kit/docs/releases/v0.2.39.md` |
| `v0.2.38` | superseded public pre-release | `wom-kit/docs/releases/v0.2.38.md` |
| `v0.2.37` | superseded public pre-release | `wom-kit/docs/releases/v0.2.37.md` |
| `v0.2.36` | superseded public pre-release | `wom-kit/docs/releases/v0.2.36.md` |
| `v0.2.35` | superseded public pre-release | `wom-kit/docs/releases/v0.2.35.md` |
| `v0.2.34` | superseded public pre-release | `wom-kit/docs/releases/v0.2.34.md` |
| `v0.2.33` | superseded public pre-release | `wom-kit/docs/releases/v0.2.33.md` |
| `v0.2.32` | superseded public pre-release | `wom-kit/docs/releases/v0.2.32.md` |
| `v0.2.31` | superseded public pre-release | `wom-kit/docs/releases/v0.2.31.md` |
| `v0.2.30` | superseded public pre-release | `wom-kit/docs/releases/v0.2.30.md` |
| `v0.2.29` | superseded public pre-release | `wom-kit/docs/releases/v0.2.29.md` |
| `v0.2.28` | superseded public pre-release | `wom-kit/docs/releases/v0.2.28.md` |
| `v0.2.27` | superseded public pre-release | `wom-kit/docs/releases/v0.2.27.md` |
| `v0.2.26` | superseded public pre-release | `wom-kit/docs/releases/v0.2.26.md` |
| `v0.2.25` | superseded public pre-release | `wom-kit/docs/releases/v0.2.25.md` |
| `v0.2.24` | superseded public pre-release | `wom-kit/docs/releases/v0.2.24.md` |
| `v0.2.23` | superseded public pre-release | `wom-kit/docs/releases/v0.2.23.md` |
| `v0.2.22` | superseded public pre-release | `wom-kit/docs/releases/v0.2.22.md` |
| `v0.2.21` | superseded public pre-release | `wom-kit/docs/releases/v0.2.21.md` |
| `v0.2.20` | superseded public pre-release | `wom-kit/docs/releases/v0.2.20.md` |
| `v0.2.19` | superseded public pre-release | `wom-kit/docs/releases/v0.2.19.md` |
| `v0.2.18` | superseded public pre-release | `wom-kit/docs/releases/v0.2.18.md` |
| `v0.2.17` | superseded public pre-release | `wom-kit/docs/releases/v0.2.17.md` |
| `v0.2.16` | superseded public pre-release | `wom-kit/docs/releases/v0.2.16.md` |
| `v0.2.15` | superseded public pre-release | `wom-kit/docs/releases/v0.2.15.md` |
| `v0.2.14` | superseded public pre-release | `wom-kit/docs/releases/v0.2.14.md` |
| `v0.2.13` | superseded public pre-release | `wom-kit/docs/releases/v0.2.13.md` |
| `v0.2.12` | superseded public pre-release | `wom-kit/docs/releases/v0.2.12.md` |
| `v0.2.11` | superseded public pre-release | `wom-kit/docs/releases/v0.2.11.md` |
| `v0.2.10` | superseded public pre-release | `wom-kit/docs/releases/v0.2.10.md` |
| `v0.2.9` | superseded public pre-release | `wom-kit/docs/releases/v0.2.9.md` |
| `v0.2.8` | superseded public pre-release | `wom-kit/docs/releases/v0.2.8.md` |
| `v0.2.7` | superseded public pre-release | `wom-kit/docs/releases/v0.2.7.md` |
| `v0.2.6` | superseded public pre-release | `wom-kit/docs/releases/v0.2.6.md` |
| `v0.2.5` | superseded public pre-release | `wom-kit/docs/releases/v0.2.5.md` |
| `v0.2.4` | superseded public pre-release | `wom-kit/docs/releases/v0.2.4.md` |
| `v0.2.3` | superseded public pre-release | `wom-kit/docs/releases/v0.2.3.md` |
| `v0.2.2` | superseded public pre-release | `wom-kit/docs/releases/v0.2.2.md` |

## From `v0.3.202` To `v0.3.203`

One additive user-reviewed operator vocabulary correction. No migration is required.

Operator-visible notes:

- `archive ai-response-concept-guide <archive-root> --topic operator_vocabulary
  --locale ko-KR --dry-run --format json` now reports the reviewed operator
  vocabulary under `confirmed_operator_language`.
- The reviewed Korean operator terms include `object_id` as `오브제 아이디`,
  `doctor` as `검진`, `provider` as `외부 서비스`, `containment` as `포함 관계`,
  `safe_preview` as `미리보기`, `approved_write` as `승인 후 쓰기`,
  `external_report` as `공개용 문서`, and `private_working_note` as
  `비공개 문서`.
- `needs_user_translation` remains available as an empty bucket for future
  naming-review items.
- See `wom-kit/docs/releases/v0.3.203.md`.

## From `v0.3.201` To `v0.3.202`

One additive read-only Korean-first vocabulary patch for AI operators. No migration is required.

Operator-visible notes:

- `archive ai-response-concept-guide <archive-root> --topic operator_vocabulary
  --locale ko-KR --dry-run --format json` now returns a grouped vocabulary
  layer for archive entrypoints, zets/drafts, objets/evidence, lifecycle
  actions, checks, connections, providers, and secrets.
- The `all` topic includes the new `operator_vocabulary` section.
- Machine terms stay unchanged; the new phrases guide human-facing prose only.
- See `wom-kit/docs/releases/v0.3.202.md`.

## From `v0.3.200` To `v0.3.201`

One additive read-only AI operator signpost. No migration is required.

Operator-visible notes:

- New `archive ai-start-here <archive-root> --dry-run --format markdown|json`
  command, with `start-here` and `operator-start-here` aliases.
- The command projects existing runtime-context, canonical entrypoint, and
  operational-context metadata into one first-read map for an entering AI
  operator.
- It writes nothing, calls no providers, reads no secrets, reads no zettel
  bodies or objet bytes, and redacts local absolute paths by default.
- See `wom-kit/docs/releases/v0.3.201.md`.

## From `v0.3.199` To `v0.3.200`

One additive schema/doctor validation patch for object-storage manifest reconcile audit receipts. No migration is required.

Operator-visible notes:

- `object-storage-wom-location-reconcile --approve` still writes the same
  local-only audit receipt, but that receipt now has a public JSON schema:
  `wom-kit/schemas/object-storage-manifest-reconcile-receipt.schema.json`.
- `archive doctor` now checks object-storage manifest reconcile audit receipts
  for schema, action, reviewer, path, updated execution receipt refs, positive
  update counts, and non-echo privacy guards.
- The command behavior, approval gates, and no-provider/no-credential/no-object-byte
  boundaries are unchanged.
- See `wom-kit/docs/releases/v0.3.200.md`.

## From `v0.3.198` To `v0.3.199`

One additive object-storage receipt/manifest binding repair patch. No migration is required.

Operator-visible notes:

- `archive doctor` no longer flags a repeated `skipped_remote_same` receipt as
  `object_storage_upload_wom_location_missing` when an existing valid
  `wom_uploaded` location already covers the same object/provider/store/remote
  key.
- New CLI command:
  `archive object-storage-wom-location-reconcile <archive-root> --receipt
  <receipt> --dry-run|--approve`.
- Always run `--dry-run` first. `--approve` requires `--reviewed-by`.
- The command never calls providers, reads credentials, reads object bytes,
  uploads, downloads, syncs, or checks remote availability.
- Approved mode writes only `objects/manifests/files.jsonl` plus one audit
  receipt under `receipts/providers/object-storage-manifest-reconciles/`.
- Candidate output intentionally does not echo object ids, remote keys, bucket
  names, provider URLs, exact credential refs, or local absolute paths.
- See `wom-kit/docs/releases/v0.3.199.md`.

## From `v0.3.197` To `v0.3.198`

One additive reconcile approval-result status cleanup patch. No migration is required.

Operator-visible notes:

- `remint-reconcile --approve --format json` and
  `retire-draft-reconcile --approve --format json` now report
  `status: reconcile_applied` and `overall_status: reconcile_applied` after a
  successful write.
- The approval result now points to `suggested_next_action:
  run_doctor_to_verify_reconcile` and doctor verification `next_safe_actions`.
- Applied approval output no longer keeps the earlier dry-run
  `needs_content_change_review` status, and no longer says a new approval write
  is pending.
- On Windows, prefer explicit UTF-8 capture for JSON examples instead of bare
  PowerShell `>` redirection.
- When directly repairing a schema enum on a zettel that also has retired-draft
  receipts, use the paired reviewed flow: `remint-reconcile` first, then
  `retire-draft-reconcile`, each dry-run before approve.
- Reconcile classification and approval gates are unchanged.
- See `wom-kit/docs/releases/v0.3.198.md`.

## From `v0.3.196` To `v0.3.197`

One additive reconcile dry-run next-action guidance patch. No migration is required.

Operator-visible notes:

- `remint-reconcile --dry-run --format json` and `retire-draft-reconcile --dry-run --format json`
  now include `status`, `overall_status`, `suggested_next_action`, `would_write`,
  `approval_would_write`, and `approval_requires_content_changed_ack`.
- A `content_change` dry-run now says that human content review is required before any
  `--approve --content-changed-ack` run.
- `retire-draft-reconcile --format text` now prints `Next safe actions` when present.
- Reconcile classification and approval gates are unchanged.
- See `wom-kit/docs/releases/v0.3.197.md`.

## From `v0.3.195` To `v0.3.196`

One additive doctor progress-log path-policy clarification patch. No migration is required.

Operator-visible notes:

- `doctor --progress-log <path>` summary output now marks relative progress-log paths as
  cwd-relative and relative to the current working directory.
- The summary labels progress logs as local progress artifacts, not archive receipts, and says
  not to commit them by default.
- Absolute progress-log inputs are not echoed in the summary.
- Default `doctor` behavior, progress-log write behavior, and exit-code semantics are unchanged.
- See `wom-kit/docs/releases/v0.3.196.md`.

## From `v0.3.194` To `v0.3.195`

One additive doctor output path-policy clarification patch. No migration is required.

Operator-visible notes:

- `doctor --output <path>` summary output now marks the path as archive-relative and relative to
  the archive root.
- The summary labels full doctor result files as local diagnostic artifacts, not archive receipts,
  and says not to commit them by default.
- `mint_retired_draft_sha_mismatch` now includes a hint explaining why
  `retire-draft-reconcile --dry-run` is the safe first step.
- Default `doctor` behavior and exit-code semantics are unchanged.
- See `wom-kit/docs/releases/v0.3.195.md`.

## From `v0.3.193` To `v0.3.194`

One additive doctor result-capture and diagnostic-guidance patch. No migration is required.

Operator-visible notes:

- `doctor --output <path>` writes the full diagnostics JSON array to a file and prints a compact
  stdout summary.
- `doctor --summary`, `--errors-only`, and `--diagnostic-level ERROR,WARN` reduce stdout volume
  without changing exit-code semantics.
- `provenance.creation_mode` enum errors, object-storage receipt/manifest link gaps, and BOM
  zettel warnings now include safer next-action hints.
- Default `doctor` output is unchanged unless the new options are used.
- See `wom-kit/docs/releases/v0.3.194.md`.

## From `v0.3.192` To `v0.3.193`

One additive doctor local-profile secret-safety progress patch. No migration is required.

Operator-visible notes:

- `doctor --progress` now emits internal progress for `local-profile-secret-safety`: gitignore
  checks, archive walking, checked-file counts, content-scan counts, local-profile counts,
  skipped-dir counts, and a final summary.
- Large archive walks can emit `still checking local profile secret safety` heartbeats.
- Eligible config/text secret-content checks now stream in chunks and can emit
  `still scanning secret content ...` for long reads.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged except for any
  pre-existing diagnostics the stage already reported.
- See `wom-kit/docs/releases/v0.3.193.md`.

## From `v0.3.191` To `v0.3.192`

One additive doctor progress volume-control patch. No migration is required.

Operator-visible notes:

- `doctor --progress` now uses compact stderr progress by default, keeping stage start/done,
  receipt milestones, quiet-interval heartbeats, and key edge-index lifecycle events.
- Use `doctor --progress --progress-detail verbose` to preserve the full detailed receipt trace.
- Use `doctor --progress-log <path>` to write every progress event as JSONL while stderr remains
  compact; the log option can also be used without `--progress`.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.192.md`.

## From `v0.3.190` To `v0.3.191`

One additive doctor edge-evolution progress patch. No migration is required.

Operator-visible notes:

- `doctor --strict --progress` now names the target edge-receipt evolution target with an
  archive-relative path after a mint target sha mismatch.
- Edge receipt index work now reports loading, scan counts, ready counts, cache hits, and target
  candidate counts.
- Target evolution replay now reports target zettel reads, missing-cutoff/no-edge-list skips,
  strict/inclusive history checks, and ok/no-match results.
- Long edge receipt scans can emit `still scanning edge receipts` liveness.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.191.md`.

## From `v0.3.189` To `v0.3.190`

One additive doctor file-ref drilldown patch. No migration is required.

Operator-visible notes:

- `doctor --strict --progress` now drills into mint receipt file-reference checks: resolving path,
  checking existence, resolved archive-relative ref, sha field check, stat, cache hit, hash
  start/end, mismatch, target edge-evolution check, and ref-ok.
- Fresh SHA-256 reads now always emit `hashing <section> file bytes` before reading, regardless of
  file size.
- `still hashing ... file bytes` remains a chunk heartbeat for longer reads, not a mandatory
  small-file line.
- Retired mint sources now emit `source file ref skipped; source retired`.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.190.md`.

## From `v0.3.188` To `v0.3.189`

One additive doctor liveness patch. No migration is required.

Operator-visible notes:

- `doctor --strict --progress` now emits `started receipt checks`, source/target/snapshot file-ref
  check names, and `completed receipt checks` for every mint receipt.
- Large mint-receipt file SHA checks can emit content-free `hashing ... file bytes`,
  `still hashing ... file bytes`, and `hashed ... file bytes` liveness.
- The heartbeat-mode transition message now says minimal file-ref liveness is emitted every receipt.
- Counted-stage ETA stays `eta=warming_up` through the first nine samples or first 30 seconds of a
  stage.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.189.md`.

## From `v0.3.187` To `v0.3.188`

One additive doctor progress patch. No migration is required.

Operator-visible notes:

- `doctor --strict --progress` now emits a mint-receipt entry for every checked mint receipt.
- Detailed mint-receipt sub-steps now run through receipt 4, then resume every 250 receipts and
  for the final receipt.
- After receipt 4, progress explicitly says it is continuing with receipt heartbeat and sampled
  detailed substeps.
- Counted-stage ETA uses per-stage timing and reports `eta=warming_up` for the first few samples
  instead of projecting from too little data.
- Result JSON, diagnostics, receipts, manifests, and archive files are unchanged.
- See `wom-kit/docs/releases/v0.3.188.md`.

## From `v0.3.186` To `v0.3.187`

One additive AI artifact lifecycle inventory patch. No migration is required.

Operator-visible notes:

- `archive ai-artifact-inventory <archive-root> --dry-run --format json` inventories AI-generated
  artifact candidates under allowlisted roots only: `.wom-scratch/`, `workbench/ai-scratch/`,
  `staging/ai/inbox/`, and `staging/ai/reviewed/`.
- The inventory reports whether candidates are still `unreviewed_ai_artifact` or already have a
  matching AI artifact `source-intake-record`.
- JSONL chat logs and other AI-generated files are treated as possible raw evidence to preserve as
  objets, not as canonical zet bodies. The safe path is raw artifact -> objet/source evidence ->
  derived/distilled text -> draft zet -> human review -> canonical zet.
- The command reads no file bodies, calculates no content hashes, writes nothing, deletes nothing,
  creates no zets, calls no providers, and hides archive-relative paths unless
  `--show-relative-paths` is explicitly used for local operator review.
- See `wom-kit/docs/releases/v0.3.187.md`.

## From `v0.3.185` To `v0.3.186`

One additive operator-diagnostics patch. No migration is required.

Operator-visible notes:

- `object-storage-adopt-existing` now accepts `--stop-after-plan`. It may be combined with an
  `--approve` command shape to resolve the same key-map/resume plan, then stop before credential
  value reads, provider HEADs, manifest updates, or execution receipt writes.
- The final `--format json` or text result is written to stdout. Optional `--progress` heartbeats
  are written to stderr, so scripts that need the structured result should watch stdout or redirect
  stderr separately.
- `adopt_summary` now includes `plan_only`, `plan_only_stop_stage`,
  `planned_remote_head_count`, `unresolved_remote_key_count`,
  `existing_matching_wom_uploaded_location_count`, and same-store `wom_uploaded`
  raw-vs-gating counts. These explain why a simple `store_ref` manifest count can be higher than
  the stricter resume skip candidates.
- `doctor --strict --progress` now emits detailed mint-receipt sub-steps for the first three
  receipts and prints `completed receipt checks` for detailed receipts, making a post-link stall
  easier to localize.
- See `wom-kit/docs/releases/v0.3.186.md`.

## From `v0.3.184` To `v0.3.185`

One additive diagnostics patch. No migration is required.

Operator-visible notes:

- `object-storage-adopt-existing --progress` still prints the v0.3.183 matching resume summary.
  It now also prints a `resume nonmatching-provider summary` when same-provider digest-bound
  locations exist but do not match this run's `store_ref` or resolved `remote_key`.
- `adopt_summary` now includes `same_provider_nonmatching_location_count`,
  `same_provider_nonmatching_declared_uploaded_count`, `same_provider_store_ref_mismatch_count`,
  and `same_provider_remote_key_mismatch_count`.
- `provider_location_mismatch_gap` warns that legacy/nonmatching `declared_uploaded` locations are
  evidence, but not `--skip-existing-wom-uploaded` candidates for the current store/key run.
- `doctor --strict --progress` now splits `checking target mint receipt link` into target mint block,
  receipt-path, relative-path, comparison, and ok/error sub-steps.
- `archive version <root>` text output now includes an import-module redaction line, and
  `--no-redact-local-paths` can show the active module path when diagnosing source-mirror/editor
  install drift.
- See `wom-kit/docs/releases/v0.3.185.md`.

## From `v0.3.183` To `v0.3.184`

One additive human-readable zet viewer patch. No migration is required.

Operator-visible notes:

- `archive read-zettel --section document` now gives a WOM-rendered document read of one zet:
  frontmatter details are hidden and text output prints only the body.
- JSON output includes `viewer_mode`, `frontmatter_hidden`, and
  `raw_frontmatter_delimiters_echoed: false` so simple viewers can separate storage metadata from
  document content.
- The canonical Markdown file format still uses YAML frontmatter for ids, provenance, edges,
  visibility, and receipts. The change is about the reading surface, not the storage format.
- See `wom-kit/docs/zet-frontmatter-viewer-contract.md` and
  `wom-kit/docs/releases/v0.3.184.md`.

## From `v0.3.182` To `v0.3.183`

One additive resume-diagnostics and progress patch. No migration is required.

Operator-visible notes:

- `object-storage-adopt-existing --progress` now prints an `adopt-plan` resume summary with
  matching provider/store/key location counts split into `wom_uploaded`, `declared_uploaded`, and
  other. This appears before the verified remote-HEAD loop.
- `adopt_summary` now includes `existing_matching_location_count`,
  `existing_declared_uploaded_count`, `existing_other_location_count`, and
  `expected_resume_skip_count`.
- Matching `declared_uploaded` locations now emit `declared_upload_resume_gap`: they explain a
  partial state where many provider/store/key locations exist but cannot be skipped by
  `--skip-existing-wom-uploaded` because they are not WOM-verified `wom_uploaded` locations.
- `doctor --strict --progress` now breaks target frontmatter loading into read/BOM/fence/YAML/load
  and mint-link sub-steps.
- See `wom-kit/docs/releases/v0.3.183.md`.

## From `v0.3.181` To `v0.3.182`

One additive basoon revalidation follow-up. No migration is required.

Operator-visible notes:

- `archive object-storage-adopt-existing ... --approve --skip-existing-wom-uploaded` is a
  resume helper for interrupted verified adopts. Objects that already have a matching
  `wom_uploaded` manifest location for the same provider/store/key are reported as
  `already_wom_uploaded_manifest` and are not remote-HEADed again.
- The default remains conservative: without `--skip-existing-wom-uploaded`, verified adopt still
  re-HEADs each resolved key. The resume option is refused with `--content-hash-verify`.
- Adopt planning now reports how many matching existing `wom_uploaded` locations it found and
  emits a `resume_hint` warning when the count is nonzero but the resume option is not enabled.
- `archive doctor --strict --progress` now prints sampled `mint-receipts` sub-steps and a cache
  summary for file SHA-256, zettel frontmatter, and BOM evidence.
- See `wom-kit/docs/releases/v0.3.182.md`.

## From `v0.3.180` To `v0.3.181`

One additive operator-progress patch. No migration is required.

Operator-visible notes:

- `archive staged-cleanup-check <root> --staged <folder> --dry-run --progress` now streams
  content-free progress to stderr while it loads manifests, scans zettel references, walks staged
  entries, verifies files, and hashes large staged/store files.
- Default command output and result JSON are unchanged when `--progress` is omitted.
- Progress lines include stage names and counts/byte totals only. They do not add staged file
  names, object ids, local absolute paths, provider URLs, tokens, or secret values.
- See `wom-kit/docs/releases/v0.3.181.md`.

## From `v0.3.179` To `v0.3.180`

One additive performance-hardening patch. No migration is required.

Operator-visible notes:

- **Large `object-storage-adopt-existing --key-map` plan resolution should no longer scan the
  manifest once per object.** The adopt plan now builds one per-run manifest index and uses
  O(1) object-id lookup while preserving first-record-wins semantics.
- **`archive doctor` receipt stages reuse per-run file evidence.** File SHA-256 and zettel
  frontmatter/BOM checks are cached during one doctor run, reducing repeated disk reads in
  `mint-receipts` and related receipt checks.
- Existing command shapes, progress output, result JSON, and receipt formats are unchanged.
- See `wom-kit/docs/releases/v0.3.180.md`.

## From `v0.3.178` To `v0.3.179`

One additive redacted diagnostic-output patch. No migration is required.

Operator-visible notes:

- **`archive remint-reconcile --diagnostic-only --format json`** is a dry-run-only projection
  that keeps `drift_class`, `body_changed`, `body_diff_diagnostic`, blockers/warnings, and
  frontmatter field names/counts while omitting `current_canonical_text` and frontmatter values.
- **Approval is intentionally not redacted.** `--diagnostic-only` is refused with `--approve`
  because the approve path must still show the current on-disk content for human review.
- Existing `remint-reconcile --format json` output is unchanged for compatibility.
- See `wom-kit/docs/releases/v0.3.179.md`.

## From `v0.3.177` To `v0.3.178`

One additive operator-progress patch. No migration is required.

Operator-visible notes:

- **`archive doctor --progress`** streams stage start/done lines to stderr during long doctor
  runs. JSON/text diagnostic output is unchanged.
- **`object-storage-adopt-existing --progress`** streams safe stage/count heartbeats for plan
  resolution and adopt HEAD loops. It does not print object ids, remote keys, bucket names,
  provider URLs, exact credential refs, tokens, or secret values.
- **No migration; default output unchanged.** The new output appears only when `--progress` is
  passed.
- See `wom-kit/docs/releases/v0.3.178.md`.

## From `v0.3.176` To `v0.3.177`

One additive force-reupload hardening patch for the object-storage upload adapter. No migration is
required; default idempotency behavior is unchanged.

Operator-visible notes:

- **`--force-reupload` now also bypasses resume-ledger-only skips.** If a post-crash or
  handoff state has a terminal resume-ledger row but the manifest does not currently have a
  `wom_uploaded` location, a reviewed force run now reaches the provider PUT path instead of
  returning `skipped_already_present`.
- **A forced zero-PUT result is blocked.** Force run output includes `forced_reupload: true`;
  if no provider PUT is attempted, the run reports `force_reupload_not_performed` with
  `ok:false` instead of a misleading executed success.
- **No migration; no default behavior change.** Without `--force-reupload`, the existing
  resume-ledger/idempotency skips behave as before.
- See `wom-kit/docs/releases/v0.3.177.md`.

## From `v0.3.175` To `v0.3.176`

One additive, DX-only reconcile body-diff diagnostic. **No behavior or classification change, no
migration.** The drift classifier is byte-identical.

Operator-visible notes:

- **`v0.3.176` adds a content-free `body_diff_diagnostic`** to the `remint-reconcile` and
  `retire-draft-reconcile` plan output. When a drift is classified `content_change` because the
  two bodies still differ AFTER the single leading BOM strip + CRLF/CR→LF fold, the plan now
  reports WHICH kind of sub-BOM residual it is: a fixed `category`
  (`final_newline_only` / `trailing_whitespace_only` / `unicode_normalization_only` /
  `content_difference`), a `first_differing_byte_offset` (an integer), a `normalized_length_delta`
  (an integer), and — for the unicode case only — a closed-enum NFC/NFD form label. It emits ONLY
  numbers and fixed labels, never any body text.
- **It is a STRICT CLASSIFICATION NO-OP.** It is computed AFTER the drift_class predicate and only
  decorates the output dict (exactly like the v0.3.172 strip-BOM preview). `drift_class`,
  `classification_basis`, `content_change_ack_required`, and `bytes_normalized_for_content_compare`
  are byte-identical with and without it. A mixed whitespace/normalization + real-edit diff stays
  the honest `content_difference` — never laundered.
- **The key is absent when it would be misleading**: on a no-anchor / no-snapshot plan
  (`body_changed` None) and on a `format_drift` plan (`body_changed` False). Both CLI text printers
  gain one content-free summary line; JSON consumers see the key only when present.
- **No migration; no behavior change.** Existing receipts and manifests are unaffected.
- See `wom-kit/docs/releases/v0.3.176.md`.

## From `v0.3.174` To `v0.3.175`

Two additive live-verification aids for the object-storage upload adapter. No migration is
required; default behavior and existing receipts/manifests are byte-identical.

Operator-visible notes:

- **`v0.3.175` adds an approval-gated `--force-reupload`** on `object-storage-upload`. It
  re-PUTs an already-present, size/hash-matching object so a client can exercise a LIVE
  provider PUT (e.g. a forced small multipart). It requires `--approve` AND `--reviewed-by`,
  is refused for any non-sha-derived `--key-strategy`, is inert under `--dry-run`, and still
  runs the pre-PUT local `sha256(local)==object_id` re-verify so a corrupt local file is
  refused before any PUT. The execution receipt records a top-level `forced_reupload` boolean.
- **A real multipart (`part_count>1`) is now recognized as an upload tier2 proof**, alongside
  the existing 5 GiB `bytes_uploaded` path. A forced small multipart can therefore prove
  upload tier2 for a store with no >5 GiB object. The adopt tier ladder is unaffected.
- **No migration; default behavior and existing receipts/manifests are byte-identical.** With
  the flag absent, every path is unchanged; a default receipt gains only an always-present
  `forced_reupload: false` boolean.
- See `wom-kit/docs/releases/v0.3.175.md`.

## From `v0.3.173` To `v0.3.174`

One additive fix to the verified-adopt tiered gate. No migration is required; existing
receipts and manifests are unaffected, and the object-storage-upload tier ladder is
byte-identical.

Operator-visible notes:

- **Adopt tiered gating is decoupled from the upload 5 GiB multipart proof.** A verified
  `object-storage-adopt-existing --approve` is HEAD-only (it moves zero bytes), so it no
  longer needs a store proven to the object-storage-upload tier 2 (a 5 GiB / multipart PUT
  proof). It now uses a binary adopt-specific gate: a single tiny-first adopt is always
  permitted, and exactly one prior verified tiny-first adopt unlocks a batch adopt of any
  size. Operator remedy for a large handover: run `object-storage-adopt-existing --only
  <one-sha> --approve` once, then re-run the full `--key-map` batch.
- **Adopt blocker token renamed.** The adopt gate blocker is now `adopt_tiny_first_unmet`
  (was `tiered_gate_unmet`). The object-storage-upload gate keeps `tiered_gate_unmet`
  unchanged. Update any script that matched the adopt blocker string.
- **No migration; nothing else changes.** Existing execution receipts and manifest locations
  are unaffected. An upload receipt still never unblocks adopt, a declared/unverified adopt
  still never counts and never gates a PUT, and a wrong `--key-map` still self-limits to zero
  adopts.
- See `wom-kit/docs/releases/v0.3.174.md`.

## From `v0.3.172` To `v0.3.173`

One additive command. No migration is required, and every default path is byte-identical to
v0.3.172.

Operator-visible notes:

- **New `archive migrate --target base-link-types --dry-run|--approve --reviewed-by
  <actor>`.** It appends every base WOM-kit link type missing from an archive-local
  `zettel-kasten/types.yml` (a superset of the recommended-9 `link-types-v0.3` set — it also
  pulls `continues`). It is append-only and no-clobber: no existing entry is removed,
  renamed, reordered, or altered in value, so a divergent same-id customization always wins
  (reported under `present_not_overwritten`). `--reviewed-by` is required with `--approve`.
  It writes a receipt (`receipt_kind: base_link_types_sync`) under
  `receipts/migrations/base-link-types.*.migration.json`, is atomic with rollback, and is
  idempotent. There is deliberately **no `--revert`** (`--revert --target base-link-types`
  fails closed). No change if you do not run it.
- **Safe no-op with no local `types.yml`.** If your archive has no local
  `zettel-kasten/types.yml`, the sync writes nothing and creates no file — you already
  inherit all current and future base link types. Do not add a local `types.yml` just to run
  this; a local `types.yml` permanently shadows (freezes) the base.
- **Doctor routing.** `archive doctor` now points an operator hitting an undefined edge type
  toward `archive migrate --target base-link-types --dry-run`.
- **Honesty.** Once an archive has its own `types.yml`, it shadows the base permanently, so
  every future base link type also needs a manual `migrate --target base-link-types` (no
  automatic propagation). Sync copies base entry shapes as of this release (a snapshot). It
  normalizes/rewrites the whole `types.yml` via `safe_dump` — comments, anchors, flow-style,
  and key ordering may be normalized — exactly like the sibling `link-types-v0.3` migration.
  Existing entries are preserved by value/id; surrounding formatting is not byte-preserved.
  Review the diff.
- See `wom-kit/docs/releases/v0.3.173.md`.

## From `v0.3.171` To `v0.3.172`

Two verification-honesty fixes. Both are additive; no migration is required, and every
default path is byte-identical to v0.3.171.

Operator-visible notes:

- **New `--multipart-part-size <BYTES>` and `--allow-tiny-parts` on
  `object-storage-upload`.** Default part size (64 MiB) is unchanged. An override is
  bounded to `[4096, 64 MiB]`, and below the default it requires `--allow-tiny-parts`.
  Paired with a lowered `--multipart-threshold`, it forces multipart on a small object so
  you can prove LIVE R2 multipart. It changes only how the file is fragmented for reads;
  the whole-object before-hash, the HEAD-after full-object verify, orphan cleanup, and the
  leak gate are unchanged. Real R2 rejects multipart parts smaller than 5 MiB except the
  last, so a tiny part size is a live-verification aid — a live tiny-part rejection is an
  upload rejection (failed status), never a silent integrity bypass. No change if you do
  not pass the flag.
- **Additive receipt field.** The object-storage upload execution receipt gains
  `effective_multipart_part_size_bytes`. The schema is non-breaking (no
  `additionalProperties:false`; the field is not `required`). Existing receipts and
  consumers are unaffected.
- **Strip-bom dry-run parity.** `--strip-bom` on a `--dry-run` of `remint-reconcile` and
  `retire-draft-reconcile` now previews the same strip-intent metadata (`bom_stripped`,
  `bom_strip_note`) an `--approve` run records. This is a strict classification no-op:
  `drift_class` and the content-change ack requirement are identical whether `--strip-bom`
  is passed or not, so a real `content_change` is never laundered to `format_drift`.
- See `wom-kit/docs/releases/v0.3.172.md`.

## From `v0.3.170` To `v0.3.171`

This release adds one opt-in flag, `--key-map`, to `object-storage-adopt-existing`.
It is additive and adopt-only: the default path (no `--key-map`) is byte-identical to
v0.3.170, and `object-storage-upload` is unchanged. No migration is required.

Operator-visible notes:

- **New `--key-map <file>` on `object-storage-adopt-existing`.** Hand WOM the exact
  existing remote key per object, as JSONL, one object per line:
  `{"sha256":"<64hex>","remote_key":"<key>"}`. For a mapped object the map value is
  the resolved key verbatim, so `--key-strategy`/`--key-prefix`/
  `--key-append-extension` are ignored for that object. Use this when objects already
  live under your own per-object filename extension that the content-addressed
  template cannot recover (the prehashed-ledger case, where the manifest logical_key
  has no extension). Objects with no map entry are reported and NOT adopted.
- **Safety is unchanged and stronger.** Size is always sourced from the manifest, not
  the map; a mapped key that 404s or size-mismatches re-uploads rather than
  false-skipping; each key must digest-bind (the object's sha256 as a path segment or
  filename stem) and pass the leak guard; a malformed or ambiguous map is whole-run
  fatal and adopts nothing. For any map you did not mechanically generate from a
  trusted per-object upload record, add `--content-hash-verify` — it is the only
  cryptographic proof against a same-size, different-bytes object.
- **No change if you do not use it.** Without `--key-map`, adopt behaves exactly as in
  v0.3.170. See `wom-kit/docs/releases/v0.3.171.md` and the runbook
  `wom-kit/docs/object-storage-adopt-existing-key-map-runbook.md`.

## From `v0.3.169` To `v0.3.170`

This release adds runtime AI-operator discipline norms. It is docs-only and
additive: no command, schema, receipt, or archive change, and no new
WOM-enforced check. No migration is required.

Operator-visible notes:

- **New `AI-Operator Discipline` section on the runtime surfaces.** The three
  `AGENTS.md` templates (personal/company/family), the runtime `SKILL.md`, and
  `wom-ai-runtime-skill-plugin-layer.md` now carry three behavioral norms an
  operator AI applies: record the source the human actually encountered and never
  silently substitute a "more authoritative"/original one; enumerate the
  installed/available tools before declaring a task impossible or degrading it; and
  carry forward already-established/approved state instead of re-asking. If you have
  copied an older `AGENTS.md` into a real archive, you may add the new section, but
  nothing breaks if you do not — it changes no command behavior.
- **New source-substitution axis in `text-provenance-hierarchy.md`.** A `## 7.
  Encountered-Source Fidelity` subsection names both provenance axes explicitly (the
  existing derivation-tool axis and the new source-substitution axis). Documentation
  only; the provenance model gains no new required field.
- **Guidance, not enforcement.** WOM does not validate provenance fidelity, tool
  enumeration, or state carry-over, and this release adds no check that does. The
  `ai-response-concept-guide` topic enum is unchanged. See
  `wom-kit/docs/releases/v0.3.170.md`.

## From `v0.3.168` To `v0.3.169`

This release adds a read-only operator-feedback delivery ledger and an
approval-gated batched mark-delivered command. All changes are additive; no
migration is required.

Operator-visible notes:

- **No archive migration; existing records unchanged; no hash change.** The
  `operator-feedback.schema.json` record gains two OPTIONAL string properties,
  `delivered_at` and `acknowledged_at` (not added to `required`), so existing
  `ops/feedback/*.yml` records validate and are read as-is. A new
  `operator-feedback-delivery-receipt.schema.json` ships for the batch receipt.
- **New read-only `archive operator-feedback-ledger`** (aliases `feedback-ledger`,
  `feedback-board`): aggregates delivery-status counts + a pending (draft) list +
  the newest delivery boundary from `ops/feedback/*.yml`. It writes nothing, reads
  no feedback body, and echoes no feedback ref, title, path, token, or secret
  values. Malformed records are counted as `unreadable` and skipped. Records
  delivered via the older `--status delivered` path have no `delivered_at`, so the
  boundary falls back to their `updated_at`.
- **New approval-gated `archive operator-feedback-mark-delivered`** (alias
  `feedback-mark-delivered`): `--dry-run` previews the draft->delivered transitions
  and writes nothing; `--approve --reviewed-by <actor>` marks every pending `draft`
  record delivered, stamps `delivered_at`, and writes one batch receipt. `--only
  <id>` marks a single record. It only touches `draft` records, is idempotent, and
  skips malformed records without half-writing others.
- **Truth boundary (no overclaim).** This is metadata lifecycle only.
  `external_submission_performed` stays `false`; `delivered` means the operator
  marked it delivered, not that anything was submitted externally or proven
  received. See `wom-kit/docs/releases/v0.3.169.md`.

## From `v0.3.167` To `v0.3.168`

This release adds draft-time identity hygiene, an attributed mint affirmation flag,
a discoverability pointer to retire consumed drafts, a base `continues` edge type,
and draft-time `--kind` validation. All changes are additive; no migration is
required.

Operator-visible notes:

- **No archive migration; existing ids unchanged; no hash change.** No existing
  canonical id is renamed or normalized. The mint receipt gains a new additive
  `affirmations` array (`item_id`, `affirmed_by`, `affirmed_at`), and the mint result
  gains a `next_safe_actions` string list; `mint-receipt.schema.json` uses no
  `additionalProperties: false`, so existing receipts, manifests, and zets are
  accepted as-is.
- **Draft-id hygiene (forward-only).** A NEW draft whose title has no ASCII
  alphanumerics (a titleless or pure-Hangul title) now gets a `zet_<ts>_note` id
  instead of the old `zet_<ts>_draft` fallback. This affects only newly created
  drafts; existing ids are untouched and mint gains no id-rewrite path.
- **Attributed `--affirm` on `mint-zet`.** `mint-zet --approve --reviewed-by <actor>
  --affirm <item_id>` (repeatable; accepts only `one_clear_purpose`,
  `sensitive_content_reviewed`) satisfies the two human-review checklist items via an
  audited, reviewer-attributed CLI act instead of a raw `mint.checklist` YAML edit,
  recorded in the receipt's `affirmations` block. It is inert without `--reviewed-by`
  (hard error), cannot override machine-enforced items, and never flips an explicit
  YAML `false`. **Honest residual:** like the pre-existing `--reviewed-by` gate,
  `--affirm` cannot prove the reviewer string names a real human; it adds no new
  self-affirm hole and its guarantee is attribution and auditability, not
  string-sniffing.
- **Retire pointer, no auto-delete.** A successful mint result now points to
  `archive retire-draft --zettel-id <id> --dry-run` via `next_safe_actions` (printed
  in text mode). Mint still never deletes the consumed inbox draft; retirement stays
  its own approval-gated step.
- **Base `continues` edge type.** The base `zettel-kasten/types.yml` (KIT and
  fixture) now defines a `continues` link type for a same-thread continuation.
  **Limitation:** it is base-only and NOT part of the `migrate link-types-v0.3`
  recommended set, so archives that vendored their own `types.yml` add the entry
  manually (it is additive).
- **Draft-time `--kind` validation + `--list-kinds`.** `archive create-draft`
  now warns (does not block) on a `--kind` not in the archive's `zettel-rules.yml`
  and lists the valid kinds; `archive create-draft --list-kinds` lists them read-only
  and writes nothing. See `wom-kit/docs/releases/v0.3.168.md`.

## From `v0.3.166` To `v0.3.167`

This release extends the honest reconcile family (snapshot-drift-aware
classification, a `retire-draft-reconcile` sibling, an opt-in `--strip-bom`),
fixes the object-storage run-outcome `live_execution_allowed_now` field, and adds
a bounded `--multipart-threshold` testing aid. All changes are additive; no
migration is required.

Operator-visible notes:

- No archive migration and no hash change. Two new fields on the mint reconcile
  audit receipt (`classification_basis`, `bom_stripped`), a new `reconcile`
  provenance block on retire receipts, a new `retire-draft-reconcile-receipt.schema.json`,
  and two new fields on the object-storage upload receipt
  (`effective_multipart_threshold_bytes`, `part_count`) are all additive. No schema
  uses `additionalProperties: false`, so existing receipts, manifests, and zets are
  accepted as-is.
- `remint-reconcile` now recognizes a `format_drift` even when the draft snapshot
  itself drifted, but only behind two independent proofs and a full-field frontmatter
  check (an all-fields reconstruction over every content field plus an `id`/`title`
  cross-check against the mint receipt) — so a canonical edit to any content field
  (`visibility`, `kind`, `facets`, …), or a content-tampered snapshot, can never
  anchor `format_drift`. Any uncertainty still classifies `content_change` and
  requires `--content-changed-ack`.
- The reconcile classification test
  `test_remint_reconcile_drifted_snapshot_falls_back_to_content_change` was revised:
  its content subscenarios are unchanged (still `content_change`), and new pure-format
  subcases were added in a sibling test that flip to `format_drift`.
- New CLI-only command `archive retire-draft-reconcile --dry-run|--approve` reconciles
  a retire-draft receipt's four refs; the doctor now routes the
  `mint_retired_draft_sha_mismatch` finding to it via a `suggested_command`.
- New opt-in `--strip-bom` on both reconcile commands removes exactly a leading
  UTF-8 BOM (`format_drift` by definition) and never bypasses the content-change ack
  gate. New `--multipart-threshold BYTES` on `object-storage-upload` is a
  validation/testing aid bounded to `[64 MiB, 5 GiB]`. See
  `wom-kit/docs/releases/v0.3.167.md`.

## From `v0.3.165` To `v0.3.166`

This release makes the object-storage upload key selectable and recorded, adds a
safe `object-storage-adopt-existing` workflow, and hardens the skip rule so an
object stored under an operator's own key layout is never re-uploaded — or, worse,
falsely skipped.

Operator-visible notes:

- No archive migration is required, and no hash change. The default key strategy
  is byte-identical to v0.3.165: the two-field model is additive. Every
  object-storage location and execution receipt now also records a `remote_key`
  (the literal bucket-relative key the object is/was PUT/HEAD at) next to the
  unchanged content-addressed `key_hint`. Existing receipts, manifests, and zets
  are unaffected; the doctor accepts them as-is.
- New opt-in flags on `object-storage-upload`, `object-storage-upload-plan`, and
  `object-storage-upload-verify`: `--key-strategy {sha256_content_addressed,
  prefix}` (default `sha256_content_addressed`), `--key-prefix <literal>` (the raw
  bucket-relative prefix; a colon in an archive-id is a legal key byte), and
  `--key-append-extension` (append the recovered original-filename extension only,
  and only when recoverable — no bare trailing dot otherwise).
- New command `archive object-storage-adopt-existing --dry-run|--approve`. Use it
  BEFORE a first `--approve` upload if your objects already live under your own key
  layout. A verified adopt (with `--approve` + live credentials) HEADs each key
  presence-only and adopts ONLY on presence + Content-Length size-match (NOT a
  content hash — the presence-only HEAD does not download the object body, so
  adopting a large archive costs one HEAD per object, not one download per object;
  add `--content-hash-verify` per object to additionally GetObject-and-rehash). A
  404 / size-mismatch is not adopted, so a wrong `--key-prefix` or extension simply
  re-uploads those objects. A declared adopt (`--accept-unverified-adopt`, a flag
  distinct from `--approve`) records a NON-gating `declared_uploaded` location that
  never skips a PUT. Adopt reports adopted-vs-total so a template miss is visible.
  Verified adopt is a live surface and honours the same tiny-first tiered gate as
  the upload command: a bulk first-live adopt REFUSES with `tiered_gate_unmet`
  until a single tiny-first object (`--only <id>`) has proved the store.
- Idempotency is now HEAD-verified. Under a live transport the executor always
  re-HEADs the recorded `remote_key` before skipping; a recorded key that 404s
  re-uploads. The re-HEAD matches how the location was verified: a presence+size
  adopt is re-checked presence-only (no download), a content-hashed upload keeps its
  checksum re-check. This live proof outranks the resume ledger — once a re-HEAD
  proves an object absent, the re-upload is forced past any stale terminal-success
  ledger row, so a wiped remote is never silently skipped. Plan echoes the resolved
  key and apply refuses (fails closed) on divergence; the plan verdict is
  strategy-aware so it never predicts a skip apply would not honour. See
  `wom-kit/docs/releases/v0.3.166.md`.

## From `v0.3.164` To `v0.3.165`

This release adds a normative Plain-Language for Humans convention to the
operator-facing runtime surfaces and a git/infrastructure terminology
translation layer to the read-only `ai-response-concept-guide`.

Operator-visible notes:

- No archive migration is required, and no hash change. The additions are
  guidance prose (in the `AGENTS.md` templates, the runtime skill, and the
  plugin-layer doc) plus a new read-only `--topic git_infra_terms` set on
  `ai-response-concept-guide`. Existing receipts, manifests, and zets are
  unaffected.
- Guidance, not enforcement. The convention tells an operator AI to translate
  git/infrastructure/WOM-internal jargon into everyday language for humans while
  keeping the exact term in parentheses or logs. WOM does not validate or enforce
  plain-language output; the reading AI applies it. Machine, JSON, and receipt
  output stays exact and unchanged.
- Look up the plain phrasing with `archive ai-response-concept-guide
  <archive-root> --topic git_infra_terms --locale en-US --dry-run --format json`.
  It writes nothing, calls no providers, and echoes no local paths or secret
  values. See `wom-kit/docs/releases/v0.3.165.md`.

## From `v0.3.163` To `v0.3.164`

This release adds Stage 2 of the object-storage upload adapter (WOM #11): a real
AWS SigV4 R2/S3-compatible upload transport. WOM is now network-CAPABLE for an
approved object-storage upload, but capable is not automatic.

Operator-visible notes:

- No archive migration and no hash change. Existing receipts and manifests are
  unaffected until you choose to run an upload command.
- Still no dependency added. The transport is hand-rolled `hashlib`/`hmac`/`base64`
  over the existing `urllib` seam; `wom-kit/pyproject.toml` stays PyYAML-only.
- A live `--approve` upload requires ALL of: env-only credential refs
  (`--access-key-id-ref env:...` and `--secret-access-key-ref env:...`), a safe
  `--reviewed-by`, a resolvable non-secret `--endpoint-host` and `--bucket`
  (region defaults to `auto` for cloudflare-r2), and a met tiered tiny-first gate.
  A bulk first-live run REFUSES with `tiered_gate_unmet` until the single small
  object is proved first. A hard cumulative PUT ceiling bounds cost across the run.
- Validate live tiny-first. Upload ONE small object end-to-end, verify the
  execution receipt + manifest `wom_uploaded` transition + remote after-HEAD by
  hand, then advance tiers. The release note ships the exact runbook. Receipts and
  the release note carry `unproven_against_live_provider: true` until the first
  live object is confirmed. See `wom-kit/docs/releases/v0.3.164.md`.

## From `v0.3.162` To `v0.3.163`

This release adds Stage 1 of the object-storage upload adapter (WOM #11) as three
new approval-gated commands, plus an additive hardening of the shared
object-storage manifest writer.

Operator-visible notes:

- New commands only; nothing runs automatically. `archive
  object-storage-upload-plan --dry-run` and `archive object-storage-upload-verify
  --dry-run` are read-only and write nothing. `archive object-storage-upload`
  requires exactly one of `--dry-run`/`--approve` and a safe `--reviewed-by` with
  `--approve`.
- The adapter CANNOT upload yet. This is Stage 1 of a staged rollout: no live
  transport ships, so `archive object-storage-upload --approve` fails closed with
  `live_transport_not_implemented` before any credential read or byte read. There
  is no env var or flag that reaches a provider; a Stage-2 code change is required.
- No archive migration and no hash change. The manifest-write hardening is
  additive: the shared object-storage manifest writer now holds the manifest lock
  and writes atomically (temp+fsync+os.replace), which also protects the existing
  `object-storage-upload-evidence` command. Existing receipts and manifests are
  unaffected until you choose to run an upload command.
- Added `wom-kit/schemas/object-storage-upload-receipt.schema.json`, a doctor
  check for object-storage execution receipts, and read-only MCP tools
  `object_storage_upload_plan` and `object_storage_upload_verify`. See
  `wom-kit/docs/releases/v0.3.163.md`.

## From `v0.3.161` To `v0.3.162`

This release adds `archive remint-reconcile`, an honest way to re-issue a mint
receipt's recorded sha256 values after a canonical zet drifts on disk. It also
adds additive BOM/newline parse tolerance and a doctor/retire route to the new
command.

Operator-visible notes:

- New command only; nothing runs automatically. `archive remint-reconcile
  <archive-root> (--zettel-id <id> | --path <rel>) [--dry-run | --approve]
  [--reviewed-by <actor>] [--content-changed-ack]` classifies a canonical zet's
  drift as `format_drift` (newline/BOM only) or `content_change`, always shows
  the on-disk content, and requires `--reviewed-by` to approve (a
  `content_change` also requires `--content-changed-ack`). See
  `wom-kit/docs/mint-receipt-reconcile.md`.
- No archive migration and no hash change. BOM/newline tolerance affects
  parse/read helpers only; sha256 still reads raw bytes, so BOM and newline
  drift stay visible as a sha mismatch. Existing receipts and canonical files
  are unaffected until you choose to run `remint-reconcile`.
- STRICT-GATE NOTE (surfacing, not new failures): a canonical zet whose bytes
  already drifted by newline/BOM from its mint receipt was already failing
  `doctor`/`--strict` with `mint_receipt_sha_mismatch`. From v0.3.162 that same
  case carries a suggested `remint-reconcile --dry-run` command, a UTF-8 BOM on
  a canonical zet adds a `zettel_has_bom` WARN, and a previously-reconciled
  receipt that re-drifted by newline/BOM only reports the distinct
  `mint_receipt_target_byte_drift_suspected_format` ERROR. All stay ERRORs; the
  edge-receipt evolution path is unchanged and no gate was relaxed.
- New mints pin the canonical write to LF newlines to prevent immediate
  re-drift. Added `wom-kit/schemas/mint-reconcile-receipt.schema.json` and a
  `reconcile` object property on `mint-receipt.schema.json` (not required;
  legacy receipts validate unchanged). See
  `wom-kit/docs/releases/v0.3.162.md`.

## From `v0.3.159` To `v0.3.160`

This release adds the AI intake protocol (source-intake before any physical
file copy), two objet-store git guards in doctor, the `/objets/` gitignore
safe default, the D2 intake layout ruling, and operator-feedback
discoverability plus schema files.

Operator-visible notes:

- STRICT-GATE IMPACT (deliberate, not merely additive), in two tiers. First,
  EVERY archive created before v0.3.160 — with or without an `objets/`
  folder — now trips the pre-existing `local_profile_gitignore_incomplete`
  warning, because `/objets/` joined the recommended `.gitignore` defaults;
  that alone fails `archive validate` (fails on warnings unless
  `--allow-warnings`) and `archive doctor --strict` until one
  `archive repair-gitignore <archive-root> --approve --reviewed-by <actor>`
  run adds the line. Second, the new doctor warnings
  `archive_objets_layout_noncanonical` (a raw in-root `objets/` folder
  exists) and `workspace_objet_store_git_exposure` (an objet byte store may
  be tracked by an enclosing git working tree) can fail the same gates plus
  `archive runtime-context --strict` for archives that keep originals in an
  in-root `objets/` folder or an exposed store — until the migration guide
  in `wom-kit/docs/artifact-hygiene.md` section 5 is followed. The layout
  warning is intentionally NOT silenced by gitignoring the folder: ignored
  originals silently drop out of the git-push backup path, so the reminder
  stays loud until the folder is emptied through the reviewed capture chain.
- Gitignore additions are additive lines only: `/objets/` (anchored — nested
  `objets/` folders inside staged trees are unaffected) joins the recommended
  defaults; existing archives pick it up with
  `archive repair-gitignore <archive-root> --approve --reviewed-by <actor>`
  (until then the completeness warning fails strict gates, as above).
  Two honest gitignore caveats: it does not untrack already-committed files
  (human-reviewed `git rm --cached` if that happened), and the sibling
  `<root-name>-objets` store is NOT matched by `objets/` — the exposure
  warning names the store's actual directory name, as an anchored
  `/<name>/` line when the store is a direct child of the repository root
  and as an unanchored `<name>/` line when it sits deeper (an anchored
  repo-root line would not match a nested store in git).
- JSON consumers see additive fields only: `staging_convention` gains
  `matched_shape`, `recommended_in_archive_shape`, and
  `in_archive_staging_supports_capture`; `recommended_first_commands` gains a
  fourth (appended) operator-feedback-plan entry; `ai_runtime_order` gains
  step 7 `plan_operator_feedback`; `available_safe_actions` gains
  `run operator-feedback-plan dry-run` INSERTED mid-list next to the other
  read-only dry-run actions (position 3 of 8). Consumers that pinned the FULL
  `ai_runtime_order` list, the exact `recommended_first_commands` length, or
  `available_safe_actions` positions must account for the new entries.
- In-archive staging is now canonical: folders under
  `<archive-root>/staging/incoming/` report
  `follows_staging_convention: true` from project-intake-plan and
  project-intake-unpack-queue instead of `outside_recommended_shape`, and
  project-intake-staging-guide (which takes no staged folder) recommends the
  same in-archive shape for capture intake via the additive
  `recommended_in_archive_shape` / `in_archive_staging_supports_capture`
  fields. The sibling
  `zettel-kasten-<profile_slug>-objets\intake\<project_slug>` shape stays
  accepted for bulk external originals.
- New schema files `wom-kit/schemas/operator-feedback.schema.json` and
  `wom-kit/schemas/operator-feedback-receipt.schema.json` describe the
  UNCHANGED shipped record/receipt shapes; schema-id strings are unchanged
  (`wom-kit/operator-feedback/v0.1`,
  `wom-kit/operator-feedback-receipt/v0.1`). No record migration.
- No archive migration is required. See
  `wom-kit/docs/releases/v0.3.160.md` and
  `wom-kit/docs/artifact-hygiene.md`.

## From `v0.3.158` To `v0.3.159`

This release adds paired transcript intake (one approval covers a staged
original plus its already-extracted transcript) and BOM-aware derive-text
encoding.

Operator-visible notes:

- ADDITIVE manifest field + NEW action string: a selection item MAY carry a
  `derived_text` sub-object (`staged_text_path`, `approved_text_sha256` over
  RAW bytes, `derivation_kind`, `tool_name`, `tool_version`, `review_status`,
  optional model/confidence/language/born_digital). Paired manifests MUST use
  `action: local_objet_capture_with_derived_text_approved` and `schema:
  wom-kit/b4-selection/v0.3`. Kits at v0.3.158 or earlier refuse paired
  manifests with `selection_action_invalid` — fail-closed by design. The
  mechanism matters: the old envelope validator ignores the `schema` field
  (it was write-only) and ignores unknown item keys, so the ACTION string is
  the only lever that makes old kits refuse instead of silently capturing the
  original and dropping the approved derived half. v0.3.159 starts validating
  the `schema` field (`selection_schema_invalid`): plain manifests require
  the v0.2 schema every generated manifest already carries; hand-built
  manifests without a `schema` field must add it.
- utf-8-sig hash-identity change (NOT additive): before this release a UTF-8
  BOM survived validation and the raw bytes were stored WITH the BOM. The BOM
  is now stripped before storage, so the same utf-8-sig input produces a
  different `text_sha256`/`derived_text_id` than a pre-upgrade capture, and a
  post-upgrade re-run of that input creates a SECOND record instead of
  `skip_already_present`. BOM-less UTF-8 input is unaffected (stored bytes ==
  raw bytes).
- Receipt schema bumps: `wom-kit/objet-capture-receipt/v0.2` ->
  `wom-kit/objet-capture-receipt/v0.3` (items may carry a `derived_text`
  sub-result; additive `status_class` at item and run level; derived summary
  counters on paired runs) and `wom-kit/derived-text-capture-receipt/v0.1` ->
  `wom-kit/derived-text-capture-receipt/v0.2` (`source_text_encoding`,
  `source_text_sha256`, and `paired_with` on paired registrations). The
  derived-text RECORD schema stays `wom-kit/derived-text-record/v0.1` with
  additive optional provenance fields.
- New blockers: `approved_text_content_mismatch`, `unsafe_staged_text_path`,
  `blocked_by_original`, `derived_text_registration_failed`,
  `selection_schema_invalid`, `text_file_bom_encoding_unsupported`,
  `text_file_bom_encoding_undecodable`, `text_file_contains_nul`,
  `text_file_too_large`. `text_file_not_utf8` is now raised for BOM-less
  non-UTF-8 input only and gains a static hint. Paired-manifest metadata
  validation reuses the existing derive-text `*_invalid` vocabulary
  (`derivation_kind_invalid`, `review_status_invalid`, `tool_name_invalid`,
  `tool_version_invalid`, `confidence_invalid`, `language_invalid`,
  `born_digital_invalid`) and adds `model_name_invalid` /
  `model_version_invalid` for non-string optional model fields.
- No archive migration is required. See
  `wom-kit/docs/releases/v0.3.159.md` and the Encoding section of
  `wom-kit/docs/derived-text.md`.

## From `v0.3.157` To `v0.3.158`

This release adds owner-approved real-archive objet capture enablement.

Operator-visible notes:

- New CLI command `archive objet-capture-enable <archive-root>` (alias
  `archive capture-enable`): `--dry-run` is a read-only eligibility report;
  `--approve --reviewed-by <actor>` writes a receipt under
  `receipts/capture-enablement/` first and the singleton
  `ops/capture-enablement.yml` consent record second; `--revoke --approve`
  revokes; pattern-matched root names require
  `--acknowledge-never-touch-name`; re-approving over a revoked record
  requires `--reenable`. The command is CLI-only and not exposed via MCP.
- No JSON fields are renamed. `objet-capture` refusals gain one ADDED field,
  `enablement_state`; the `blocked_by` ids are unchanged.
- The hint TEXT of both `objet-capture` refusal hints changed (hints are
  static strings, not a parsing contract). Downstream copies of the
  `"separate planned flow"` substring assertion need the same update.
- Per-item never-touch semantics change for validly-enabled roots only:
  the pattern is evaluated on archive-relative components below the enabled
  root. Non-enabled roots, including all sandbox-marked archives without an
  enablement record, behave exactly as before.
- No archive migration is required. See `wom-kit/docs/capture-enablement.md`
  and `wom-kit/docs/releases/v0.3.158.md`.

## From `v0.3.4` To `v0.3.5`

This release is a compatible field-feedback fast-follow for derived-text
registration and local archive hygiene.

What changed:

- added CLI `archive derive-text capture <archive-root> --from-manifest <jsonl> --dry-run|--approve --reviewed-by <actor>` for batch registration of already extracted UTF-8 derived text,
- batch manifests are JSONL: each line uses `source_object_id`, `text_file`, `derivation_kind`, `tool_name`, `tool_version`, and `review_status`, with optional `item_id`, `model_name`, `model_version`, `confidence`, `language`, and `born_digital`,
- relative `text_file` values resolve from the JSONL manifest location, and archive records do not store the local text file path,
- added CLI `archive repair-gitignore <archive-root> --dry-run|--approve --reviewed-by <actor>` to append missing WOM-kit safe `.gitignore` patterns while preserving existing entries,
- removed private dogfood archive identifiers from public guardrail code and docs while keeping generic live-archive and local `*-objets` protections,
- updated version metadata to `0.3.5`.

No frontmatter or manifest migration is required for v0.3.4 users.

`repair-gitignore` does not delete or rewrite existing `.gitignore` entries,
clean files, inspect source file bodies, upload, sync, or call provider APIs.
`derive-text capture --from-manifest` still does not run OCR, ASR, parsers, LLM
vision, provider APIs, drafting, or minting.

## From `v0.3.3` To `v0.3.4`

This release adds the first derived text capture layer.

What changed:

- added CLI `archive derive-text capture <archive-root> --text-file <file> --source-object-id <object-id> --derivation-kind <kind> --tool-name <name> --tool-version <version> --review-status <status> --dry-run|--approve`,
- added `objects/manifests/derived-text.jsonl` for provenance-aware derived text records,
- approved capture stores UTF-8 text bodies under `objects/derived-text/sha256/` and writes `receipts/derived-text-capture/*.json`,
- `archive index` ingests derived text records and `archive search` can return `type: derived_text`,
- doctor validates derived text JSONL, source object references, vocabulary, and stored text hashes when present.
- updated version metadata to `0.3.4`.

The source object must already exist in `objects/manifests/files.jsonl`.
`derive-text capture` does not run OCR, ASR, parsers, LLM vision, provider APIs,
drafting, or minting. Rebuild the generated search index after approved derived
text capture:

```text
archive index <archive-root>
```

## From `v0.3.2` To `v0.3.3`

This is a compatible field-feedback hardening release.

What changed:

- CLI output is resilient to console encodings that cannot represent every character,
- doctor and validate now fail more clearly on unquoted YAML timestamp frontmatter,
- `validate --strict` is accepted for parity with doctor,
- `staged-cleanup-check` exits `0` only when `safe_to_cleanup` is true; unsafe cleanup reports exit `1`,
- `view-zets` can match scalar facet filters against list-valued zettel facets after re-indexing,
- list-valued view filter inputs block instead of being guessed or broadened,
- objet-capture source-intake plan SHA binding is regression-tested with a real `source-intake --dry-run` producer plan through dry-run and approve,
- updated version metadata to `0.3.3`.

Archives authored under v0.3.2 rules need no schema migration. If you rely on
facet views, rebuild the disposable search index once:

```text
archive index <archive-root>
```

If you automate staged-folder cleanup checks, treat the new nonzero exit on
unsafe reports as expected fail-closed behavior and read the JSON
`safe_to_cleanup` field before any manual cleanup decision.

This release does not touch live archives, providers, ZET transport, MCP write
tools, cleanup targets, or the v0.3.1 frontmatter schema itself.

## From `v0.3.1` To `v0.3.2`

This release ships the frontmatter v0.3 compatibility migration, the local objet
capture spine, and consistent redacted-zettel suppression.

What changed:

- added approval-gated CLI `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run|--approve --format json`,
- added approval-gated CLI `archive objet-capture <archive-root> --selection <manifest> --dry-run|--approve --reviewed-by <actor>` writing content-addressed objets, manifest records, and capture receipts into sandbox-marked archives only,
- added report-only CLI `archive staged-cleanup-check <archive-root> --staged <folder> --dry-run`,
- added read-only CLI `archive related-zets` (typed-edge backlinks) and `archive view-zets` (facet view execution),
- indexed typed edges and zettel facets in the disposable search index,
- enforced redacted-zettel content suppression across search, the index, list-zettels, read-zettel, block-header previews, projection previews, related-zets, and view-zets,
- added the report-only artifact hygiene checker and file-lifecycle baseline,
- updated version metadata to `0.3.2`.

Archives authored under v0.3.1 rules need no frontmatter changes; the v0.3.1
schema is unchanged. Archives authored from older v0.2-draft frontmatter rules
should run:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before strict v0.3 validation, and apply only after reviewing the plan on a
backup or sandbox copy.

Rebuild the local search index once to pick up edges and facets:

```text
archive index <archive-root>
```

The objet-capture write path refuses archives without an explicit sandbox marker
(`.wom-sandbox` file or top-level `environment: sandbox`). This release does not
touch live archives, providers, ZET transport, MCP write tools, or the v0.3.1
schema itself.

## From `v0.3.0` To `v0.3.1`

This is a compatible read-only route-preview release.

What changed:

- added CLI `archive shared-update-route-preview <archive-root> --record <path> --dry-run --format json`,
- added a local service that reuses `zet_shared_update_record_review_preview` before returning any route pointer,
- added route pointer fields for `delegate`, `attest`, `anchor`, and `none`,
- added explicit `related_shared_update_review_required_flags` when the route points toward `shared-update-attestation-review`,
- hardened route selection so free-form or hostile `proposed_action` metadata is not echoed,
- added `wom-kit/docs/shared-update-route-preview.md`,
- updated version metadata to `0.3.1`.

The route-preview command itself requires no provider, transport, or
shared-update record migration. Archives authored from older v0.2-draft
frontmatter rules should run:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before strict v0.3 validation.

The new command is read-only and dry-run only. It writes no files and only points a human toward an existing canonical command surface. It does not expose an MCP write/apply/approve tool and does not create real ZET transport, keys, feed updates, trust/import/acceptance, attestations, signatures, anchors, public proofs, provider sync, projection writes, queues/workers, wallet/key custody, payment/staking/consensus/blockchain, tokens, model training, backpropagation, or full-auto behavior.

## From `v0.2.60` To `v0.3.0`

This is a compatible first v0.3.0 write-boundary release.

What changed:

- added CLI `archive shared-update-attestation-review <archive-root> --record <path> --decision <attest|needs_more_review|reject> --reviewed-by <actor> --approve --format json`,
- added a local service that reuses `zet_shared_update_record_review_preview` before writing,
- added deterministic receiver-side review record and receipt paths,
- added replay/overwrite refusal and receipt-failure rollback,
- added `wom-kit/docs/shared-update-attestation-review-write.md`,
- updated version metadata to `0.3.0`.

The shared-update attestation/review command itself requires no provider,
transport, or shared-update record migration. Archives authored from older
v0.2-draft frontmatter rules should run:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before strict v0.3 validation.

The new command writes only a local shared update attestation/review record and matching receipt. It does not expose an MCP write/apply tool and does not create real ZET transport, keys, feed updates, trust/import/acceptance, signatures, anchors, public proofs, provider sync, projection writes, queues/workers, wallet/key custody, payment/staking/consensus/blockchain, tokens, model training, backpropagation, or full-auto behavior.

## From `v0.2.59` To `v0.2.60`

This is a compatible documentation, version, and test checkpoint for the v0.2.x freeze and v0.3.0 entry boundary.

What changed:

- added `wom-kit/docs/v02x-freeze-v03-entry-boundary.md`,
- added the v0.2.60 release note and public-safe work log,
- updated the capability matrix with the v0.2.x freeze, public proof boundary, DID-compatible identity research boundary, and proposed first v0.3.0 write boundary,
- updated version metadata to `0.2.60`.

No private archive migration is required.

This release adds no product CLI command, MCP tool, archive service behavior, or schema change. It records that the proposed v0.3.0 first boundary should be one narrow receiver-side, replay-gated, human-approved, local-first, body-safe write. It does not add real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, feed updates, trust/import/acceptance/anchor mutation, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, queues/workers, DID registry, wallet/key custody, public proof anchoring, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.58` To `v0.2.59`

This is a compatible read-only ZET transport threat model and would-transport planning patch.

What changed:

- added CLI `archive zet-transport-plan <archive-root> --record <path> --method <key-sharing|radio-frequency|mirroring> --dry-run --format json`,
- added MCP `zet_transport_would_plan`,
- added service `zet_transport_would_plan`,
- added `wom-kit/docs/zet-transport-threat-model.md`,
- updated version metadata to `0.2.59`.

No private archive migration is required.

The new command reads one local archive-contained shared update record JSON, reuses the v0.2.56 single-record review preview policy, writes nothing, and returns a planning-only risk/control preview for a future transport method. It does not add real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, shared-update review writes, receiver-side renewal writes, neighbor feed update, recommendation execution, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, queues/workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.57` To `v0.2.58`

This is a compatible read-only shared update review index patch.

What changed:

- added CLI `archive shared-update-record-review-index <archive-root> --records-dir <path> --dry-run --format json`,
- added MCP `zet_shared_update_record_review_index`,
- added `wom-kit/docs/zet-shared-update-record-review-index.md`,
- updated version metadata to `0.2.58`.

No private archive migration is required.

The new command inspects only direct-child local JSON records under an archive-relative directory, reuses the v0.2.56 single-record review policy, writes nothing, and returns a compact deterministic index. It does not add shared-update review writes, shared-update transport, real ZET transport, neighbor feed update, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.56` To `v0.2.57`

This is a compatible capability matrix and README readability patch.

What changed:

- added `wom-kit/docs/capability-matrix.md`,
- shortened the top-level README status summary and linked to the capability matrix,
- restored the missing `v0.2.55` README release-tag entry,
- documented a proposed v0.2.x closing plan and narrow proposed v0.3.0 boundary,
- updated version metadata to `0.2.57`.

No private archive migration is required.

This release adds no archive product CLI, MCP, or service behavior. It does not add provider calls, real ZET transport, shared-update writes, receiver-side renewal writes, RF access, key-sharing registry, mirroring delivery, neighbor feed update, automatic feed renewal, recommendation execution, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.55` To `v0.2.56`

This is a compatible read-only ZET shared update record review preview patch.

What changed:

- added CLI `archive shared-update-record-review <archive-root> --record <path> --dry-run --format json`,
- added MCP `zet_shared_update_record_review_preview`,
- added `wom-kit/docs/zet-shared-update-record-review-preview.md`,
- updated version metadata to `0.2.56`.

No private archive migration is required.

The new command reads only one archive-relative JSON record and writes nothing. It blocks unsafe record paths, body-included records, token/secret-like values, local absolute path leakage, and true mutation/write/transport/provider/trust flags. It does not add shared-update transport, real ZET transport, neighbor feed update, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.54` To `v0.2.55`

This is a compatible ZET shared update record baseline documentation/example patch.

What changed:

- added `wom-kit/docs/zet-shared-update-record-baseline.md`,
- added a sanitized non-executable example at `wom-kit/examples/zet-shared-update-record/shared-update.example.json`,
- updated version metadata to `0.2.55`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not add shared-update transport, real ZET transport, RF access, key-sharing registry, mirroring delivery, neighbor feed update, automatic feed renewal, recommendation execution, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.53` To `v0.2.54`

This is a compatible main branch protection readiness documentation patch.

What changed:

- added `wom-kit/docs/main-branch-protection-readiness.md`,
- documented a staged path from local release gate to future GitHub Actions, required status checks, and optional review requirements,
- updated version metadata to `0.2.54`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not add GitHub Actions, enable branch protection, change repository settings, call GitHub APIs, call providers, edit GitHub Releases, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.52` To `v0.2.53`

This is a compatible release readiness gate patch.

What changed:

- added `wom-kit/tools/check_release_readiness.py`,
- added tests for expected child checker paths, pass/fail behavior, failure output, current-repository pass behavior, and network-free / release-edit-free gate scope,
- documented the gate at `wom-kit/docs/release-readiness-gate.md`,
- updated version metadata to `0.2.53`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. The gate is local-only and read-only. It runs the public link, Korean product-language, and public privacy hygiene checkers only. It does not rewrite files, fetch external URLs, call GitHub APIs, add GitHub Actions, enable branch protection, run product doctors/tests, call providers, edit GitHub Releases, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.51` To `v0.2.52`

This is a compatible public privacy hygiene checker patch.

What changed:

- added `wom-kit/tools/check_public_privacy.py`,
- added tests for local user-home paths, token-like strings, private key headers, seed-phrase-like text, private/local endpoint examples, placeholders, and network-free checker scope,
- documented the checker at `wom-kit/docs/public-privacy-hygiene.md`,
- updated version metadata to `0.2.52`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. The checker is local-only and read-only. It does not rewrite files, fetch external URLs, call providers, inspect private archives, edit GitHub Releases, scan the whole disk, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.50` To `v0.2.51`

This is a compatible Korean product-language hygiene checker patch.

What changed:

- added `wom-kit/tools/check_korean_product_language.py`,
- added tests for required baseline anchors and high-risk wording drift,
- documented the checker at `wom-kit/docs/korean-product-language-hygiene.md`,
- updated version metadata to `0.2.51`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. The checker is local-only and read-only. It does not rewrite files, rename implementation identifiers, fetch external URLs, call providers, edit GitHub Releases, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.49` To `v0.2.50`

This is a compatible Korean product-language baseline patch.

What changed:

- added `wom-kit/docs/concepts/korean-product-language-baseline.ko.md`,
- documented Korean explanation terms for WOM, zettel-kasten, zet, ZET, objet, lifecycle verbs, block/header/body wording, foreign block safety terms, sharing forms/methods, surface/action terms, SNS-type ZET actions, and messenger-type ZET threads,
- linked the new baseline from README files and public documentation maps,
- updated version metadata to `0.2.50`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not rename CLI commands, JSON fields, schema fields, filenames, or implementation identifiers. It does not implement real ZET transport, real trust/import/acceptance/anchor, attestation/signature writes, RF access, key-sharing registry, mirroring delivery, provider sync, WordPress publishing, projection writes or receipts, recommendation fetching/ranking/feed updates, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.48` To `v0.2.49`

This is a compatible public release link hygiene patch.

What changed:

- added `wom-kit/tools/check_public_links.py`,
- added tests for repo-local Markdown link resolution and GitHub Release body link hygiene,
- documented the difference between repo-local Markdown links and GitHub Release body links,
- converted known unsafe release-note relative file links to absolute GitHub `blob` URLs.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not edit GitHub Releases, fetch external URLs, call providers, publish to WordPress, write projection records or receipts, run ZET transport, fetch or rank recommendations, update neighbor feeds, create trust/import/acceptance/attestation/signature/minting changes, add background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.47` To `v0.2.48`

This is a compatible ZET radio-frequency recommendation model baseline patch.

What changed:

- documented the distinction between followed/neighbor feeds and recommended/broadcast feeds,
- documented the radio-frequency metaphor for user/node-selected ZET channels, scopes, or broadcast lanes,
- documented prompt-as-algorithm selectors as inspectable policy/rule/config/code bundles rather than only LLM prompts,
- added a sanitized non-executable selector example.

No private archive migration is required.

This release adds no CLI or MCP behavior. It does not fetch recommendations, rank feeds, update neighbor feeds, call providers, publish to WordPress, write projection records or receipts, run real ZET transport, create trust/import/acceptance/attestation/signature/minting changes, add Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.46` To `v0.2.47`

This is a compatible ZET closed sharing model baseline patch.

What changed:

- documented the base zettel-kasten layer as GitHub-tracked records, object storage, and DB relationships,
- documented the unit layer distinction between `zet` and `objet`,
- documented the future ZET closed sharing/SNS layer above the base system,
- clarified that GitHub is not the whole ZET sharing architecture,
- clarified that WordPress is one possible user-selected projection surface, not the WOM/ZET UI,
- added sanitized non-executable closed sharing examples.

No private archive migration is required.

This release adds no CLI or MCP behavior. It does not call providers, publish to WordPress, write projection records or projection receipts, implement real ZET transport, automatically update neighbor feeds, mint, trust, import, accept, attest, sign, anchor, apply, introduce Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.45` To `v0.2.46`

This is a compatible ZET projection plan dry-run preview patch.

What changed:

- added `archive projection-plan <archive-root> --zet <zet-id-or-path> --surface <surface-kind> --dry-run --format json`,
- added read-only MCP `zet_projection_plan_check`,
- added metadata-only planning output for one local zet and one operator-declared surface kind,
- added closed safety flags for provider calls, WordPress publishing, projection writes, projection receipts, trust/import/acceptance, attestation, signature, minting, ZET transport, and full-auto behavior.

No private archive migration is required.

The preview reads one local archive zet only enough to confirm existence and extract safe metadata. It does not output the full zet body, write files, create receipts, call providers, publish to WordPress, mint, trust, import, accept, attest, sign, anchor, apply, or run ZET transport.

## From `v0.2.44` To `v0.2.45`

This is a compatible ZET publication surface baseline patch.

What changed:

- added documentation for the no-UI WOM core and user-selected publication/projection surfaces,
- added sanitized example files for a future projection envelope, WordPress-like title, and WOM Safe HTML-compatible post body,
- clarified that posting is not minting,
- clarified that a surface locator is not the canonical zet identity.

No private archive migration is required.

This release adds no CLI or MCP behavior. It does not call providers, publish to WordPress, implement projection-plan CLI/MCP, create projection receipts, trust, import, accept, attest, sign, mint, anchor, run ZET transport, add payments, staking, consensus, blockchain, Redis, model training, backpropagation, or full-auto behavior.

## From `v0.2.43` To `v0.2.44`

This is a compatible foreign block attestation statement draft decision preview patch.

What changed:

- added `archive attestation-statement-draft-decision <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--decision-intent`, `--reviewer`, `--expected-review-scope`, `--expected-statement-style`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_statement_draft_decision_preview`,
- added route previews for keeping a draft under review, revising it, rejecting it later, preparing a future explicit attestation statement review, or requesting more review.

No private archive migration is required.

The preview revalidates the current statement draft review index, statement draft record/receipt, candidate record/receipt, quarantine case/receipt, and decision record/receipt. It writes nothing and records no decision. Review notes are local preview context only; raw note bodies are not echoed or stored. Statement drafts remain untrusted and do not create trust, import, acceptance, attestation, signature, mint, receipt write, WordPress publishing, provider calls, sharing, or ZET transport.

## From `v0.2.42` To `v0.2.43`

This is a compatible foreign block attestation statement draft review index patch.

What changed:

- added `archive attestation-statement-draft-review <archive-root> --format json`,
- added optional `--case-id`, `--statement-style`, `--review-scope`, and `--include-receipts` filters,
- added read-only MCP `foreign_block_attestation_statement_draft_review_index`,
- added consistency checks for recorded statement draft records, statement draft receipts, current candidate records/receipts, quarantine cases/receipts, and decision records/receipts.

No private archive migration is required.

The review index writes nothing, keeps `dry_run: true`, and returns `would_change: []`. `--statement-style` and `--review-scope` filter displayed records only; they do not hide blockers from other discovered records. `--case-id` intentionally scopes the verdict to that one case. Indexed statement drafts remain untrusted and do not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.41` To `v0.2.42`

This is a compatible foreign block attestation statement draft write approval patch.

What changed:

- added `archive record-attestation-statement-draft <archive-root> --draft-preview <json-file> --dry-run --format json`,
- added CLI-only `--approve --reviewed-by <safe-actor-id>` to record the statement draft and matching receipt,
- added read-only MCP `record_attestation_statement_draft_check`,
- added stale/tamper checks that revalidate the current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt before writing.

No private archive migration is required.

Dry-run writes nothing. Approved mode writes exactly two local files and keeps the foreign block untrusted. It does not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.40` To `v0.2.41`

This is a compatible foreign block attestation statement draft preview patch.

What changed:

- added `archive attestation-statement-draft <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-review-scope`, `--prospective-attestor`, `--statement-style`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_statement_draft_preview`,
- added non-binding statement draft output for one recorded attestation review candidate.

No private archive migration is required.

The preview re-reads current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt state before returning a draft. It writes nothing and does not create trust, import, attestation, signature, mint, receipt, sharing, provider calls, or ZET transport.

## From `v0.2.39` To `v0.2.40`

This is a compatible foreign block attestation review candidate index patch.

What changed:

- added `archive attestation-candidate-review <archive-root> --format json`,
- added optional `--case-id`, `--review-scope`, and `--include-receipts` filters,
- added read-only MCP `foreign_block_attestation_review_candidate_index`,
- added consistency checks for recorded candidate records, candidate receipts, current quarantine cases, original quarantine receipts, recorded decisions, and decision receipts.

No private archive migration is required.

The review index writes nothing, keeps `dry_run: true`, and returns `would_change: []`. Filters only affect displayed candidates; all discovered records are still validated before top-level `ok` is set. Indexed candidates remain untrusted and do not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.38` To `v0.2.39`

This is a compatible foreign block attestation review candidate write approval patch.

What changed:

- added `archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --dry-run --format json`,
- added CLI-only `--approve --reviewed-by <actor-id>` for recording an untrusted candidate record and receipt,
- added optional `--expected-case-id`, `--expected-review-scope`, `--expected-attestor`, and `--review-note`,
- added read-only MCP `record_attestation_review_candidate_check`.

No private archive migration is required.

Dry-run writes nothing. Approved CLI mode writes exactly two archive-relative files: one candidate record and one receipt. The candidate remains untrusted and does not create an attestation, signature, import, mint, share, provider call, ZET transport, or acceptance.

## From `v0.2.37` To `v0.2.38`

This is a compatible foreign block attestation review candidate planning patch.

What changed:

- added `archive attestation-review-candidate <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-decision`, `--expected-outcome`, `--prospective-attestor`, `--review-scope`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_review_candidate_plan`,
- added a safe candidate packet for human review when the recorded decision is `eligible_for_attestation_review`.

No private archive migration is required.

The candidate planner reads only sanitized quarantine case, quarantine receipt, decision record, and decision receipt metadata. It writes nothing and does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, share it, call providers, or run ZET transport.

`prepare_attestation_review_candidate` is still not an attestation. It only means a human can review a candidate packet before any future explicit attestation workflow exists.

## From `v0.2.36` To `v0.2.37`

This is a compatible foreign block decision outcome planning patch.

What changed:

- added `archive quarantine-decision-outcome <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-decision`, `--reviewer`, and `--review-note`,
- added read-only MCP `foreign_block_decision_outcome_plan`,
- added conservative next-step routing for recorded decisions.

No private archive migration is required.

The outcome planner reads only the current quarantine case, original quarantine receipt, recorded quarantine decision, and decision receipt. It writes nothing and does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, share it, or call providers.

`eligible_for_attestation_review` is still not trust. It only maps to `prepare_attestation_review_candidate` for a future explicit workflow.

## From `v0.2.35` To `v0.2.36`

This is a compatible foreign block quarantine decision review index patch.

What changed:

- added `archive quarantine-decision-review <archive-root> --format json`,
- added optional `--case-id`, `--decision`, and `--include-receipts`,
- added read-only MCP `foreign_block_quarantine_decision_review_index`,
- added consistency checks for recorded quarantine decision records and matching decision receipts.

No private archive migration is required.

The review index reads only quarantine cases, original quarantine receipts, recorded quarantine decision JSON, and matching decision receipts. It writes nothing and does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, share it, or call providers.

## From `v0.2.34` To `v0.2.35`

This is a compatible foreign block quarantine decision write approval patch.

What changed:

- added `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --dry-run --format json`,
- added `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --approve --reviewed-by <actor-id> --format json`,
- added optional `--expected-case-id`, `--expected-decision`, and `--review-note`,
- added read-only MCP `record_quarantine_decision_check`,
- added replay validation that re-reads the current quarantine case and matching quarantine write receipt before any approved local decision record write.

No private archive migration is required.

The approved write creates exactly two local files:

```text
quarantine/foreign-blocks/<case-id>/quarantine-decision.json
receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json
```

This records an operator-reviewed quarantine decision only. It does not trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, execute it, accept it, apply it, share it, or call providers.

MCP remains read-only for this workflow. Real quarantine decision recording is CLI-only and requires `--approve --reviewed-by`.

## From `v0.2.33` To `v0.2.34`

This is a compatible foreign block quarantine decision preview patch.

What changed:

- added `archive quarantine-decision <archive-root> --case-id <safe-id> --dry-run --format json`,
- added optional `--decision-intent`, `--reviewer`, and `--review-note` preview context,
- added read-only MCP `foreign_block_quarantine_decision_check`,
- added a decision aid for existing untrusted quarantine cases.

No private archive migration is required.

Quarantine decision preview reads one existing quarantine case and matching receipt. It does not write a decision, record approval, trust the foreign block, import it, attest it, mint it, anchor it, delegate it, sign it, accept it, apply it, or call providers.

The preview may propose:

- `keep_quarantined`,
- `reject_and_keep_record`,
- `eligible_for_attestation_review`,
- `needs_more_review`.

`eligible_for_attestation_review` is still not trust. It only means a future explicit attestation review path may be appropriate.

## From `v0.2.32` To `v0.2.33`

This is a compatible foreign block quarantine review index patch.

What changed:

- added `archive quarantine-review <archive-root> --format json`,
- added optional `--case-id`, `--status`, and `--include-receipts`,
- added read-only MCP `foreign_block_quarantine_review_index`,
- added read-only inventory and consistency checks for existing untrusted quarantine cases and matching quarantine write receipts.

No private archive migration is required.

Quarantine review index reads existing files only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Indexing a case does not mean the case is trusted, imported, accepted, attested, minted, anchored, delegated, signed, or safe to apply. It only gives a reviewer a stable list of untrusted quarantine cases and obvious consistency blockers/warnings.

## From `v0.2.31` To `v0.2.32`

This is a compatible foreign block quarantine write approval patch.

What changed:

- added `archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json`,
- added `archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json`,
- added read-only MCP `quarantine_foreign_block_check`,
- added a CLI-only approved local write for sanitized foreign block quarantine cases and quarantine write receipts.

No private archive migration is required.

Approved quarantine writes create only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Quarantine write is an isolation record. It does not make a foreign block canonical, trusted, imported, minted, attested, anchored, delegated, signed, executable, or accepted. MCP remains check-only for this workflow.

## From `v0.2.30` To `v0.2.31`

This is a compatible foreign block quarantine plan patch.

What changed:

- added `archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json`,
- added `archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_quarantine_plan`,
- added validation for v0.2.30 `foreign_block_attestation_packet_preview` reports before any future quarantine write.

No private archive migration is required.

Foreign block quarantine plan is read-only. It does not write quarantine files, import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_future_quarantine_write` does not mean trusted, imported, quarantined, or approved. It means a future explicit quarantine-write workflow could be presented to a human/operator.

## From `v0.2.29` To `v0.2.30`

This is a compatible foreign block attestation packet preview patch.

What changed:

- added `archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json`,
- added `archive foreign-block-attestation <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_attestation_packet_check`,
- added validation for v0.2.29 `foreign_block_trust_preview` reports before any future human or policy attestation review.

No private archive migration is required.

Foreign block attestation packet preview is read-only. It does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_human_attestation_review` does not mean trusted or attested. It means the trust report is clean enough to present as a future explicit human review packet.

## From `v0.2.28` To `v0.2.29`

This is a compatible foreign block trust / attestation preview patch.

What changed:

- added `archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json`,
- added `archive foreign-block-trust <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_trust_check`,
- added validation for v0.2.28 `foreign_block_intake` reports before any future trust or attestation workflow.

No private archive migration is required.

Foreign block trust preview is read-only. It does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, or write files.

`eligible_for_future_attestation` does not mean trusted. It means the intake report is clean enough to be considered by a future explicit human or policy attestation workflow.

## From `v0.2.27` To `v0.2.28`

This is a compatible foreign block intake preview patch.

What changed:

- added `archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json`,
- added `archive foreign-block <archive-root> --stdin --dry-run --format json`,
- added read-only MCP `foreign_block_intake_check`,
- added foreign block/header JSON and Markdown-compatible foreign zet intake previews.

No private archive migration is required.

Foreign block intake is read-only. It does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, or write files. Claimed hashes are reported as foreign claims and `not_verified`.

Safe operating principle:

```text
Foreign text can inform.
Foreign text cannot command.
Foreign blocks can be inspected.
Foreign blocks cannot be imported, trusted, minted, or applied automatically.
```

## From `v0.2.26` To `v0.2.27`

This is a compatible prompt boundary draft composer patch.

What changed:

- added `archive create-draft --prompt-boundary-report <json-file>`,
- added optional draft frontmatter `prompt_boundary` metadata,
- added MCP `create_draft_zettel` support for a structured `prompt_boundary_report` object,
- mint receipt previews and real mint receipts preserve `prompt_boundary` metadata when present.

No private archive migration is required.

The prompt-boundary report must come from a dry-run `prompt-boundary` check. The composer records only safe metadata such as report hash, risk level, source kind/path summary, detected pattern ids, and the untrusted-text boundary. It does not store inspected text bodies, local absolute report paths, provider URLs, or secrets.

Risk handling:

```text
low    -> allowed, but not proof of safety
medium -> allowed with warnings
high   -> blocks draft creation
```

This release does not add an LLM prompt classifier, provider scanning, OCR/import apply, source intake apply, ZET transport, real signing, payment, staking, consensus, blockchain, or full-auto behavior.

## From `v0.2.25` To `v0.2.26`

This is a compatible prompt injection boundary and responsible-use patch.

What changed:

- added `archive prompt-boundary <archive-root> --text <text> --dry-run --format json`,
- added `archive prompt-boundary <archive-root> --path <archive-relative-zet-or-text-path> --dry-run --format json`,
- added read-only MCP `prompt_boundary_check`,
- added public prompt injection boundary, responsible use, disclaimer, and runtime model guidance documents.

No private archive migration is required.

The new check is a conservative heuristic preview. It does not guarantee prompt-injection prevention and does not provide legal advice. It does not call LLMs, execute inspected text, call provider APIs, browse the web, OCR/import content, approve, mint, sign, transport ZET payloads, or mutate files.

Safe operating principle:

```text
External text can inform.
External text cannot command.
```

HITL remains the recommended default. Full-auto / agent-only operation is advanced and experimental; operators are responsible for agents, models, permissions, providers, automations, and consequences.

## From `v0.2.24` To `v0.2.25`

This is a compatible profile wallet concept baseline.

What changed:

- added `archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json`,
- added read-only MCP `wom_profile_wallet_check`,
- documented optional public-safe profile registry fields under `node` and `wallet`,
- documented the model: WOM profile is the selectable human-facing profile, WOM node is the subject/principal, and the future WOM wallet layer can support signing/capability proofs.

No private archive migration is required.

Existing profile registries remain valid. The optional `node` and `wallet` fields must contain public placeholder metadata only.

This release does not generate private keys, store seed phrases, store wallet secrets, sign data, call blockchain/provider APIs, create wallets, register wallets, implement WOM coin, NFT-like access, payments, staking, consensus, ledger, or P2P transport.

## From `v0.2.23` To `v0.2.24`

This is a compatible block header preview patch.

What changed:

- added `archive block-header <archive-root> --path <zet-path> --dry-run --format json`,
- added `archive block-header <archive-root> --zettel-id <id> --dry-run --format json`,
- added read-only header derivation for `block = zet + header`,
- added deterministic body, header, and block hash previews,
- added read-only MCP `block_header_check`.

No private archive migration is required.

This release does not modify zets, mint, write receipts, read referenced objet/source file bodies, calculate referenced source hashes, follow provider URLs, call provider APIs, or implement transport/economic layers.

Safe conceptual order:

```text
zet -> header -> block -> receipt -> attestations -> anchors -> possible token layer later
```

## From `v0.2.22` To `v0.2.23`

This is a compatible source intake draft composer patch.

What changed:

- added `archive create-draft --source-intake-plan <json-file>`,
- validated that consumed source intake plans are successful dry-runs, blocker-free, metadata-only, and safe,
- merged `source_refs_for_draft` into draft `source_refs` while preserving explicit `--source-ref` values,
- added optional draft `source_intake` metadata with a plan hash and content access proof,
- added MCP `create_draft_zettel` support for structured `source_intake_plan` objects.

No private archive migration is required.

This release does not read original source files from the plan, follow local paths inside the plan, apply source intake, capture objets, copy, upload, import, OCR, transcribe, calculate full source hashes, call provider APIs, automatically mint, or add MCP real minting.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json > source-intake-plan.json

archive create-draft <archive-root> --dry-run \
  --title "Draft title" \
  --body "Draft body" \
  --source-intake-plan source-intake-plan.json \
  --format json
```

## From `v0.2.21` To `v0.2.22`

This is a compatible source intake planner patch.

What changed:

- added `archive source-intake <archive-root> --dry-run --format json`,
- added metadata-only locator planning for local files, source map items, source-relative paths, manifested objets, provider refs, and AI artifacts,
- added draft-ready `source_refs_for_draft` so AI runtimes can feed safe refs into `create-draft --dry-run`,
- added object storage context reporting from `provider-bindings.yml`,
- added read-only MCP `source_intake_plan`.

No private archive migration is required.

This release does not read file bodies, calculate full hashes, copy, upload, import, OCR, transcribe, extract, call provider APIs, create drafts automatically, mint, or sync providers.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json
```

## From `v0.2.20` To `v0.2.21`

This is a compatible object storage/objet setup planner patch.

What changed:

- added `archive object-storage <archive-root> --dry-run --format json`,
- added safe default bucket/container naming as `zettel-kasten-<normalized-profile-slug>-objets`,
- added default objet prefix planning as `archives/<archive_id>/objets/`,
- added strict safety gates for provider kind, profile slug, bucket/container name, region, endpoint reference, and storage account reference,
- added `--approve --reviewed-by` for local-only provider metadata and setup receipt writes,
- added optional ignored local object storage account hints with `--write-local-profile`,
- added read-only MCP `object_storage_setup_plan`.

No private archive migration is required.

This release does not create buckets, run OAuth, call provider APIs, upload, sync, copy source files, hash files, or import source content.

```bash
archive object-storage <archive-root> --dry-run \
  --provider cloudflare-r2 \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --storage-account-ref storage:account:honggildong \
  --format json
```

## From `v0.2.19` To `v0.2.20`

This is a compatible GitHub profile repository setup planner patch.

What changed:

- added `archive github-repo <archive-root> --dry-run --format json`,
- added safe default repository names as `zettel-kasten-<profile_slug>`,
- added strict safety gates for profile slugs, repository names, GitHub owners, and account references,
- added `--approve --reviewed-by` for local-only provider metadata and setup receipt writes,
- added optional ignored local account hints with `--write-local-profile`,
- added read-only MCP `github_repository_setup_plan`.

No private archive migration is required.

This release does not create GitHub repositories, run OAuth, call GitHub APIs, run `gh`, configure git remotes, push, or sync.

```bash
archive github-repo <archive-root> --dry-run \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --github-owner example-user \
  --github-account-ref github:account:honggildong \
  --format json
```

## From `v0.2.18` To `v0.2.19`

This is a compatible WOM-kit naming and path cleanup patch.

What changed:

- the implementation folder is now `wom-kit/`,
- the Python import package is now `wom_kit`,
- package metadata now uses the project name `wom-kit`,
- `archive` and `archive-mcp` remain available as compatibility console scripts,
- preferred aliases `wom` and `wom-mcp` are available when installed from the package metadata.

No private archive migration is required.

Current commands should use the new paths:

```bash
python wom-kit/cli/archive.py doctor wom-kit/examples/fake-life-archive --strict
python -m wom_kit.archive_cli doctor wom-kit/examples/fake-life-archive --strict
```

## From `v0.2.17` To `v0.2.18`

This is a compatible profile-aware draft zet creation dry-run patch.

What changed:

- added `archive create-draft --dry-run --format json`,
- added replay-safe draft creation fields for draft id, created-at timestamp, expected body hash, and draft approver,
- added profile-aware provenance fields for resolved profile id, operator id, authority mode, source refs, local AI sessions, assisting actors, and supervising actors,
- extended MCP `create_draft_zettel` with the same dry-run and profile-aware inputs,
- kept real draft writes constrained to `inbox/`,
- kept minting separate through `mint-zet --approve --reviewed-by`.

No private archive migration is required. Existing drafts remain valid.

For profile-bound AI writes, first run profile resolution and runtime context, then dry-run draft creation. After human draft approval, replay the same draft id, created-at timestamp, expected archive id/type, profile id, and expected body hash.

```bash
git fetch --tags
git checkout v0.2.18
```

## From `v0.2.16` To `v0.2.17`

This is a compatible WOM Profile Registry dry-run patch.

What changed:

- added `archive profile-list --registry <path> --format json`,
- added `archive profile-resolve --registry <path> --target <query> --format json`,
- added read-only MCP tools `wom_profile_list` and `wom_profile_resolve`,
- added token-state aware profile resolution before runtime context and draft work,
- added an example registry template at `wom-kit/templates/profiles/wom-profiles.example.yml`.

No private archive migration is required.

This release does not add profile registration, token storage, create-draft dry-run, provider API sync, UI, real minting through MCP, or any MCP write/register/apply tool.

```bash
git fetch --tags
git checkout v0.2.17
```

## From `v0.2.15` To `v0.2.16`

This is a compatible WOM AI Runtime Context Layer patch.

What changed:

- added `archive runtime-context <archive-root> --format json`,
- added `--expected-archive-id`, `--expected-type`, and `--strict` checks so terminal-capable AI runtimes can confirm they are operating on the intended archive before creating drafts, running dry-runs, or asking for mint approval,
- added default local path redaction; JSON paths are archive-relative unless `--no-redact-local-paths` is explicitly used for trusted local debugging,
- added read-only MCP tool `archive_runtime_context` with existing MCP allowed-root enforcement.

No private archive migration is required.

This release does not add create-draft dry-run, provider API sync, UI, real minting through MCP, or any MCP apply tool.

```bash
git fetch --tags
git checkout v0.2.16
```

## From `v0.2.14` To `v0.2.15`

This is a compatible WOM Safe HTML Profile validator dry-run patch.

What changed:

- added `archive check-safe-html --path <zet> --dry-run` as a read-only CLI command that previews whether a v0.2 Markdown-compatible zet is compatible with a future WOM Safe HTML Profile migration,
- the validator blocks zet bodies that contain `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URLs, or inline event handler attributes such as `onclick=`,
- the validator returns structured JSON with `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, and `source_reference_preview`.

No private archive migration is required.

This release does not add a Markdown-to-HTML converter, a profile allowlist, a UI, live sharing, P2P transport, or external provider sync. Existing Markdown-compatible zets remain valid.

```bash
git fetch --tags
git checkout v0.2.15
```

## From `v0.2.13` To `v0.2.14`

This is a compatible documentation/spec baseline patch for the WOM Safe HTML Profile.

What changed:

- documented the distinction between `WOM`, `zet`, and `ZET`,
- clarified that `zet` is the unit document minted inside a zettel-kasten,
- clarified that `ZET` is the future communication layer that can become messenger, SNS/feed, or collaboration,
- documented WOM Safe HTML Profile as the long-term canonical/interchange/rendering target,
- kept Markdown as the v0.2 authoring/import compatibility format.

No private archive migration is required.

This release does not add a Markdown-to-HTML converter, profile validator, UI, live sharing, P2P transport, or external provider sync.

```bash
git fetch --tags
git checkout v0.2.14
```

## From `v0.2.12` To `v0.2.13`

This is a compatible WOM naming baseline and CLI alias patch.

What changed:

- documented `WOM` as the umbrella name and `Widesider of Modernity` as its expansion,
- added `archive mint-zet` as the preferred command name for minting a zet,
- kept `archive mint-zettel` as a compatibility alias,
- added `archive parcel` as the preferred command name for creating a bounded portable unit,
- kept `archive pack` as a compatibility alias,
- added `archive admit --dry-run` as the preferred command name for previewing parcel/workpack admission,
- kept `archive import --dry-run` as a compatibility alias.

No private archive migration is required.

Existing scripts can keep using the old names, but new user-facing docs should prefer `mint-zet`, `parcel`, and `admit`.

```bash
git fetch --tags
git checkout v0.2.13
```

## From `v0.2.11` To `v0.2.12`

This is a compatible real delegate receipt write patch.

What changed:

- added `archive delegate-zet --approve --reviewed-by <actor>`,
- real delegate writes create `receipts/delegate/*.delegate.json`,
- `archive doctor` validates applied delegate receipts,
- real delegate capability receipts get a generated nonce,
- claim/spent/revocation registries remain explicitly unimplemented.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.12
```

## From `v0.2.10` To `v0.2.11`

This is a compatible delegate capability contract patch.

What changed:

- added `--target-policy counterparty_bound|claimable_once` to `archive delegate-zet --dry-run`,
- made `--target-archive` optional for `claimable_once` delegate previews,
- added `delegation_capability`, `claim_binding`, and `settlement_condition` preview fields,
- kept settlement non-financial with `mode: "none"`,
- kept real P2P, claim registry, spent registry, revocation, blockchain, and payment unavailable.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.11
```

## From `v0.2.9` To `v0.2.10`

This is a compatible dry-run lifecycle feature patch.

What changed:

- added `archive delegate-zet --dry-run`,
- added `archive attest-zet --dry-run`,
- added `archive anchor-zet --dry-run`,
- added read-only MCP checks for delegate, attest, and anchor,
- added schemas for delegate receipts, attestation receipts, and anchor metadata.

No private archive migration is required.

Real P2P, feed, transport, external sending, and foreign zet import remain unavailable.

```bash
git fetch --tags
git checkout v0.2.10
```

## From `v0.2.8` To `v0.2.9`

This is a compatible terminology stabilization patch.

What changed:

- new archives default to `human_minting`,
- existing `human_promotion` archives remain valid,
- `minting_rules` may be used in zettel rules,
- `promotion_rules` remains available as the v0.2 legacy fallback,
- user-facing docs now prefer minting language.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.9
```

## From `v0.2.7` To `v0.2.8`

This is a compatible minting lifecycle feature patch.

What changed:

- added `archive mint-zettel --dry-run`,
- added `archive mint-zettel --approve --reviewed-by <id>`,
- added mint receipts under `receipts/mint/`,
- added draft snapshots under `receipts/mint/drafts/`,
- added canonical zettel `mint` frontmatter,
- added doctor validation for mint receipts and SHA-256 file links,
- added read-only MCP `mint_zettel_check`.

No private archive migration is required.

If you mint new zettels, keep the generated canonical zettel, mint receipt, and draft snapshot together.

```bash
git fetch --tags
git checkout v0.2.8
```

## From `v0.2.3` To `v0.2.4`

This is a documentation polish patch.

What changed:

- rewrote `README.md` as a cleaner English project entrypoint,
- added `README.ko.md` as a full Korean entrypoint,
- split upgrade documentation into English and Korean files,
- clarified the public positioning, current status, privacy boundary, storage model, and text provenance.

No private archive migration is required.

Recommended steps:

```bash
git fetch --tags
git checkout v0.2.4
```

## From `v0.2.2` To `v0.2.3`

This is a bilingual documentation patch.

No private archive migration is required.

```bash
git fetch --tags
git checkout v0.2.3
```

## From `v0.2.1` To `v0.2.2`

This is a documentation, provenance, and public-history hygiene patch.

No private archive migration is required.

Important concept change:

```text
original editable text != OCR/AI-derived text
```

Both should be stored, but OCR/AI-derived text should keep derivation metadata and review status.

## Staying On An Older Version

Users may stay on an older version.

That is part of the design:

```text
old version -> old rule set
new version -> updated rule set
```

Future sharing and collaboration features should make the sender/receiver version explicit.

## Future Release Requirements

Every future public release should include:

- changelog entry,
- release note under `wom-kit/docs/releases/`,
- compatibility statement,
- migration instructions,
- test/doctor verification status,
- privacy scan status,
- Git tag,
- GitHub Release.
