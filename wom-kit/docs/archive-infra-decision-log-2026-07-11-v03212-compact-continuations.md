# Decision Log: v0.3.212 Compact Continuations

Date: 2026-07-11
Status: implemented

## Decision

Require a full cursor-zero response, then allow an opt-in `continuation`
response profile on later strict pages. Omit only repeated scope-wide
diagnostics while retaining items, coverage, snapshot, token, chain evidence,
session consistency, and safety fields.

## Context

Large exhaustive passes repeat diagnostic metadata hundreds of times. Removing
items or relying on top-k retrieval would violate WOM's node-first coverage
rule. Keeping every field forever, however, spends host context on diagnostics
already observed on the first page.

## Consequences

- Existing calls remain full by default.
- Cursor zero and non-strict calls reject the continuation profile.
- Response profile is intentionally not continuation-token-bound, so the host
  can switch between full and compact responses without changing node order.
- Scope-wide gap details stay on the required first page; completion readiness
  booleans remain on every page.
- Response measurements are calculated after profile shaping.
- No archive migration, node rewrite, generated map, provider call, or
  persistent WOM goal/loop state is introduced.
