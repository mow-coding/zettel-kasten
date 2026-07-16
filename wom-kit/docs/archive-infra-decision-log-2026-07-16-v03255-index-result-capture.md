# Archive Infra Decision Log - v0.3.255 Index Result Capture And Crash Safety

Date: 2026-07-16
Status: accepted for v0.3.255 after local engineering and release verification

## Context

The basoon v0.3.254 real-use report confirmed a canonical mint, its receipts,
the retired draft, and the removal of the inbox draft. The subsequent
`archive index` and two `archive index-health` attempts each returned from the
agent execution boundary after roughly 25 to 28 seconds without usable stdout,
stderr, or a captured exit code. The reporter correctly stopped rather than
claiming that the final index was current.

A later official read-only `index-health` run took roughly 90 seconds and then
returned a complete result with exit code 1:

```text
live_zettel_count: 8,586
indexed_zettel_count: 0
missing_from_index_count: 8,586
```

This result established that output capture loss and generated-index loss were
separate problems. Code inspection found the destructive boundary: the index
setup script could durably delete existing rows before the later Python insert
loop committed. Python `sqlite3.Connection.executescript()` commits any pending
transaction before executing its script and does not implicitly wrap the later
statements and Python inserts in one transaction. Interruption could therefore
leave a valid SQLite file with an empty zettel index.

## Decision

1. Add opt-in `--progress` to `archive index` and `archive index-health`.
   Progress goes only to stderr, contains only fixed stage labels and safe
   counts, and emits a 10-second heartbeat. The final result stays on stdout
   when `--output` is not used.
2. Add opt-in `--output .wom-scratch/diagnostics/*.json` to both commands.
   The full JSON is published only at a complete result boundary; stdout becomes
   a compact completion summary.
3. Reject path traversal, symbolic links, Windows reparse points, and
   preexisting destinations before command work. Publish through a unique,
   flushed private partial with atomic no-overwrite semantics, so concurrent
   attempts have exactly one winner. Result files are private local scratch
   diagnostics, not WOM records, receipts, canonical evidence, or files to
   commit.
4. Include `cli_output_artifact` and `cli_execution` in the saved result.
   `cli_execution` always records `status`, `exit_code`, `started_at`,
   `finished_at`, and nullable `error`.
5. Define `status: completed` as saved command-result completion, not command
   success or proof of later terminal delivery. Record
   `exit_code_scope: command_result_before_terminal_transport`; operators must
   use that code together with the command's `ok` or `index_state` result.
   Terminal progress/summary I/O is best-effort once durable capture is in use
   and cannot change database or command-result meaning.
6. Make the SQLite rebuild one explicit transaction. Start it with
   `BEGIN IMMEDIATE` inside the setup script, then include schema work, old-row
   deletion, every new insert, and metadata updates through the existing final
   commit. An exception or process loss before that commit rolls the rebuild
   back and preserves the previously committed index.
7. Keep `index-health` read-only and never let it trigger an automatic rebuild.
   The official procedure is health first, index only for a missing or stale
   result, then health again.

## Completion And Failure Boundaries

- A forced termination before publication has no complete scratch result.
  Absence means unconfirmed, not success. Termination after publication can
  leave the complete result even when no terminal summary is displayed.
- A completed nonzero command may have a scratch result. The nonzero exit code
  remains authoritative.
- A rebuild failure before SQLite commit preserves the prior committed index.
- If the interrupted operation was the first build and no prior schema exists,
  the small SQLite file may remain. `index-health` classifies that file as
  `archive_index_schema_incomplete` / `stale_or_incomplete` rather than raising
  an unstructured missing-table error.
- SQLite commit and scratch publish are separate. If commit succeeds but result
  capture fails, the new index may already be installed. Run a fresh
  `index-health` with a new output filename before deciding whether to rebuild.
- A preexisting output destination is never overwritten or treated as evidence
  from the new invocation.
- Handled failure artifacts contain only a fixed error type/code; raw parser
  excerpts and local paths are not stored or printed in captured mode.
- A well-formed health scan stops at the frontmatter boundary. If malformed
  delimiters require body bytes to establish that the boundary is invalid, the
  privacy guard reports that read instead of claiming `false`.

## Official Operator Procedure

1. Run read-only `index-health` with `--progress` and a new diagnostic output
   filename.
2. If its completed result has exit code 0 and reports `index_state: current`,
   stop. Do not rebuild.
3. If it reports a missing or stale index, run `archive index` with progress and
   a different new diagnostic filename.
4. Judge that command from its saved `cli_execution.exit_code` and result.
5. Run `index-health` again with another new filename. Only this final health
   result can confirm currentness within the documented health-check scope.

Approved mint already has an index-update fast path. Therefore a successful
mint does not authorize an unconditional full rebuild.

## Rejected Alternatives

- Do not treat an agent wrapper's `process completed` message as CLI success.
- Do not infer success from an absent result file.
- Do not automatically rebuild from `index-health`.
- Do not overwrite, append to, or publish partial scratch results.
- Do not promote local diagnostics into WOM receipts or canonical records.
- Do not print archive paths, zet ids, titles, or body content as progress.
- Do not use direct SQLite inspection as the ordinary success procedure.
- Do not swap a temporary SQLite file into place. On Windows, WAL and
  shared-memory sidecars make that design less direct than one SQLite-managed
  crash-safe transaction.

## Implementation And Verification Plan

1. Reuse the shared compact progress reporter and scratch-output writer.
2. Instrument both commands with content-free stage/count events and heartbeat
   tests that also prove stdout/stderr separation.
3. Validate output paths before index work and cover traversal, extension, and
   preexisting-file refusal.
4. Add execution-envelope tests for successful, completed nonzero, and forced
   termination boundaries.
5. Add a regression that interrupts or raises after deletion has begun and
   proves that the previously committed index remains intact.
6. Prove that a completed rebuild replaces all generated rows and that a fresh
   `index-health` reports the expected live/indexed equality.
7. Run focused CLI/service tests, documentation contract tests, and the full WOM
   suite for the v0.3.255 release. The basoon archive follow-up remains
   real-use validation and must not be claimed by unit tests alone.

## Primary References

- Python
  [`sqlite3.Connection.executescript()`](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.executescript)
  documents the explicit-script transaction boundary that exposed the
  delete-only state.
- SQLite [Transactions](https://www.sqlite.org/lang_transaction.html)
  documents the `BEGIN IMMEDIATE` transaction used for the rebuild.
- Python [`os.fsync()`](https://docs.python.org/3/library/os.html#os.fsync),
  [`os.rename()`](https://docs.python.org/3/library/os.html#os.rename), and
  [`os.link()`](https://docs.python.org/3/library/os.html#os.link) document the
  complete-only no-overwrite result publication primitives.

## Consequences

- Long commands expose liveness without leaking archive content or corrupting
  machine-readable stdout.
- Operators can retain a bounded, durable local result across chat or PTY output
  loss while keeping success semantics explicit.
- An interrupted rebuild can no longer publish the delete-only intermediate
  state as the current generated index.
- The design adds no auto-repair daemon, persistent progress log, canonical
  receipt type, or broader `index-health` inspection scope.
