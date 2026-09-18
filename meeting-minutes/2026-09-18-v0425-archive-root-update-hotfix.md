# v0.4.25 archive-root update hotfix record (letter 161 and the 2026-09-18 v0.4.24 resume report)

Date: 2026-09-18 (Korea Standard Time)
Status: development verified on synthetic fixtures; release candidate in preparation; not client-verified

Executing models: Claude Fable 5.1 until the Fable limit was reached during
the first diagnostic workflow (all 8 agents failed on the limit); the user
switched the session to Claude Opus 5 and said to retry. Everything from the
retried workflow onward — reproduction, diagnosis, code, tests, docs and the
release steps — is Claude Opus 5, under the user's standing approval to run
the release train without re-asking. One bounded read-only workflow (5
readers, 1 synthesizer, 2 refuters; Opus 5) localised the failure window to
the transaction reopen; the decisive step was a solo reproduction with the
client's exact invocation form. Attribution of the commits: Claude Opus 5.

## User intent and boundary

The client's 2026-09-18 report (file
`.wom-scratch/analysis/wom-update-20260918/reply-to-devs-v0424-resume-fails-at-preflight.md`
in the client workspace, read only): with the public v0.4.24 bootstrap, three
`project-version-update --resume` runs died in `project-preflight` with
`result_unavailable` and no cause; `--dry-run` answered
`terminal_cleanup_required` and pointed back at `--resume`; requests: a cause
for preflight failures, whether `--abandon-started-approval` covers a
"reserved" transaction, and which files to send. The user's reaction: the
update still does not work, fix it. Boundaries unchanged: synthetic archives,
temporary repositories and local bare remotes only; the client workspace and
its letters are read only (the client's captured command outputs under the
shared `%TEMP%` were deliberately not read either — the client sends what we
ask for, in letters); no `git add -A`; every decision recorded here, in the
decision log and in the acceptance register.

## Reproduction (solo, synthetic)

Fixture: `repro_v0424_resume.py` (session scratchpad), derived from the
v0.4.22 two-step fixture, with two new switches: the positional root
(`--root archive|project`) and the client's colon-form reviewer id shape
(`person:<name>`, tested and cleared as a cause). Wheels: the
byte-exact public v0.4.18 (`ab8d07f5…`), v0.4.21 (`73f13ff7…`) and v0.4.24
(`44f964ab…`) in three isolated venvs; the hotfix build in a fourth.

| Run | Root | Code | Result |
| --- | --- | --- | --- |
| A. install v0.4.18 onto a v0.0.1 project | project | v0.4.18 | `updated_restart_required` (control, as in v0.4.22) |
| A'. the same install | archive | v0.4.18 | dialog shown, then `approved_snapshot_changed` wrapped as `exact_human_approval_state_unknown`, 130 s; lock + `lock_backlinked` + started claim left (fixtures fx1, fx2) |
| B. dry-run v0.4.21 on a v0.4.18 project | archive | v0.4.21 | `ready_for_approval` (letter 161 step 6) |
| B'. approve v0.4.21 | archive | v0.4.21 | dialog shown, then `approved_snapshot_changed` from `_project_update_assert_approved_snapshot_unchanged`, 154 s — letter 161 ③ exactly (fx6) |
| C. `--resume --abandon-started-approval` on fx1 | archive | v0.4.24 | exit 1, no JSON, 39 s, `project_version_update_directory_stability_unavailable` raised in `_project_update_reopen_durable_state` — the 2026-09-18 report exactly |
| C'. the same on fx2 | project | v0.4.24 | identical: the root given at resume time does not matter |
| D. the same on fx1 | archive | hotfix | `ok: true`, `preapproval_scaffold_cancelled` in one run, 63 s |
| E. fresh approve v0.4.24 on the cleaned fx1 | archive | hotfix | dialog shown, `updated_restart_required`, pin `v0.4.24` |
| F. plain `--resume` on fx2 | archive | hotfix | reopens, rediscovers the started claim, refused by the snapshot guard (`project_runtime_policy_invalid` under the newer runtime policy); the abandon route is the recovery |

A hold probe on run C printed the failing directory:
`<project>/parent_of_archive/.zettel-kasten/source`, `kind=missing`.

## Diagnosis

Preflight labels every recorded location by the root the operator gave:
`wom_kit_project_source_mirror_location(root_label)` and
`wom_kit_version_pin_location(root_label, ...)` return
`.zettel-kasten/...` for `inspection_root` and
`parent_of_archive/.zettel-kasten/...` for `parent_of_archive`
(`archive_services.py` ~105801-105816; `root_label` decided at ~136451). The
mirror location goes into the private plan as `mirror_logical`, the pin
locations into `pin_specs[].logical`, and the mirror, pin and receipt
locations into the intent's component `logical_target`s. Six consumers then
joined those strings literally onto `project_root`:

1. `_project_update_assert_approved_snapshot_unchanged` — pin specs
   (`state.project_root.joinpath(*logical.parts)`): the live pin observation
   looked at `<project>/parent_of_archive/...`, saw no pin, and reported the
   approved snapshot as changed right after the person approved (runs A', B').
2. `_project_update_reopen_durable_state` — `mirror_path` from
   `private_plan["mirror_logical"]`: the directory guard could not hold a
   missing directory (run C), before `--abandon-started-approval` was ever
   evaluated (the abandon guard runs after reopen).
3. `_project_update_reopen_durable_state` — component paths from
   `component.logical_target` (pins, receipt).
4. `_project_update_terminal_original_postimage_superseded_read_only` — the
   active pin.
5. the terminal-original basis check — `basis["mirror_logical"]`.
6. the terminal-original basis check — regular components.

The runtime (`.zettel-kasten/runtimes/vX`) and launcher
(`.zettel-kasten/bin/archive.cmd`) locations were never labelled, which is
why the mixed intent has both forms. Every earlier reproduction, the
runtime-journey checker and the CI fixtures pass the project root, so the
labelled form never reached the guard or the reopen in development. The
client runs every command from the archive root (README's
`archive project-version-update .` form), so every approve since v0.4.18
failed after the dialog and every resume failed in reopen.

Corrections to earlier statements: `marker.json` `state: reserved` is a
constant of every transaction (`ProjectUpdateReservation.document()`), not a
"before the dialog" state; the client's dialog was approved (letter 161) and
the claim is `started` in the archive's claim store, which the transaction
directory cannot show. The v0.4.22 record's "the refusing gate is load- or
state-specific" was wrong: it was invocation-form-specific.

The stderr line `operation tracking requires recovery-plan.` is not an
error: `OperationRunJournal.complete()` returns false whenever only a CLI
failure artifact exists, and the CLI prints that sentence then. The journal
sequence arithmetic (0 started, 1 starting, 2 project-preflight, heartbeats
every 10 s, then `result_unavailable`) placed the failure inside the reopen
before any code was read for it.

## Hotfix (branch `claude/v0425-archive-root-update-hotfix` from main `4a6d79d8`)

- A. `archive_services.py`: `wom_kit_project_update_logical_relative_to_project_root`
  strips the `parent_of_archive` label and refuses absolute, empty or
  traversing values; the six consumers above resolve through it. Recorded
  plans, intents, receipts and digests are unchanged, so the transaction the
  client already holds reopens as is.
- B. `archive_cli.py` / `operation_control.py`: a failure the service raises
  directly before any result carries its fixed code as `cause_code` and the
  journal's current stage as `cause_stage` (new read-only
  `OperationRunJournal.current_stage`); accepted classes are the fixed-code
  families (`ArchiveServiceError` with a single code-shaped argument,
  `ProjectUpdateTransactionError`, `ProjectRuntimeError`,
  `ProjectUpdateGitRunnerError`, `OperationControlError`,
  `ExactHumanApprovalError`) and the allowlisted prefixes plus `operation_`;
  the diagnostics writer accepts a hyphenated stage name. Free text never
  crosses; the journal schema is unchanged.
- Tests: `tests/test_v0425_archive_root_update_hotfix.py` (12: resolver
  cases and round trips with the preflight labels, consumers pinned to the
  resolver, stale literal joins absent, direct-cause projection incl. foreign
  families and free text, wrapper projection unchanged, journal stage
  accessor, diagnostics artifact with a hyphenated stage).
- Docs: release note `docs/releases/v0.4.25.md`, contract and
  project-version-update paragraphs, manifest and matrix intros, register
  row UF-02 and log entry, decision log
  `docs/archive-infra-decision-log-2026-09-18-v0425-archive-root-update-hotfix.md`.

Deferred (recorded in the decision log): the labelled public `files_written`
form; the pre-dialog `failed_rollback_incomplete` text blocker (seen once on
fixture fx5 while other fixture runs were executing concurrently, not
reproduced on the clean fx6 rerun); a `--resume --dry-run` preview.

## Verification

- Hotfix-adjacent cohort before the bump: `test_v0422_update_failure_hotfix`,
  `test_operation_control`, `test_v0419_operation_control_availability`,
  `test_project_update_transaction`, `test_operation_approval_binding`
  (261 tests) green; the new module green.
- End to end: runs D, E and F above on the hotfix build.
- Wider cohorts, the bump cohort and CI are recorded below as they complete.
