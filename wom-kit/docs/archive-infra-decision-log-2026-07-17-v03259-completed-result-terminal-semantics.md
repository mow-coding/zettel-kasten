# Archive Infra Decision Log - v0.3.259 Completed-Result Terminal Semantics

Date: 2026-07-17

Status: accepted for v0.3.259 implementation and release

## Context

The v0.3.255 complete-only `--output` path protects unattended `index` and
`index-health` results from terminal loss. The independent Fable5 follow-up
found one narrower path outside that explicit capture mode: after `index` had
successfully committed, the ordinary no-`--output` JSON/text print and final
flush could raise `BrokenPipeError`, `UnicodeError`, or `ValueError`.

The database was already complete and `index-health` reported `current`, but
the Python exception escaped the CLI and made the caller observe an abnormal
termination instead of the computed command result. The same final-delivery
pattern existed for a completed no-`--output` `index-health` result.

## Decision

1. v0.3.259 changes only final terminal delivery after `index` or
   `index-health` has computed its result and no durable `--output` path was
   requested.
2. JSON keeps the existing `print_json()` serializer through
   `best_effort_terminal_json()`. Text keeps the same lines, order, wording,
   and final newline through `best_effort_terminal_print()`.
3. Terminal transport failures covered by the existing helper (`OSError`,
   `UnicodeError`, and `ValueError`) do not override the computed result code.
   This includes broken pipes, closed streams, and console encoding failures.
   A failed standard stream is replaced with a discard-only sink so CPython's
   interpreter shutdown cannot flush the broken stream again and replace the
   process result with exit code 120. The same neutralization applies when
   optional progress first observes a failed stderr transport.
4. Exit 0 remains exit 0. A completed quarantining rebuild or
   stale/incomplete health result remains exit 1. Terminal loss never changes
   a nonzero completed result into success.
5. `KeyboardInterrupt`, `SystemExit`, and failures before a result exists are
   not swallowed. The change is not a global exception boundary.
6. The complete-only `--output` writer, result schemas, archive/index schemas,
   normal CLI content, progress transport, and service logic do not change.
7. A missing terminal message is not durable evidence. Unattended runs should
   still use the reviewed archive-relative `--output` path.

## Verification Contract

- A regression first reproduces a committed and healthy index followed by an
  escaping broken-pipe exception on released v0.3.258 behavior.
- With both stdout and stderr broken, no-`--output` JSON `index` and
  `index-health` preserve completed exit 0 and the index remains `current`.
- With both streams broken, no-`--output` text `index` with quarantined zets
  and its stale/incomplete `index-health` preserve completed exit 1.
- Real child-process regressions close the parent side of stdout or stderr and
  assert the operating-system return codes: successful index 0, quarantining
  index 1, successful progress index 0, and current progress health 0.
- Existing durable-output, post-commit progress, sanitized-error, normal
  JSON/text, and index-health regressions remain green.
- Independent read-only review must find no P0/P1/P2 or scope blocker before
  versioning.

## Independent Review Outcome

The first in-process review found no P0/P1/P2, and one reviewer asked that an
unrelated catalog observation test be removed; the scope was narrowed. A final
actual-process audit then found that CPython re-flushed the failed stream at
interpreter shutdown and changed both completed 0 and 1 results to exit 120.
Publication and the running full suite were stopped. The implementation now
neutralizes only a standard stream that has actually failed, and a real
subprocess regression exercises closed stdout and progress stderr. Re-review
exercised success, quarantine, stale/incomplete, progress, shared-stream, JSON,
and text subprocess cases and found no remaining P0/P1/P2.

The final local release gate passed 1,517 tests with 13 skips and 4,226 passing
subtests in 11 minutes 14 seconds. Public-link, Korean product-language,
public-privacy, runtime-skill, packaged-resource, version-consistency, and
staged-diff checks also passed.

## Consequences

Callers can trust the computed process result after `index` or `index-health`
finishes even when the terminal transport disappears. They still cannot infer
that the human saw any text, and a no-`--output` run still has no durable result
artifact. The release deliberately does not add relative-path text output,
change MCP error handling, strengthen wheel-manifest byte binding, or reopen
the quarantined mutation-engine research checkpoint.
