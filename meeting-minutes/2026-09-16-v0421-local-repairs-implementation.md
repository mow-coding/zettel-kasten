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

## Unit LR-01d: zet-revision-write and zet-revision-restore-write reopened

The semantic revision pair (`zet-revision-write`, `zet-revision-restore-write`)
were the last two LR-01 writers (letters 157-160: reviewed revision proposals
could only be dry-run since the v0.4.0 compound closure; issue I14). Executing
model: Claude Opus 5, high reasoning effort, solo (no fan-out).

Design:

- Both writers keep their own digest protocol (expected-proposal and
  expected-current digests, reviewer marker, `revision_at`) and gain the same
  three exact-approval inputs as every other reopened writer
  (`expected_exact_approval_plan_sha256`, `expected_exact_approval_target_binding_sha256`,
  `exact_human_approval_claim`). The claim is verified immediately after the
  dry-run return point, against a binding rebuilt from the same
  `result_payload("ready_to_apply")` the preview produced (with `dry_run`
  marked true, because the binding builders refuse non-dry documents), so an
  approved dialog binds exactly the bytes and digests the write applies. The
  receipt embeds the approval reference.
- Unbound service calls no longer raise: the guard returns the same
  content-free blocked document as the compound era, with reason
  `exact_human_approval_required` instead of the closed reason, so the
  v0.4.0 fail-closed pins (`assert_compound_revision_write_blocked`) keep
  holding while the reopened path is testable. `_compound_exact_human_approval_blocked`
  takes the reason code as a parameter for this.
- Bindings: `zet_revision_write_approval_binding` and
  `zet_revision_restore_write_approval_binding` share `_zet_revision_binding`:
  the target is digest-only (zettel path, current bytes, proposal or
  restore-source receipt bytes, `revision_at`); the review context carries
  the expected-digest match flags, which must both be true; reviewer marker
  and affirm flags are deliberately not part of the basis because they are
  private reviewer inputs, not archive state.
- CLI: `_zet_revision_exact_approval_route` runs the preview without the
  reviewer/affirm inputs (the preview refuses them; earlier attempt failed
  with `reviewed_by_only_valid_with_approve`), re-derives the plan digest
  with the bound `revision_at`, opens the dialog with a live target observer,
  then executes the write with the reviewer marker and the claim. The
  reviewer marker may appear in the dialog context but never in stdout; a
  marker that is not a safe actor id returns `zet_revision_write_reviewer_required`
  (the letter-137 CLI pin was updated from `_workflow_failed_safely` to this
  precise reason). The restore parser gained a description mentioning the
  exact-byte restore so the help pins have text to assert.
- Copy: both operations were added to `ExactHumanApprovalOperation` and to
  all four per-operation copy tables (labels, questions, summaries, approve
  buttons); the schema enum `operation-exact-human-approval-v0.1` now lists
  all eight v0.4.21 operations; both receipt schemas gain optional
  `exact_human_approval`; packaged resources resynced.
- Registry and inventory: `COMPOUND_APPROVAL_FIXED_CLOSED_PLAN_WRITERS` is
  now empty; 55 approval-available, 60 fixed-closed (59 compound migrations
  plus `operation-control`); coverage manifest 55 paths, 29 pending.
  Installed-wheel smoke (v0.4.11 program) now asserts the reopened contract:
  help mentions exact human approval, a reviewer-less approve returns
  `zet_revision_write_reviewer_required`, evidence records
  `approval_status: approval_available`.

Verification: new `test_v0421_zet_revision_exact_approval.py` (5 tests: the
revision applies through the native boundary and a replay is blocked by the
preflight; cancel and missing reviewer write nothing; unbound service calls
return the blocked document before any read; restore returns the exact
previous bytes under one dialog; inventory reports both available). Updated
pins: letter-137 revision and help tests (59 closed), additional-public
count (59), command-status and v0.4.19 availability samples moved to
`remint-reconcile`, v0.4.0/v0.4.1/v0.4.20 release-doc counts (55/60, 55/29),
writer-session coverage gate denominator 55, letter-140 enum, `test_cli`
plan and write expectations (`ready_for_human_review`, applied write),
wheel-checker pins, capability matrix revision rows and inventory, operator
capabilities and exact-approval contract docs. Two test files rewritten by a
patch script came back with LF endings and were restored to CRLF before
commit (content diff unchanged). Readiness gate 5/5. The full cohort
(`test_cli` plus the approval and boundary modules, 26 modules) was rerun
from scratch on the LR-01d tree because the LR-01c cohort rerun had been
started before LR-01d changed the same modules; its result is recorded below
before the commit: 2,018 tests, OK (13 skipped), 3,504 s.

## Unit LR-01e: the intake chain under one approval

Design recorded before implementation; the implementation and verification
notes follow the design.

Letter 160 ⑦: one objet intake costs three approvals (`source-intake-record`
→ `objet-capture-selection --exact-existing-intake` → `objet-capture
--exact-local`); 42 popups for three drafts over two days. The v0.4.10 batch
pair (`source-intake-batch` → `objet-capture-batch`) already needs only two
approvals per batch, but it starts from a bounded batch request, not from the
`source-intake --dry-run` plan the client's flow produces, and the client has
never used it. The letter asks for the three-step chain as one plan.

Decision (Claude Opus 5, high; solo):

- New command `source-intake-chain` and module `source_intake_chain_exact.py`.
  Inputs are the union of the three steps' inputs (`--source-intake-plan`,
  `--staged-path`, `--item-id`, `--manifest-id`, `--project-intake-receipt`).
  No new approval system: the chain is a heterogeneous batch under the LR-01b/c
  `_ExactBatchAuthority`, one native dialog, one authenticated claim that every
  step re-verifies against the chain context before it proves its own binding
  is approved.
- Chain plan: (1) the existing record planner must be approveable; its
  receipt path and bytes are known at plan time. (2) The selection planner
  gains a projected-receipt input so it can validate the not-yet-written
  intake receipt from those exact bytes instead of disk; its selection path
  and bytes are then known. (3) The capture preview runs from the projected
  selection document (`_objet_capture_run(selection_document=...)`, the same
  in-memory path `objet-capture-batch` uses); capture never reads the intake
  receipt from disk. The chain binding covers the three step bindings (plan
  and target digests) plus the three content-free step identities.
- Execution: the chain callback builds the batch authority (which verifies
  the chain claim against a fresh chain plan), then runs record, selection and
  capture in order. The two manifest-framework steps get a chain variant of
  their `_authority`: the step's own manifest binding must be an approved
  pair (or approved target) and the `ExactOperationApprovalAuthority` is built
  from the chain claim's reference, so the exact-operation final receipts
  record the approval the human actually gave. The capture step takes
  `batch_authority` exactly like the LR-01c item writers. Later steps re-plan
  from disk after the earlier step wrote its bytes; the pair must match
  exactly because the written bytes are the projected bytes.
- A step failure after an earlier write is reported as `partial` with each
  step's state and the written receipt/selection paths so the remaining
  single-step commands can finish the chain; nothing is rolled back (the
  written intake record and selection are valid standalone artifacts).
- Registry: one more approval-available exact writer (56 available); the
  coverage manifest gains its path (session integration is LR-06).

Implementation (Claude Opus 5, high; solo). The design held with two
additions found while building:

- Projection seams. The selection planner reads the intake receipt in two
  places (its own strict reader and the legacy `objet_capture_selection_manifest`
  builder), and the capture run validates the intake receipt per item
  (`objet_capture_intake_evidence_blockers`). All three accept projected
  receipt bytes only while the receipt file does not exist yet; the capture
  run refuses projections on an approving pass. Experiment before coding:
  record, selection and capture plans are byte-deterministic across seconds,
  and the capture binding is identical whether planned from the projected
  selection document or from the file on disk.
- Capture precondition in the chain dry-run. The single-step capture preview
  does not check the archive-index manifest mutation authority; only the
  apply does. A chain that wrote its record and selection first and then
  met `archive_index_rebuild_required` would be honest but wasteful, so the
  chain plan runs the same read-only authority check
  (`require_archive_manifest_index_mutation_authority` with the current
  manifest snapshot) and blocks the capture step before any write.
- Chain authority. `source_intake_record_exact` and
  `objet_capture_selection_exact` gained `_chain_authority` plus
  `execute_*_in_chain(plan, claim=, chain_authority=)`: the step's own manifest
  binding must be an approved chain item (`item_approval`), the chain claim is
  re-asserted against the chain context, and the `ExactOperationApprovalAuthority`
  is built from that claim's reference. `objet_capture_apply` gained
  `batch_authority` exactly like the LR-01c item writers, with
  `_objet_capture_item_identity` (selection path, manifest id, staged paths).
  The chain module builds the authority with `_build_exact_batch_authority`
  over the three step documents after a fresh chain plan matched the approved
  digests.
- Binding and copy: `source_intake_chain_approval_binding` (target = sorted
  step pairs, step count, chain id and receipt digests; plan adds step
  identities, the intake plan digest and the staged-bytes digest; review
  codes `chain_step_bindings`, `intake_plan_digest`, `staged_source_digest`);
  `ExactHumanApprovalOperation.source_intake_chain` in all four copy tables;
  schema enum extended; packaged resources resynced.
- Result and receipt: the chain result lists every step's state, binding
  digests and output path, `files_written` (intake receipt, selection,
  capture receipt, object, manifest, index, chain receipt), and a chain
  receipt under `receipts/source-intake-chains/` records the one approval and
  the step bindings. A step failure after an earlier write returns `ok: false`,
  `state: partial`, per-step reason codes and `next_safe_actions` naming the
  single-step command that finishes; the framework keeps the claim `started`
  with `exact_human_approval_reconciliation.required`. The capture step's
  output path is minted at capture time, so the plan leaves it null and the
  result carries the actual receipt path.
- CLI: `source-intake-chain` (inputs: `--source-intake-plan`, `--staged-path`,
  `--item-id`, `--manifest-id`, `--project-intake-receipt`; `--dry-run` /
  `--approve --reviewed-by`, `--expected-plan-sha256`, progress default on)
  with a one-objet count-first collection (no staged name shown) and a live
  target observer; registered in the startup progress table.
- Registry and inventory: 56 approval-available (parser-derived), 60
  fixed-closed, 317 canonical paths / 576 invocation paths (surface digest
  `0b173957…`); coverage manifest 56 paths, 30 pending; capability matrix
  row "One-approval objet intake chain"; contract and operator docs updated.

Verification: new `test_v0421_source_intake_chain_exact_approval.py` (7
tests: dry-run plans three steps from projected bytes and writes nothing with
a stable digest; one dialog writes record, selection, capture and the chain
receipt, the exact-operation and capture receipts bind the chain claim's
approval id, and a replay is blocked; cancel, missing reviewer, dry-run with
reviewer and a digest mismatch write nothing; a refused capture precondition
blocks the plan before any write; a capture failure after two writes is
reported partial with the written selection still valid for the single-step
capture; step writers refuse a foreign or missing chain authority; inventory
and help). Pins: v0.4.1/v0.4.20 release-doc counts (56/317/576/274, 56/30),
coverage gate 56, letter-140 enum, v0.3.299 predecessor surface and private
objet index surface (577 paths, new digest), startup progress table.
Neighbouring intake modules (v0.4.8 selection, v0.4.9 record, v0.4.10 batch
intake and batch capture, v0.4.20 record command/workflow/held/original
review) pass. Readiness gate 5/5. The full cohort (36 modules including
`test_cli` and `test_wheel_install`): 2,127 tests, OK (15 skipped), 3,488 s.

## Release scope decision and v0.4.21 bump (2026-09-17)

Decision: release v0.4.21 with LR-01a-e now. Reasoning: the letters 157-160
regressions (eight closed writers, three dialogs per objet intake) block the
client's daily work and are fixed and verified; LR-06 (session integration of
30 pending writer paths) is a multi-release architecture item and LR-02
through LR-05 and LR-07 are older audit rows with no new client evidence
since the 2026-09-05 audit. Letter 160 ① (directory st_size) and ② fallback
guidance were already in v0.4.20; ④ stays unreproduced; the byte-hash
fidelity mode for binary originals is deferred as a design item. All carried
rows keep their register text and v0.4.21 target notes until re-planned.

Bump (Claude Opus 5, high; solo), following the v0.4.20 ritual: package
version 0.4.21 in pyproject and both `__init__` shims; CITATION 0.4.21;
supply lock `project-runtime-supply-lock-v0.4.21.json` (v0.4.20 bytes with the
target tag; sha256 `ec6e0b1b…`), policy and `project_runtime.py` pins;
bootstrap blocks (`bootstrap-v0421`, the v0.4.21 wheel URL, exact
`archive 0.4.21`) in both READMEs, both UPGRADE guides (new sections), the
kit README, both install guides, runtime entry points and version truth
source; CHANGELOG entry; capability matrix, operator manifest, contract and
philosophy-evidence status lines (previous-checkpoint lines keep v0.4.20);
release note `docs/releases/v0.4.21.md` packaged as the only note; historical
`test_v04xx_release_docs.py` moved CURRENT facts only, `test_v0420_release_docs`
keeps its own contract test, new `test_v0421_release_docs`; resource-path and
CLI surface digests refreshed. Release-doc, surface, runtime, capability and
coverage suites pass (353 tests); readiness gate 5/5.

Candidate CI on `0d795a0c` (PR #101, run 35114467567): the Ubuntu shards
found two stale pins that none of the unit cohorts included —
`test_mcp_server` expected the `zet_revision_plan` MCP tool to report
`approval_fixed_closed` (now `ready_for_human_review` with
`approved_write_implemented: true`, LR-01d) and
`test_notion_property_backfill_cli` pinned the v0.4.20 inventory counts
47/68 (now 56/60). Both corrected; the registry-inspecting modules outside
the cohorts (`test_mcp_server`, doctor performance/operability, invocation
effects, session command and public work-session modules) were run locally
(319 tests OK) before the corrected candidate was pushed.

## Pre-merge adversarial review of the v0.4.21 diff (2026-09-17)

Executing model from here: Claude Fable 5.1 with Ultracode, switched on by
the user ("사용량이 많이 남아가지고… 3시간 뒤에 주간 사용량 초기화"). The
release steps stay solo and sequential; the one fan-out used was a bounded,
read-only review workflow over `main...claude/v0421-work-session` — three
lenses (approval boundary, chain/projection, privacy and truth) and one
skeptic per finding, 9 agents, 1.14M subagent tokens, 16 minutes. Nine
candidate findings, six verified (none refuted), three unverified and
handled directly.

Corrections before merge (Fable 5.1, solo):

- `identity_after_own_write` race (edge batch and revert batch). The batch
  loop proved "the only change since the dialog was our own write" by
  re-reading the source after its write and again before the next item; a
  foreign edit landing between that check and the item writer's own fresh
  read was accepted under the batch approval (the reviewer reproduced it with
  a patched writer). Now the loop records the digest of the bytes it actually
  wrote (`written_source_sha256`, returned by `zettel_edge_write` and
  `zettel_edge_revert` on both result paths), passes it as
  `for_item(identity, own_write_source_sha256=)`, and the item writer passes
  the digest of the bytes it just read as `item_approval(...,
  fresh_source_sha256=)`; the identity rule is granted only when the two are
  equal. The proof is now tied to the writer's read, not to a separate look.
  Tests: two edges from one source are written as `exact` then
  `identity_after_own_write` (control); a foreign edit before the second
  item's read is refused with rollback; the authority refuses a non-digest
  own-write value and a missing or different fresh digest.
- Chain evidence when the capture reports `ok: false`: the capture writer
  publishes the object bytes and its always-written receipt before the
  manifest append, so a failed append left those durable writes out of the
  chain result and chain receipt. The failed step document now carries the
  capture's receipt path, `files_written` and summary, merged into the
  chain's `files_written`. A chain that wrote nothing (step 1 failed) no
  longer writes a chain receipt, and a receipt-write failure after real
  writes adds the warning `source_intake_chain_receipt_not_written` with
  `receipt_written: false` instead of silently reporting `completed`.
  Tests: manifest append forced to `not_written`; step 1 forced to fail.
- Documentation that still described the reopened writers as fixed closed,
  including the packaged Runtime Skill `operator-contract.md` that
  `runtime-skill-install` copies into client runtimes (zet-revision-plan
  "no supported handoff", discard "remain dry-run previews"), the
  `zet-revision-plan`, `zet-revision-write`, `zet-revision-restore-write`
  and `zettel-edge-batch` guides, the archive status board, the Notion clue
  audit, four capability-matrix rows, both root READMEs, and the release
  note/CHANGELOG sentence claiming batch receipts record the matched rule
  (only item receipts do). The docs tests that pinned the stale contract
  (`test_capability_matrix_docs` revision plan, revision write and restore
  write blocks) were re-pinned to the v0.4.21 text in the same change;
  packaged resources resynced. Doc suites 236 OK; readiness gate 5/5; full
  cohort (30 modules including `test_cli`, `test_mcp_server`,
  `test_wheel_install`, `test_git_backup_writer`): 2,185 tests, OK
  (13 skipped), 3,388 s.
