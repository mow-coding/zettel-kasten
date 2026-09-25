# Decision Log: Helper-AI Guidance Core Card (v0.4.45)

Date: 2026-09-25
Status: implemented in v0.4.45 (candidate)

## Owner Request

The owner observed that beta feedback has shifted from "a command is blocked"
to "the helper AI (Claude or Codex) does not follow WOM's rules". WOM has many
commands; the development team's job is to condense the guidance so a helper
AI understands it quickly, and to say which provider, model and reasoning
level suits WOM work.

## Evidence

A read-only review of beta letters 150-173 found about thirty cases of a helper
AI breaking, skipping or over-applying a rule. By frequency: direct file or
runtime edits, update and recovery procedure (backgrounded or repeated
approvals, a global `archive` instead of the project launcher), letter writing,
reading results (approving with blockers, reporting unverified state), session
scope and grants (reusing another conversation's refs, "all sessions" backups
and uploads), command choice, reviewer format, and legacy numbering. No letter
compared models, and none could state the reasoning level used.

The guidance itself contributed:
- `capture-draft-and-publication.md` said "revise it in place" while the skill
  forbade hand edits; `draft-revision-write` existed but was not named.
- `operator-contract.md` "Carry established state" listed "permissions granted",
  which matched the reuse of another conversation's grant.
- The launcher rule, foreground approvals, re-running `ai-start-here` after a
  context reset, letter numbering and fidelity, and the legacy-id rule were
  missing or buried in a 1,256-line reference.

## Decision

1. `SKILL.md` leads with a twelve-rule core card and an intent-to-command
   table; every command in the table is checked against the parser.
2. Long, rarely needed detail moves verbatim into focused references:
   `credentials-and-sessions.md` (provider credential popup facts and session
   grant rules), `long-operations-and-updates.md` (the previous "Long
   Operations And Updates" section plus launcher and foreground rules). New:
   `developer-letters.md` and `models-and-reasoning.md`.
3. The two contradictions are fixed.
4. `docs/ai-guidance-scenarios.md` turns eighteen letter cases into a manual
   evaluation set; `test_ai_guidance_core_rules` keeps the card, table,
   references and scenarios consistent. CI does not run a model, so model
   behavior remains unmeasured.
5. Model guidance is labeled a recommendation: strongest available model and
   high reasoning for any approval, update, recovery, cleanup, backup,
   credential or provider task; small or fast models only for read-only work;
   one task per session and `ai-start-here` after compaction.

Historical release tests that pinned operating tokens to `SKILL.md` now bound
`SKILL.md` itself and look for those tokens anywhere in the runtime package.

Recorded by Claude (Opus 5.5) under the owner's request.
