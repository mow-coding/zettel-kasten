# Decision Log — v0.3.173 base-link-types append-only no-clobber sync

Date: 2026-07-05
Batch: v0.3.173 (implements the LOCKED spec: "`base-link-types` sync — append-only,
no-clobber"). Merges the base design + Critique A (safety/honesty) + Critique B
(operator-surface consistency).
Anchor tree at spec authoring: HEAD `d44157c1` (v0.3.172 intake label), tree clean.
Release action: working tree only — no git commit/tag/push. Never touches a real archive
or `zettel-kasten-basoon`; all test archives live in temp dirs.

This log records the decisions per the Critique A/B ledger and the AGENTS.md decision-log
mandate.

## Problem (verified in code)

The base `zettel-kasten/types.yml` grows over time (v0.3.168 added `continues`). An
archive that vendored its own `zettel-kasten/types.yml` permanently shadows the base
(`load_allowed_link_types:11480-11493` returns the local set and never falls through once
a local file exists), so a base-only link type like `continues` becomes silently invisible
in that archive and its edges fail the `allowed_edges` checklist. Before this release the
only remedy was a manual YAML hand-edit. The sibling `migrate --target link-types-v0.3`
appends only the recommended-9 connection-edge set and deliberately excludes `continues`.

## Decision 1 — the one hard contradiction: normalize-honest, not byte-preserve

Critique A's BLOCKER is correct and verified: `dump_yaml = yaml.safe_dump(..., sort_keys=
False, allow_unicode=True)` (`archive_services.py:2674-2676`) re-emits the whole file and
strips comments / reflows scalars. A design cannot both promise byte-preservation AND reuse
the migration write path.

- **DECISION — Option (b), honest normalize. No new dependency.** Keep `dump_yaml`
  (PyYAML). Drop the byte-preservation promise. The guarantee sync makes is **semantic,
  by-value, per-id**: no existing entry is removed, renamed, reordered relative to other
  existing entries, or altered in value; missing base entries are appended after the
  existing `link_types` (same as `migrate_link_types_v03`'s `.extend(missing_records)`).
  Surrounding formatting/comments are NOT preserved — the file round-trips through
  `safe_dump` exactly as `migrate --target link-types-v0.3` already does today.
- **Rationale:** a ruamel round-trip is genuinely new scope/dependency for an "additive
  command" release; the sibling migration already normalizes types.yml on every approve, so
  matching its fidelity is consistent and honest. Claiming better fidelity would be the
  dishonest release note Critique A forbids. The "byte-preserved" precedent test only
  round-trips equal because it pre-normalizes the fixture through `dump_yaml` first — a
  false assurance if reused verbatim, so the preservation test is restated as by-value/id
  parsing (T4), never a byte comparison and never watered down to set-membership.

## Decision 2 — command shape: fold into `migrate --target`, new target `base-link-types`

- **DECISION (per Critique B's strongly-preferred shape):** no standalone
  `sync-base-link-types` verb, no alias. Add `BASE_LINK_TYPES_TARGET = "base-link-types"`
  next to `LINK_TYPES_V03_TARGET`, add it to the migrate `--target` choices, and dispatch a
  third branch in `migrate_archive` to the new `sync_base_link_types(...)`.
- **Rationale:** a standalone verb would sit awkwardly beside `migrate --target
  link-types-v0.3`, which already appends missing base entries into the same types.yml and
  writes into the same `receipts/migrations/` tree. Folding it in reuses the dispatcher,
  receipt dir, and CLI surface. A distinct target segment (`zettel_edge_filename_segment
  ("base-link-types") == "base-link-types"`) plus a distinct `receipt_kind` is exactly what
  keeps the `link-types-v0.3` revert glob from cross-wiring.

## Decision 3 — `--reviewed-by`, guarded to the new target only

- **DECISION:** add `migrate.add_argument("--reviewed-by", ...)` and enforce it in
  `command_migrate` ONLY for `base-link-types` when `--approve` is used
  (`return 1` with the stderr message otherwise). The frontmatter and link-types-v0.3
  branches never receive `--reviewed-by`, so their pinned tests (`test_cli.py:34033,34094`)
  are untouched.
- **Rationale:** `--reviewed-by` is the house convention for approval-gated writes. The
  reused v0.1 migration receipt has no such field, so sync gets its own receipt variant
  (`schema_version: wom-kit/base-link-types-sync-receipt/v0.1`, `receipt_kind:
  base_link_types_sync`) rather than mutating migrate's receipt and churning pinned tests.

## Decision 4 — no-`types.yml` footgun: LOCKED to the SAFE branch

- **DECISION:** when the archive has no `zettel-kasten/types.yml`, write nothing, create no
  file, report `inherits_base_directly: true` and `archive inherits base directly; nothing
  to sync`. Do NOT raise (unlike `migrate_link_types_v03:63010-63011`, whose error is wrong
  for sync's purpose).
- **Rationale (verified against `load_allowed_link_types:11480-11493`):** an archive with
  no local types.yml transparently inherits ALL current and future base link types. Writing
  a local types.yml would permanently sever that inheritance and freeze the archive at
  today's base — a silent, irreversible regression opposed to the command's purpose. Both
  critics independently mandate this branch. Enforced by test T5.

## Decision 5 — no revert (LOCKED)

- **DECISION:** no `--revert` for `base-link-types`; `--revert --target base-link-types`
  fails closed with `base-link-types migration does not support --revert.`
- **Rationale:** a symmetric revert would have to distinguish sync-appended ids from
  owner-authored ids and could remove `continues` etc. the owner now relies on. Sync stays
  forward-only append; the recommended-set revert stays scoped to its 9. The
  `link-types-v0.3` revert reads only its own `migration_write` receipt AND intersects
  candidates with the recommended-9 set (`archive_services.py:63257`), so `continues` can
  never enter the revert set even if a stray receipt were mis-read.

## Decision 6 — idempotency footgun avoided

- **DECISION:** all receipt logic (path computation, receipt-exists blocker, write) is
  gated behind `if missing_records`. A second run with nothing missing sets
  `new_text = original_text`, computes no receipt, and reaches no `migration_receipt_exists`
  blocker: `files_written == []`, `ok == True`, `blocked == False`.
- **Rationale:** the receipt-collision blocker in the sibling migration only fires when
  there is something to append; gating all receipt logic behind the guard makes the second,
  nothing-missing run a clean no-op instead of a false blocker. Enforced by test T7.

## Decision 7 — discoverability (one wired message)

- **DECISION:** append a remedy hint to the doctor `zettel_edge_type_unknown` warning
  (`archive_cli.py:1663`) routing the operator to `archive migrate --target base-link-types
  --dry-run`. The edge-write blocker and the `allowed_edges` checklist block are left as-is
  to avoid changing block strings other tests pin.
- **Rationale:** a sync command nobody is routed to reproduces the original
  silently-invisible-base-type footgun; doctor's warning is the lowest-risk, already-per-
  edge surface to carry the hint, and it alters no blocker/exit semantics. Enforced by a
  doctor test.

## Verification

- New: T1 dry-run reports `continues` missing / writes nothing; T2 approve appends +
  writes receipt (`reviewed_by`, `receipt_kind`) + `load_allowed_link_types` sees it; T3
  requires `--reviewed-by`; T4 custom + divergent-same-id preserved BY VALUE (exactly one
  entry per id); T5 no-types.yml safe no-op; T6 rollback on receipt-write `OSError`; T7
  idempotent + migrate interaction + revert isolation; doctor hint test.
- Pins stay green: `test_migrate_link_types_v03_appends_missing_connection_edge_vocabulary`
  and `test_migrate_link_types_v03_revert_blocks_types_used_by_edges`;
  `test_capability_matrix_docs`.
- Gates: full pytest suite + `check_public_privacy.py` + `check_release_readiness.py`.
