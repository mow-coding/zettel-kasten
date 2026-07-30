# Decision Log — v0.3.289 Windows CI Time Budget

Date: 2026-07-30

## Context

The complete Windows suite normally approached the existing 45-minute GitHub
Actions timeout. An exact-source v0.3.288 tag job exhausted that budget on a
slow runner while tests were still progressing, although the same commit's
main workflow and complete local Windows suite had passed.

## Decision

Keep the complete test suite and stable check name. Keep Linux at 45 minutes
and raise only Windows to 75 minutes through a per-matrix timeout value.

Defer sharding until it is designed together with stable check aggregation or
branch-protection migration.

## Consequences

- Slow Windows runners have meaningful headroom without reducing coverage.
- Linux failure budgets do not expand.
- Existing check names and commands remain stable.
- v0.3.288 keeps its immutable tag and needs a documented exact-SHA timeout
  exception; the new budget starts with v0.3.289.

Detailed evidence is recorded in
`meeting-minutes/2026-07-30-v03289-windows-ci-time-budget.md`.
