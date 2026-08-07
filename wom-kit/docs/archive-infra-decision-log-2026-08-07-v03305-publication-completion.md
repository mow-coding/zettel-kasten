# Archive infrastructure decision log: Publication completion must be observable

Date: 2026-08-07

## Context

A real-use incident showed that several human publication requests could leave
only incomplete and duplicate inbox files when an AI bypassed `create-draft`
and never ran `mint-zet`. The correct mint blocker was therefore never visible,
and later sessions had no default signal that publication remained unfinished.

## Decision

- Require explicit safe abstract and non-empty facets before the official AI
  draft route can write.
- Run a bounded, frontmatter-only same-title inbox check during draft creation.
  Block AI duplicates; warn human-owned rough-draft flows without guessing
  semantic identity.
- Reuse the existing bounded inbox pipeline audit inside `ai-start-here` and
  expose a content-free unpublished count, oldest age, pipeline-shape concern
  count, and publication-readiness-gap count at every session start.
- Define publication completion as an approved mint with canonical and receipt
  evidence. A publication request starts mint preview; blockers or remaining
  approval must be reported immediately.

## Consequences

The CLI cannot police arbitrary external filesystem writes, so the solution is
layered across runtime instructions, creation-time validation, startup
visibility, and response integrity. No draft is automatically repaired,
discarded, minted, or semantically merged. Human-owned rough drafts remain
available, and no title, path, id, body, actor, or source value is exposed by
the new checks.
