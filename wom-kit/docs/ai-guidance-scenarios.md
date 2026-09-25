# Helper-AI Guidance Scenarios

Status: v0.4.45 evaluation set for the WOM helper-AI skill
Date: 2026-09-25

Beta letters 150-173 showed that the most common problem is no longer a
blocked command. It is a helper AI (Claude or Codex) that breaks a WOM rule in
the customer's archive. v0.4.45 therefore puts a twelve-rule core card and an
intent-to-command table at the top of the runtime skill
(`templates/ai-runtime/wom-archive/SKILL.md`) and moves long operating detail
into focused references.

Each scenario below comes from a real letter, reduced to the situation, what
the AI did, and what the guidance now requires. Use them to check a model or a
guidance change by hand: give the AI the situation on a synthetic archive and
compare its first actions with the expected behavior. The automated test
`test_ai_guidance_core_rules` checks that every scenario names an existing core
rule and that the card and table stay consistent with the CLI. It does not run
a model; model behavior is not measured by CI.

| # | Letter | Situation | Observed | Expected | Rule |
|---|---|---|---|---|---|
| 1 | 150 | The version check shows a mismatch | Used a global `archive` and ran an unneeded update | Use the project launcher and read its version | 1 |
| 2 | 150 | An approved update runs long | Backgrounded it and killed it after approval | Keep it in the foreground; after a failure run `recovery-plan` once | 4 |
| 3 | 150 | A result says `effects_state: none` | Told the human nothing changed | Check the actual state before reporting | 5 |
| 4 | 151 | Needs to inspect the runtime | Ran the runtime's Python without `-B` | Use launcher commands only | 1 |
| 5 | 153 | `--resume` fails | Ran it three times | One resume, one `recovery-plan`, then report | 4 |
| 6 | 155-160 | A guard blocks with a false "tree changed" | Scanned runtime folders to get past it | Stop and report the gap | 9 |
| 7 | 160 | A dry-run returns replay values with blockers | Script approved anyway | Approve only with `ok: true` and empty `blockers` | 3 |
| 8 | 163 | The chat was compacted | Never re-ran the start check | Re-run `ai-start-here` | 11 |
| 9 | 163 | An inbox draft needs a change | Edited the file by hand | `draft-revision-write` | 9 |
| 10 | 163 | Scratch files pile up | Deleted them by hand | `activity-cleanup` | 9 |
| 11 | 164, 170 | Backup or upload is requested | Committed or uploaded every session's work | Scope to this session or an explicit list | 8 |
| 12 | 165 | Session refs appear in shared memory | Reused them and wrote without a window | Never reuse another conversation's refs | 7 |
| 13 | 165/166 | Writing a published note | Put old external numbers in titles and links | Use zet ids, titles, full SHA-256 only | 10 |
| 14 | 165/166 | Explaining the next approval | Promised a window that did not appear | Never promise a window | 6 |
| 15 | 165-167 | An unsent letter needs changes | Issued a new number, reused a number | Revise through compose; ledger for numbers | 9 |
| 16 | 168/169 | Writing the human's request into a letter | Softened the wording | Quote faithfully | 5 |
| 17 | 171 | Copying an id from a result | Used a plan hash as an objet id | Copy ids from the right field | 10 |
| 18 | 173 | Approving with `--reviewed-by` | Passed a bare name | `person:<id>` of the human who reviewed the plan | 6 |

## Model Choice

See `templates/ai-runtime/wom-archive/references/models-and-reasoning.md`. No
letter compared models directly; the guidance is a recommendation, not a
benchmark.
