# Decision Log — v0.3.168 Draft-Time Identity Hygiene + Honest Human Affirmation + Continuation Edges

Date: 2026-07-04
Batch: v0.3.168 (implements the LOCKED spec: "Draft-time identity hygiene + honest
human affirmation + continuation edges").
Anchor tree at spec authoring: HEAD `522bd4a5` (v0.3.167), tree clean.
Release action: working tree only — no git commit/tag/push. Never touches a real
archive or `zettel-kasten-basoon`; all archive fixtures live in temp dirs.

This log records the five design decisions with one-line rationales, plus the two
corrected critique facts, per the AGENTS.md decision-log mandate.

## Prime directives (highest priority, unchanged)

- **(마) Identity safety — forward-only.** No existing canonical id is renamed or
  normalized; mint gains no id-rewrite path. Only the generator of new draft ids
  changes, before any reference can exist.
- **(다) Lifecycle safety — no silent auto-delete.** Mint never deletes the inbox
  draft; retirement stays its own approval-gated step.
- **(나) Lifecycle safety — no AI self-affirm.** A human-review item can be affirmed
  only with an attributed `--reviewed-by`; `--affirm` is inert without one, cannot
  override machine-enforced items, and is recorded auditably in the receipt.

## Item (마) — titleless/Hangul draft id keeps a `_draft` slug

- **DECISION:** fix at draft creation, forward-only. Change ONLY the empty-slug
  fallback token in `make_zettel_id` (`archive_services.py:63039`) from `draft` to
  `note`. No normalize-at-mint, no rename of any existing id.
- **Rationale (fix-at-draft vs fix-at-mint):** `make_zettel_id` runs once before any
  reference target exists; fixing at mint would demand an atomic multi-file
  reference rewrite (canonical id/filename, edges, `source_refs`, object manifests,
  the mint-receipt path, the draft snapshot path all derive from the id).
- **Rationale (token = `note`, not a hash):** `note` is human-readable and stable,
  and the existing same-second collision loop (`while path.exists(): …_{suffix}`)
  already disambiguates, so a hash would be opaque and buy nothing.
- **Grounded trigger:** the slug regex keeps only `[a-z0-9]`, so ANY title with no
  ASCII alphanumerics — including a pure-Hangul title — hits the fallback, not just
  an empty title. Existing `zet_<ts>_draft` ids and real "draft …" title slugs are
  untouched (they are not the fallback).

## Item (나) — mint human-review checklist only satisfiable by hand-editing YAML

- **DECISION:** add a repeatable `--affirm` flag (`action="append"`) + required
  `--reviewed-by`, threaded through the whole dry-run chain into
  `build_lifecycle_checklist`, applied as source `cli_affirmation` only when the
  operator did not hand-edit the YAML, and recorded as an attributed `affirmations`
  block in the mint receipt.
- **Rationale (flag format = append):** matches every other multi-value flag
  (`--facet`, `--assisted-by`, `--supervised-by`, `--derived-from`, `--source-ref`,
  `--local-ai-session`); the CLI has no comma-split primitive.
- **Rationale (AI self-affirm):** enforce two mechanical gates (inert without an
  attributed reviewer; scoped to the two human items and unable to override machine
  items) and document the residual honestly — auditability, not string-sniffing, is
  the honest guarantee. A prefix rejection (`ai_runtime:`/`ai:`) is NOT added: it is
  trivially bypassed (`--reviewed-by person:not-really`), giving false assurance,
  and would break the legitimate audited case where an operator's id carries a tool
  tag.
- **Wiring proof:** the two items infer to `needs_human_review` and are
  `required: true`, so they become dry-run blockers; the affirmation is threaded
  into the SAME on-the-fly checklist evaluation that would otherwise block, so a
  post-mint-only receipt note would not unblock the dry-run.
- **Machine-item guard proof:** `object_id_only`/`allowed_edges` are excluded from
  `HUMAN_AFFIRMABLE_CHECKLIST_ITEMS`, and the `MACHINE_ENFORCED_CHECKLIST_ITEMS`-
  blocked branch precedes the `explicit is True` branch, so a machine block cannot
  be flipped by `--affirm`.
- **YAML precedence:** a hand-edited YAML value (`explicit not None`) wins first, so
  `--affirm` never flips an explicit YAML `false` — an operator who marked an item
  failed must not have it silently overridden.

## Item (다) — mint does not auto-retire the consumed inbox draft

- **DECISION:** keep `preserves_draft_reference: true`; mint does NOT delete the
  draft. Fix discoverability only: add a `next_safe_actions` list to the mint result
  pointing to `archive retire-draft --zettel-id <id> --dry-run`, printed in text mode.
- **Rationale (pointer vs chain flag):** deleting a consumed draft is a separate,
  approval-gated act; a pure pointer routes the operator to retire-draft without
  making deletion an implicit mint side effect. No opt-in chain flag ships here.
- **Rationale (doctor routing):** scope concrete routing to the mint result;
  `info()`/`warn()` cannot carry a `suggested_command` (that is an `error()`-only
  parameter), extending them is out-of-scope cross-cutting work, and mint-time is
  the moment the stale draft appears.

## Item (라) — no `continues` connection/edge type

- **DECISION:** add a `continues` link type to the BASE vocabulary in BOTH
  `types.yml` files, matching the existing entry shape. Do NOT add it to
  `CONNECTION_IMPORT_RECOMMENDED_EDGE_TYPES`; leave
  `CONNECTION_EDGE_RELATIONSHIP_VOCABULARY` untouched (do not promote `sequence`).
- **Rationale (recommended-set membership):** migration/revert only ever touch the
  recommended set, so a base-only member keeps every pinned migration and
  connection-vocabulary test green.
- **Rationale (do not promote `sequence`):** touching
  `CONNECTION_EDGE_RELATIONSHIP_VOCABULARY` risks the connection-fixture counts; a
  carved-out base description resolves the ambiguity without that risk.
- **Disambiguation:** `continues` = same-thread continuation / next installment in
  the SAME work — explicitly NOT `derived_from`, `references`, `derived`,
  `supersedes`, or a generic `sequence` step.
- **Migration/revert proof:** `missing` and the revert-candidate set are computed as
  intersections with the recommended set, so a non-recommended base member is never
  appended and never reverted.
- **Acknowledged limitation:** archives that vendored their own `types.yml` do not
  receive `continues` via `migrate link-types-v0.3`; they add it manually
  (additive). Deliberate trade to keep migration test-safe.

## Item (가) — create-draft does not validate `--kind`

- **DECISION:** validate `--kind` inside `create_draft_zettel` against the archive's
  own `zettel-rules.yml`, emit a WARNING (not a block) listing the valid kinds, keep
  default `fleeting_capture`, no argparse `choices=`. Print the warning in the
  non-dry-run text path, and add a read-only `--list-kinds` path.
- **Rationale (warn vs block):** valid kinds are archive-owned and may be custom; a
  `choices=` list is fixed before the archive root is known, and a hard block would
  be stricter than mint (which only warns on unknown kinds).
- **Rationale (`--list-kinds`):** the warning enumerates kinds inline AND a
  discoverable read-only lister exists, so the reference is never dangling.

## Corrected critique facts (load-bearing)

1. **Recommended-set membership.** `CONNECTION_IMPORT_RECOMMENDED_EDGE_TYPES`
   (`archive_services.py:285-295`) has **9** members and **includes `supersedes`**.
   The 8-member literal cited in the critiques/tests
   (`{material, derived, semantic, embed, mention, contains, view_query,
   comment_context}`) is the fake-archive *test-fixture* set, not the constant — the
   tests pin the 8-member set because the fixture's `types.yml` already ships
   `supersedes`, so it never appears in `missing`. This does not change any decision;
   the spec is grounded on the real constant.
2. **Checklist anchor drift.** `build_lifecycle_checklist` is at line **11117** (not
   ~11136/11145), `infer_promotion_checklist_item` at **11212** (not ~11266), and
   `MACHINE_ENFORCED_CHECKLIST_ITEMS` at **2531** — several critique line numbers
   were off by ~120 lines. All decisions hold under the corrected anchors, which
   were re-verified against HEAD `522bd4a5`.

## Scope

Five additive items. No archive migration, no id rewrite, no hash change; all new
flags/fields opt-in. Working tree only; the main session releases after gates.
