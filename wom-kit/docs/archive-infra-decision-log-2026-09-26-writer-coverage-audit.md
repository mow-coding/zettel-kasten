# Decision log: writer-session coverage audit (2026-09-26)

## Context

`tools/check_writer_session_coverage.py` still listed 29 approval-available
writers as `pending`. The count was carried from v0.4.21 (LR-06). Since
v0.4.36 (letter 168), the exact approval broker resolves the work-session grant
from the environment refs whenever a caller leaves `session_permission` unset,
and every operation kind is grantable. The owner delegated follow-up work on
2026-09-25, and this audit checked whether each pending writer already uses
that route.

## Findings

- 28 writers already send `--approve` through a broker entry point, and nothing
  on the path forces a dialog. Some reach it from the CLI, some through a
  module-level executor, and some through a writer chosen into a variable.
  The only function that passes `session_permission=None` is onboarding,
  because no archive or grant exists yet.
- `credential-adopt` opens the secure window in which the person enters the
  provider secret. No grant can supply a secret.

## Decisions

1. The 28 writers become `session_integrated` with `route: environment`. The
   evidence is `test_writer_session_environment_routes` (traced route, no
   forced dialog, onboarding as the only forced dialog) plus
   `test_v0436_letter168` (runtime grant skip).
2. `credential-adopt` becomes a `legacy_exception`. This is **not** an
   exclusion from the 2026-09-17 decision that a grant covers every approval
   dialog: the window collects a secret and is not an approval. If the owner
   wants a stored-secret reuse path, that is a separate feature.
3. The checker now reports 0 pending and a complete all-writer scope. This
   covers the grant route only; customers' own runs remain unconfirmed.

## Boundaries

No writer behaviour changed. No new session-ref options were added. The
static trace is a reachability proof over module-level functions. It is not a
runtime execution of each writer.
