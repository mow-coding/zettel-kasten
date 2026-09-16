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
