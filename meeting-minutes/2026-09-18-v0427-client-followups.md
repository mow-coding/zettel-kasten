# v0.4.27 client follow-ups record

Date: 2026-09-18 (Korea Standard Time)
Status: development verified; release candidate in preparation; not client-verified

Executing model: Claude Opus 5, solo. Input: the client's v0.4.25 success
report (read only, `.wom-scratch/analysis/wom-update-20260918/reply-to-devs-v0425-success-report.md`).
The user's direction: keep working from the client's replies without
asking; the client keeps testing from the last letter. Boundaries unchanged.

## What the report established

- v0.4.25 recovery and update from the archive root: `preapproval_scaffold_cancelled`
  (one started claim abandoned) → dry-run 16/16 → approve →
  `updated_restart_required`, pin / source / runtime aligned after restart.
  The recorded intent carried the labelled locations exactly as diagnosed.
- Session permission mode `limited`: eleven writes under two dialogs.
- `source-intake-chain` ×5, `discard-draft --approve` ×3,
  `zettel-objet-link --approve` ×1, letter-159 `mint-zet` defects gone.
- The client states letters 157 through 162 may be closed (the client's
  own `resolved_in`); recorded on the register rows.

## Two maintainer errors in the reply draft

1. The step-3 approve command omitted `--affirm-external-writers-quiescent`;
   the client's first approve stopped at stage `starting` with a bare
   `ValueError` and no cause. Corrected in the draft; item 1 below makes the
   refusal name its code.
2. The draft did not warn that a bootstrap installed from a local wheel file
   is not the verified public wheel; item 2 below puts the hint into the
   blocked result.

## Implemented (branch `claude/v0427-client-followups` from main `e998852d`)

1. `archive_cli._project_version_update_direct_cause_code`: a bare
   `ValueError` whose single argument is a `project_version_update_` token
   (the command's own usage refusals) becomes `cause_code` with the journal
   stage (`starting`). Subclasses and free text stay excluded.
2. `archive_services`: the blocked result's `next_safe_actions` for
   `project_runtime_exact_public_wheel_required` name the public-URL
   reinstall and a dry-run from that bootstrap.
3. `work_session_permission.normalize_grant` raises
   `work_session_permission_operation_not_grantable` with a content-free
   `detail` (`rejected_operation_index`, `grantable_operations`,
   `always_dialog_operations`); `WorkSessionServiceError` carries `detail`
   through `_safe_call`; `management_failure` emits it as `reason_detail`.
4. `source_intake_record_exact._strict_json_object` and the batch twin strip
   a UTF-8 BOM and name UTF-16/32 marks with two new fixed codes.
5. `_draft_discard_plan_core` / `_draft_discard_restore_plan_core` mirror
   `plan_sha256` at the top level.
- Tests: `tests/test_v0427_client_followups.py` (9); the v0.4.25 hotfix
  test's free-text case now uses a non-token string because bare tokens
  are a cause since this release.

## Asked back, not changed

The index-rebuild block after several intakes: the chain already checks the
index mutation authority at planning time and reports the capture step as
blocked with `archive_index_rebuild_required`, so the observed sequence
(which run blocked, at dry-run or at approve, and whether the earlier chains
reported `index_marked_dirty`) is requested in the reply before any change.

## Verification

Recorded below as the cohorts and CI complete.
- Session, intake, discard, permission and MCP cohorts (44 modules) green
  against the changes; `test_v0427_client_followups` (9) green.
