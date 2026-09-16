# v0.4.21 local repairs implementation record

Date: 2026-09-16 (Korea Standard Time)
Status: development in progress; not integrated, released, or client-verified

## Scope and sequence

v0.4.20 is public (tag `v0.4.20`, main `25a46efb`, evidence in
`meeting-minutes/2026-09-16-v0420-release-evidence.md`). This worktree
(`zettel-kasten-v0421-work-session`, branch `claude/v0421-work-session`)
starts from main `9a4e6364` and carries the v0.4.21 rows of the acceptance
register: LR-01 through LR-07. The user's standing approval covers the train
and its releases; the hard boundaries stay: synthetic archives, temporary
repositories and local bare remotes only; no client archive, runtime,
credential, provider configuration, feedback ledger or public-PATH
installation is read or modified; the beta-letter workspace is read only.

Executing model for every unit below: Claude Opus 5 at effort high, solo (no
agent fan-out), announced to the user before the first code change.

Unit order (client impact first, from the letters 150-160 verification
record): LR-01 reopenings that letters 157-160 report as regressions
(discard-draft and restore; the zettel-edge, mint and retire batches; the
semantic revision and restore writers), the letter-160 intake-chain single
approval, then LR-06 session integration of the pending writer paths, then
LR-02 through LR-05 and LR-07.

## Unit LR-01a: discard-draft and discard-draft-restore reopened

Since v0.4.0 both writers were `approval_fixed_closed` with
`compound_exact_human_approval_binding_required`: the dry-run validated and
`--approve` refused before any read. Letters 157-160 (issue I14) report that
regression in daily use. v0.4.21 reopens both through operation-specific exact
human approval, the same boundary every other v0.4 writer uses; no approval
mode substitute and no new approval system.

Design:

- `ExactHumanApprovalOperation.draft_discard` and `draft_discard_restore`
  with Korean dialog copy (label, question, summary, approve button) in every
  per-operation table.
- `operation_approval_binding.draft_discard_approval_binding(plan)` and
  `draft_discard_restore_approval_binding(plan)` follow the retire-draft
  template: the plan must be ready with no blockers; ids, archive-relative
  paths and the reason digest are reduced to digests before the public
  binding; the target preview shows only the draft filename and id; a
  tampered plan (for example a mint receipt present) is refused.
- `completion_workflows.draft_discard_apply` and `draft_discard_restore`
  require the claim, the expected exact plan digest and the expected target
  binding digest before any archive read; under the existing per-draft lock
  they re-derive the plan, rebuild the binding from that fresh plan and call
  `_require_exact_human_operation_approval`, whose receipt is embedded as
  `exact_human_approval` in the discard and restore receipts. The plan
  document now reports `state: ready`, `approval_status: approval_available`
  and an `approval_contract` from the new
  `command_status.exact_approval_available_plan_contract`, keeping
  `plan_sha256_is_approval_authority: false`.
- The CLI `--approve` route (`_draft_discard_exact_approval_route`, shared by
  both commands) requires `--reviewed-by`, a valid `--expected-plan-sha256`,
  runs a fresh private preflight, compares the service digest, binds, adds the
  bound-file title clue only for the discard (the draft is absent before a
  restore), opens the production boundary and maps every failure to a fixed
  reason code (`discard_draft_apply_reviewer_required`,
  `..._expected_plan_sha256_invalid`, `..._preflight_blocked` with bounded
  blockers, `..._plan_changed`, `..._workflow_precondition_failed`,
  `..._workflow_failed_safely`, or `exact_human_approval_state_unknown`).
- Both receipt schemas gain an optional `exact_human_approval` object;
  pre-v0.4.21 receipts without it stay valid, so historical restores still
  plan. The shared operation-approval schema enum gains the two operations.
- `command_status` drops both names from the fixed-closed registry and the
  plan-writer map; the audited v0.3.320 exposure history no longer describes
  them, so they report `history_not_audited` like every reopened surface.
- Coverage manifest: both paths are classified `pending` with target v0.4.21
  (session refs follow with LR-06); the honest denominator is now 49.

Inventory after the unit: 316 canonical paths, 575 invocation paths, 49
approval-available (11 conditional), 66 fixed-closed (65 compound migrations
plus `operation-control`), 201 not exposed. The MCP surface is unchanged (no
discard tool exists).

Verification: new `test_v0421_draft_discard_exact_approval.py` (6 tests:
plan contract, full discard then restore through the injected native dialog
and key with schema-validated receipts and no reason or path echo, cancel and
stale digest and missing reviewer writing nothing, unbound workflow calls
failing before any archive read, binding privacy and tampering, capability
inventory). Updated pins: completion-workflows discard test rewritten to the
reopened contract; letter-137 boundary tests now assert the unbound service
call raises `exact_human_approval_required` before the plan core and the CLI
refuses with a fixed code without entering the writer; closed-writer samples
in the command-status, blocked-help and v0.4.19 availability tests moved to
`mint-zet-batch`; closed count 67→65 and available 47→49 in the v0.4.0,
v0.4.1 and letter-137 tests; the v0.4.20 manifest pins moved to 49/23; the
wheel checker's v0.4.11 smoke program asserts the reopened contract and help
for discard-draft and the fixed-closed contract for zet-revision only, and
that a reviewer-less `--approve` refuses with `discard_draft_apply_reviewer_required`
without entering the writer. Cohorts: 421 tests (surface, docs, boundary,
schema parity, predecessor surfaces) OK; wheel-install, MCP and fail-closed
cohorts 241 tests OK; the v0.4.11 installed smoke program rerun from a wheel
built from this tree in a fresh venv returned `ok: true`; readiness gate 5/5.

## Unit LR-01b: zettel-edge-batch under one exact approval

Letter 160 measured 21 single-edge dialogs for one review batch (issue I40)
because `zettel-edge-batch --approve` had been fixed closed since v0.4.0 and
each edge went through `zettel-edge` alone. v0.4.21 reopens the batch under
one operation-specific exact human approval that covers exactly the reviewed
policy-writable items.

Design:

- The dry-run already ran the single-edge preflight per item. It now keeps
  each item's own single-edge binding digests (`approval_plan_sha256`,
  `approval_target_binding_sha256`, public-safe) in the result; an item whose
  binding cannot be built is a blocker.
- `operation_approval_binding.zettel_edge_batch_approval_binding(plan)` binds
  the sorted set of those item digest pairs plus the batch id and receipt path
  as the target, and the policy, item projection (all digests), queue counts,
  warnings and would-change digest as the plan. The first source filename is
  the only local label; nothing private enters the public binding.
- `zettel_edge_batch_write(approve=True)` requires the claim and both expected
  digests before any read, re-runs the dry pass, verifies the claim against
  the batch binding built from that fresh pass, then constructs a private
  `_ZettelEdgeBatchAuthority` (batch context, digests, the approved item pair
  set, the batch approval receipt). Each item write calls `zettel_edge_write`
  with that authority: the single writer re-derives its own binding, proves
  the pair is in the approved set, re-authenticates the same claim against the
  batch context, and embeds the batch approval receipt plus its own item
  binding in the edge receipt. A forged authority object or a batch authority
  without `approve` is refused before any read. The batch receipt embeds the
  batch approval. Rollback on any item failure is unchanged.
- The CLI route requires a reviewer, refuses dry-run plus approve through the
  shared parser gate, runs the private preflight (fixed
  `zettel_edge_batch_preflight_blocked` with bounded blockers, no dialog),
  treats a plan with no policy-writable edges as an honest no-op without a
  dialog, and otherwise opens the production boundary with the v0.4.20
  count-first `TargetCollectionPreview` of the source zets and a live observer
  that re-runs the dry pass; the dialog therefore shows "대상 N개" with one page
  per 20 zets and closes if a source changes while the person is reading.
- `command_status` drops the command from the fixed-closed registry; the
  audited v0.3.320 history no longer describes it. Inventory: 50 available,
  65 fixed-closed (64 compound migrations plus `operation-control`). Coverage
  manifest: pending session integration (LR-06), denominator 50.

Verification: new `test_v0421_zettel_edge_batch_exact_approval.py` (5
tests: item bindings and capability truth in the dry-run; one dialog writing
two policy edges while the low-confidence row stays queued, receipts carrying
the batch approval and item bindings; cancel writing nothing and a source
edited after the decision refused with rollback and the honest unknown-state
code; unbound and forged-authority calls failing before any read; reviewer and
mode errors without a dialog). Updated pins: the letter-137 batch tests now
assert the unbound service call and the missing-archive CLI route stop before
the writer; the non-boolean guard list drops the reopened writer (48); the
legacy `test_cli` batch test now asserts the approved write and its receipt
and the type-incompatible test asserts the preflight block; the test CLI
approval fake accepts the preview options and calls the observer once; closed
count 65→64 and available 49→50 in the v0.4.0, v0.4.1 and letter-137 tests;
manifest pins 50/24; capability matrix edge row and inventory paragraphs.
Cohorts: 429 tests (approval, boundary, preview, checker, docs) OK; the full
`test_cli` module (1,469 tests, 3,434 s) passed except the format-variant
batch test whose closed-era expectation LR-01c updates; readiness gate 5/5.

## Unit LR-01c: mint, retire and edge-revert batches under one approval each

`mint-zet-batch`, `retire-draft-batch` and `revert-batch` were the remaining
fixed-closed batches of LR-01 (letters 157-160: repeated single dialogs for
reviewed batches). They reuse the LR-01b mechanism, generalized.

Design:

- The batch authority is now generic. `_ExactBatchAuthority` holds the batch
  context and digests, the approved item binding pairs, the approved item
  identities and the batch approval receipt; `_build_exact_batch_authority`
  verifies the batch claim against a fresh dry pass immediately before the
  first write. Each item write receives `for_item(identity, own_write_state_verified)`,
  a per-item view whose `item_approval` accepts the fresh single-item binding
  in order of strictness: an exact approved pair; an approved target digest
  when only review context drifted (a mint's duplicate scan changes after the
  batch's own earlier mint while the draft bytes and destinations do not); or
  an approved stable identity when the batch itself verified that the only
  change to the item's source since the dialog was its own earlier write (two
  edges from one zet). The same authenticated claim is re-verified against
  the batch context on every item, and the receipt records which rule matched.
  Identities are content-free digests of ids and archive-relative paths.
- `mint_zettel`, `write_retired_draft_from_plan` and `zettel_edge_revert`
  accept the per-item authority exactly like `zettel_edge_write`; a forged
  or wrongly typed authority is refused before any read.
- The mint and retire batches now plan every item first (recording the
  single-item binding and identity), refuse to approve while any item cannot
  be planned (fixed or skipped with `--skip-existing`), verify the batch claim
  from a planned batch document with the receipt path the write will use,
  then write. The revert batch keeps its plan-then-write shape and gains the
  same verification. Batch receipts embed the batch approval; item receipts
  embed the batch approval plus their item binding and match rule.
- Bindings: `mint_zet_batch_approval_binding`, `retire_draft_batch_approval_binding`
  and `zettel_edge_batch_revert_approval_binding` share `_batch_binding`:
  sorted approved pairs, item count, batch id and receipt digests as the
  target; item projections, policy or source-receipt digests and warnings as
  the plan; the first draft or source filename as the only local label.
- CLI: `_exact_batch_approval_route` is shared by the four batches (mode
  conflict and reviewer checks, fresh preflight with bounded blockers, an
  explicit `nothing_to_write` no-op without a dialog when nothing is
  writable, count-first collection preview with a live observer, fixed
  reason codes). The edge batch was moved onto it.
- Registry and inventory: three more writers leave the fixed-closed set;
  53 approval-available, 62 fixed-closed (61 compound migrations plus
  `operation-control`); coverage manifest 53 paths, 27 pending.

Verification: new `test_v0421_lifecycle_batches_exact_approval.py` (4
tests: two drafts minted under one count-first dialog with batch and item
receipts; the two minted drafts retired under one dialog; a written edge batch
reverted under one dialog with the original receipts preserved; cancel and
unbound and reviewer-less calls writing nothing). Updated pins: letter-137
compound and edge-revert tests assert the unbound service call and the
missing-archive route stop before the writer; the non-boolean guard list
drops the three writers (45); closed 64→61 and available 50→53; manifest
53/27; closed-writer samples moved to `zet-revision-write` and
`zet-revision-restore-write`; the legacy `test_cli` mint batch test asserts
the approved write, the retire test asserts the preflight block on a missing
plan, and the format-variant test asserts the explicit no-op; capability
matrix mint lifecycle and edge rows; inventory paragraphs. Cohorts: 363
surface and boundary tests OK; readiness gate 5/5. The full `test_cli` module
and approval-cohort rerun on the LR-01c tree was interrupted by the user's
shutdown; it is the first step when work resumes and must pass before PR CI
is trusted for this unit (the LR-01b tree's full `test_cli` run is recorded
above; only the closed-era expectations LR-01c updates changed since).
