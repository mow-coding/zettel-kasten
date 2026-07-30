# v0.3.288 MCP Content-Free Error Envelope Implementation

Date: 2026-07-30

Branch: `codex/v0.3.288-mcp-content-free-error-envelope`

Initial base: v0.3.287 candidate
`3a36d4e9e8c296d19e5d0246d30e12aae71bc7bc`

## User Intent

The user asked WOM development to continue unattended and carefully through
the remaining beta-tester and review backlog. Work remains split into small
public releases with verification and an independent review between
implementation and publication.

## Selected Problem

The shared stdio MCP boundary exposed raw exception messages in tool and
JSON-RPC errors. This release fixes that systemic privacy boundary before
adding more MCP features.

The complete implementation contract is recorded in
`meeting-minutes/2026-07-30-v03288-mcp-content-free-error-envelope-directive.md`.

## Hard Boundaries

- The beta-tester archive remains read-only and is not accessed.
- This release adds no tool, command, writer, migration, provider call, model
  call, credential-store call, or network call.
- Existing dry-run, approval, allowed-root, redaction, and no-write checks
  remain active.
- Internal exception chaining may remain, but raw details must not cross the
  MCP wire boundary.

## Implementation Plan

1. Replace caller-supplied tool error text with one exact content-free
   envelope.
2. Normalize JSON-RPC failure messages to five fixed categories.
3. Reject falsey non-object `params` and `arguments`.
4. Migrate raw-text-dependent MCP tests to exact-envelope equality while
   retaining safety assertions.
5. Add sentinel privacy and protocol-shape regressions.
6. Update version, public documentation, release notes, and packaged
   resources.
7. Run focused, full-suite, independent-review, release-readiness, resource,
   and clean-wheel gates.

## Work Log

- Created a dedicated v0.3.288 worktree from the exact v0.3.287 candidate.
- Recorded the directive before production and test implementation began.
- Assigned production and MCP test changes to separate reviewers so their
  diffs can be combined and independently checked.
- Changed the shared MCP tool-error result to one exact content-free envelope.
- Normalized the five JSON-RPC error categories to fixed messages.
- Changed request `params` and tool `arguments` so only `null` becomes `{}`;
  every other non-object value is invalid.
- Migrated 92 existing raw-error-text assertions to exact-envelope equality
  while retaining the adjacent no-write, approval, dry-run, allowed-root, and
  redaction assertions.
- Added direct tool, service, unexpected-exception, unknown method/tool,
  invalid request, and invalid parameter sentinel regressions.
- Updated version, public documentation, release notes, capability evidence,
  and deterministic packaged resources.

## Independent Review Findings And Corrections

The first combined implementation passed its focused tests, but independent
adversarial review reproduced seven release-blocking protocol and privacy
gaps. The release was held, and every finding was converted into a regression
before the candidate returned to the full test gate.

1. A syntactically valid but 5,000-level-deep JSON value raised
   `RecursionError` outside the `JSONDecodeError` handler. The process exited
   and Python printed a traceback with local paths to stderr. Unexpected parse
   implementation failures now return fixed `Internal error` with id `null`
   and the server continues to the next line.
2. Invalid request objects without an id were classified as notifications and
   received no `Invalid Request` response. Object, array, Boolean, and
   non-finite ids were also echoed back, including nested sentinel paths.
   Request shape and id validity now precede notification classification.
   Only `null`, string, non-Boolean integer, and finite float ids are accepted;
   invalid requests return fixed `Invalid Request` with id `null`.
3. A valid JSON string id containing an escaped lone surrogate caused strict
   stdout encoding to fail and print a traceback. Wire serialization now uses
   ASCII-safe JSON escapes while preserving the decoded JSON value.
4. Invalid UTF-8 bytes raised `UnicodeDecodeError` in text-stream iteration
   before the line handler. The server now reads raw stdin bytes when
   available, decodes each line as strict UTF-8 inside the boundary, returns
   fixed `Parse error`, and continues to the next request.
5. A closed stdout reader or a write/flush failure produced a traceback and a
   second CPython shutdown-time stream error. Wire writes now return a safe
   completion signal; a failed real stdout is replaced with a no-op sink and
   the server exits quietly because no response channel remains. A
   non-serializable server result is replaced with fixed `Internal error` and
   does not stop later requests.
6. Python's permissive JSON defaults accepted `NaN`, `Infinity`,
   `-Infinity`, and an overflowing `1e400`, while output serialization could
   emit non-standard `NaN`/`Infinity` tokens. Input now rejects those values
   as fixed `Parse error`; output uses `allow_nan=False` and converts an
   invalid server result to a fixed failure.
7. An unexpected exception during a valid `tools/call` became JSON-RPC
   `Internal error`, contradicting the documented exact failed-tool envelope.
   Unexpected executed-tool failures and non-serializable tool results now use
   the same exact `tool_execution_failed` envelope. Unexpected non-tool server
   method failures remain fixed JSON-RPC `Internal error`.

## Verification Status

Completed local gates so far:

- exact-envelope migration: 92 former raw-text assertions, 0 remaining known
  raw tool-error-text assertion;
- focused adversarial boundary regressions: 14 passed after the final
  corrections;
- complete MCP test file: 155 tests passed;
- package-resource and capability/public documentation subset: 176 tests
  passed;
- complete staged source suite: 1,775 tests passed, 19
  environment-dependent skips, 0 failures in 1,050.469 seconds;
- resource synchronization: 102 files for v0.3.288;
- `py_compile`, staged/unstaged `git diff --check`: passed;
- independent P1/P2 code and test review after all corrections: no remaining
  finding;
- initial candidate commit:
  `7a99931e40cf94f070229384039e844eca5d5ed1`;
- clean candidate wheel:
  `wom_kit-0.3.288-py3-none-any.whl`, 1,205,792 bytes,
  SHA-256
  `9fcb35bd2ff4b3f939d770b429ee712caac9015993e44374a44463cf069aac45`;
- clean-wheel contents and lifecycle: 102 manifested resources, 117 wheel
  files, all four entrypoints, runtime Agent Skill lifecycle, onboarding
  preview/write, and strict Doctor passed;
- preserved local candidate artifact:
  `C:\Users\mylifeisbusy\Documents\dev\zettel-kasten-release-artifacts\v0.3.288-candidate-7a99931e`.

This evidence update follows the initial product candidate commit. The
supervisor must rerun the clean-wheel gate on the final evidence-bearing tree
before treating it as the exact PR candidate.

Remote PR, CI, merge, tag, GitHub Release, public artifact, and beta
validation remain pending and are not claimed here.
