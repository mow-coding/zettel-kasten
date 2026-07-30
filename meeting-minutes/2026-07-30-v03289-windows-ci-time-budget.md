# v0.3.289 Windows CI Time-Budget Record

Date: 2026-07-30

## Context

The v0.3.288 tag workflow ran the exact source commit
`41440e6949d4b4a9a84a0a62744f5f90dfafe649`. Its Linux jobs and release
readiness gate passed. The Windows job reached the workflow's 45-minute
timeout while it was still making progress through `test_mcp_server.py`; the
recorded interruption was a job cancellation, not a test assertion failure.

The same exact commit had already passed the complete main-branch workflow in
GitHub Actions run `30517031159`, including the Windows job. The exact source
also passed the complete local Windows suite before tagging.

Recent successful Windows test steps took approximately 36.57 to 44.28
minutes. On the slower tag runner, the observed MCP rate implied a complete
runtime of approximately 51 to 55 minutes. The old budget therefore had no
reliable hosted-runner headroom.

## Decision

Starting with v0.3.289:

- keep both Linux full-suite jobs at 45 minutes;
- give only the Windows full-suite job 75 minutes;
- preserve the existing full `unittest discover` command;
- preserve the existing job/check name; and
- defer Windows sharding.

The matrix now carries an explicit timeout for every included platform and
the job reads `matrix.timeout-minutes`.

## Why Not Shard Now

Sharding could reduce wall-clock time, but it would create two Windows check
contexts instead of one. That requires coordinated branch-protection or an
aggregator design if the check becomes required. The current release problem
is a time-budget defect, not missing coverage, so a Windows-only timeout is
the smallest standard correction.

## Release Consequence

The change cannot retroactively alter the workflow embedded in the v0.3.288
tag. The v0.3.288 release decision must therefore cite exact-SHA main CI,
local full-suite evidence, and the tag-timeout exception without moving the
tag. v0.3.289 and later tags receive the corrected budget.

No beta archive was read or written for this correction.
