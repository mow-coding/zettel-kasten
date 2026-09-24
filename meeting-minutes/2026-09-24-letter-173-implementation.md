# 2026-09-24 beta letter 173 and the one-letter request — implementation record (public, sanitized)

Executed by: Claude Opus 5.5 (Claude Code). Owner for this unit: Claude, single worker.
Scope source: the developer's direction to handle beta letter 173 and a forwarded client request about letter preparation. No customer workspace was accessed beyond the letter the developer named; tests use synthetic data only. Customer text, identifiers and paths are not reproduced here.

## What the client reported (summarized)

- A. After a clean `activity-cleanup` preview, the approval failed with `activity_cleanup_plan_changed`; private plan comparison showed only folder size rows differing.
- B. Large previews and approvals ran for minutes without progress, and a refusal reported `effects_state: unknown`.
- C. `git-backup-plan` refused an ignored attribute file in a scratch/restore-test folder; the session backup route answered only `work_session_git_unavailable`.
- D. Session close required fates for AI artifacts of every activity, the approval-side inventory stopped at 1000 rows, and the scratch writers were fixed-closed.
- E. (separate request) "Write a letter" should give one deliverable letter with two states, not review drafts and side files.

## What changed (v0.4.39)

- A: folder size and time are no longer part of the plan fingerprint; content changes still change it.
- B: refusals before approval report no effects; content-free progress, heartbeats and an optional progress log.
- C: inert ignored attribute files no longer block; the session route names the fixed cause with a next action.
- E: runtime route v0.3 (compose approval is the single human decision), automatic next letter number, two user states in compose and ledger results, Skill and lifecycle document updated. The AGENTS block is unchanged (see decision L173-06).
- D: direction decided by the developer; implementation follows in the next version.

## Verification (development only)

Each fix has a synthetic reproduction that fails before the change and passes after it (checked by stashing the change where applicable). Local Windows runs: activity cleanup 26, feedback/routing/compose 103, Git backup and session Git suites 235 plus the two new modules, release documentation 289, package resources and runtime skill checks, and the release readiness gate. Full CI, public release, anonymous download and fresh installation are recorded separately. Customer update and successful use are not confirmed.

## Process notes

- The lesson of the v0.4.19 fix (a Windows folder size is not content) had not reached the newer cleanup module, so the same class of defect reappeared. The new test pins the rule for this module.
- One tightening (preview effects reported as none under the session lock) was reverted because existing tests pin the conservative contract and the effect-free claim was not proven.
- The first local release-documentation run after the Skill edit found a word-budget overrun (1409 > 1400); it was fixed before any CI run.
