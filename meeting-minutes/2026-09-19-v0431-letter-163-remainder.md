# v0.4.31 — beta letter 163 remainder (hints, edge warnings, explanations, preflight cause, index pre-announce)

Date: 2026-09-19 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for implementation,
tests, docs and the bump; a bounded read-only Ultracode workflow (9 agents,
`wf_24f23d02-f97`) produced the map, the unit design and two adversarial
verdicts. Standing approval from the user to work through the backlog.

## Client reply

The user sent the one combined reply (v0.4.30 갱신본: install command,
restore/offload, the letter-163 answers, the three commands that close the
27 started claims, the index-rebuild question) to the client on 2026-09-19
after v0.4.30 was public, per the user's decision to send one letter rather
than three. Nothing sets a letter's `resolved_in` until the client reports.

## Units (all synthetic fixtures)

1. Create-draft hints (⑦a/c): `ai_draft_assisted_by_required` + option
   names; `omit_when_null` on handoff arguments; `--profile-id` entry;
   `create_draft_replay_value_null_literal` guard.
2. Edge-target gating (11): `edge_target_discarded` / `edge_target_missing`
   warnings; `discarded` requires a discard receipt for an absent target.
3. Warning explanations (⑪): `quality_check.warning_explanations` with
   detector, rule, marker counts, body lines; text renderer prints counts.
4. Preflight cause (②): `project_version_update_failure_family_<family>`
   (`cause_code_source: exception_family`) for non-broker failures; the
   except tuple gains `ProjectRuntimeError` and
   `LegacyProjectUpdateRecoveryError`; `existing_transaction` on the
   terminal-cleanup / outcome-unknown / legacy-recovery gates.
5. Index pre-announce (⑧ 8a): `archive_index_precheck`; `index_precheck` on
   zettel-edge, revert-edge and intake-chain plans; rebuild commands in
   `next_safe_actions`.

Deferred with reasons in the decision log: 8b/8c incremental index, scratch
classifier, record_type registry, session refs (coverage targets moved to
v0.4.32).

## Verification

`test_v0431_letter163_remainder` (8), plus the mint/edge/create-draft/
project-update cohorts and the v0.4.30 modules; the pin sweep and the full
CI run on the candidate.
