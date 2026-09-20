# v0.4.36 candidate CI contract correction

Date: 2026-09-21. Execution: Codex continuing the existing release candidate after a Claude handoff.
Status: local regression verified; corrected remote candidate CI, merge, tag, and publication remain pending.

## Findings

Candidate CI run [35527154522](https://github.com/mow-coding/zettel-kasten/actions/runs/35527154522) exposed four distinct stale expectations. The four failures were reproduced locally with synthetic fixtures before changes (4 tests, 14.183 seconds, exit 1).

| Existing test | Intended candidate behavior | Correction and retained protection |
|---|---|---|
| Feedback draft revision and rebinding | Compose creates the draft record by default | Exercise the full revision/rebinding journey in default and explicit manual modes; default duplicate creation must still be refused. |
| Approval command inventory | Archival adds one approval-capable command | Pin 61 and the new command's status; retain target-conditional and closed-path checks. |
| Public CLI surface inventory | Archival adds one CLI path | Pin 585 and its digest. Removing only the new path reproduces the previous 584-path digest exactly. MCP and database pins are unchanged. |
| Backup refusal after target drift | Proven no-effects refusal closes its approval claim | Check refusal, domain cause, failed claim, no Git staging, and unchanged local and remote commit IDs. |

The first strengthened backup assertion used an overly specific guessed cause. Running it showed the actual propagated cause is `exact_operation_target_state_drifted`; both cause and claim assertions now use that observed contract.

## Scope and decisions

- Product source and permission policy are unchanged. No full-access exclusions were introduced.
- Use the existing pull request, with the correction isolated from unrelated process-document changes.
- Test data consists of synthetic fixtures and temporary development repositories. No customer workspace was inspected or modified.
- Keep release mutations sequential. A failed or unfinished candidate CI is not release evidence.
- Update this record with the local result before committing. Record the resulting remote candidate separately after pushing so a record does not claim to know its own future commit ID.

## Verification

Relevant local regression: 110 tests in 747.818 seconds, exit 0 (2 release-artifact-only checks skipped because their paired artifacts were not supplied). This covers both draft journeys and the backup writer, inventory, private metadata, prior feedback, current feedback, and exact approval workflow modules. Release-document verification after resource normalization: 9 tests in 0.196 seconds, exit 0. The corrected remote candidate CI is still required.
## Release wording correction

The user has prioritized process improvements next. The release note and changelog now keep functional follow-ups in backlog without promising v0.4.37. The earlier decision log retains its historical statement and adds an explicit superseding note. The packaged note and resource manifest were synchronized. Release-document tests: 9 passed (0.181 seconds).

The first readiness gate passed all five checks and verified 173 synchronized resources. It will be repeated after the wording correction because packaged documentation changed.


The post-wording gate passed links, Korean language, runtime skill, and coverage. Its privacy scan refused with index_snapshot_drift because staging changed during the scan. This is a real invalidated snapshot, not a privacy pass; recheck the stable index before committing. Source and packaged notes use LF as required by the repository, and their manifest was regenerated after normalization.

Stable-index retry: privacy PRIV000, zero findings; all 173 packaged resources synchronized. Staged whitespace review found two extra trailing blank lines, removed before commit. Final staged privacy and whitespace checks are required after this record update.
