# v0.3.287 Notion Locator Evidence Plan Implementation

Date: 2026-07-30

Branch: `codex/v0.3.287-notion-locator-evidence-plan`

Initial base: v0.3.286 candidate `6e3711ff59ba16b81b1699de9e8776bf2d48374a`

## User Intent

The user asked the release work to continue unattended and carefully, with the
remaining beta-tester and review backlog split into small public releases.
The outstanding Notion locator problem must be handled without guessing or
writing to the beta-tester archive.

## Hard Boundaries

- The beta-tester archive remained read-only and the new command was not run
  against it.
- This release adds a CLI-only, dry-run-only planner. It adds no writer,
  receipt, provider/API call, MCP tool, raw `recordMap` adapter, or
  `pages.index.jsonl` adapter.
- Private source page ids and locator strings may be read only from an
  archive-relative JSONL file below
  `.wom-scratch/notion-locator-evidence/`.
- Public JSON and text output must not echo the private join material, local
  paths, canonical ids, canonical hashes, or individual occurrence digests.

The full implementation contract is recorded in
`meeting-minutes/2026-07-30-v03287-notion-locator-evidence-plan-directive.md`.

## Implementation

The release adds:

- `notion_import_locator_evidence_plan` in `archive_services.py`;
- `archive notion-import-locator-evidence-plan` in `archive_cli.py`;
- a strict public JSON Schema for reviewed private occurrence evidence;
- exact nested `facets.source_page_id` joins with UUID-only normalization;
- exact current canonical SHA-256 selection for one-to-many fan-out;
- single-snapshot canonical hashing, UTF-8 BOM decoding, and frontmatter/body
  parsing;
- positive equal marker/frontmatter/evidence counts and bijective
  source-to-marker ordinal validation;
- bounded HTTP(S) locator validation without locator normalization or echo;
- bounded evidence and canonical reads, duplicate JSON-key rejection, path
  containment, and symlink/junction/reparse rejection;
- content-free row summaries, coverage aggregates, blocker-code counts, and
  one plan digest binding the private evidence snapshot and alignment inputs;
- public documentation, capability-matrix, runtime-route, release-note,
  version, and packaged-resource updates.

## Privacy Correction During Review

The first implementation returned the archive id as a conventional top-level
field. It was not needed by the evidence-plan output and may itself be a
name-like identifier, so it was removed from the public result. Archive
identity remains bound only inside the allowed single `plan_digest`.

The regression suite now asserts both that the `archive_id` key is absent and
that the fake archive id is not present in rendered output.

## Schema And Runtime Parity Correction

Runtime URL parsing accepts case-insensitive HTTP(S) schemes. The first public
schema pattern accepted only lowercase `http://` and `https://`. Source and
packaged schemas were corrected together to the ECMA-compatible pattern
`^[Hh][Tt][Tt][Pp][Ss]?://`, and resource synchronization plus schema tests
now enforce that parity.

## Independent Review Findings And Corrections

The first independent P1/P2 review reproduced five release-blocking defects.
The release was held and each defect was converted into a regression test
before the full suite was restarted.

1. A canonical-looking zet from a different archive could pass the Notion and
   status checks. Canonical reads now use the existing
   `validated_approval_zettel_snapshot` boundary, which binds the open file
   snapshot to a valid zet id, the current archive id, canonical readable
   status, and the canonical frontmatter schema.
2. The evidence and canonical readers compared only path metadata before and
   after reading. A test could replace the opened handle with a same-length
   file and have those different bytes accepted. Evidence now uses
   `lstat -> open/fstat -> bounded read -> fstat/lstat` generation checks, and
   canonical reads reuse the same established validated-snapshot pattern.
3. A quoted 5,000-digit omitted-count value could escape as `ValueError`.
   Unbounded or non-convertible counts now become the fixed
   `canonical_frontmatter_omitted_count_invalid` blocker, and the CLI command
   has a final generic exception boundary that never stringifies the error.
4. In the over-5,000-row branch, `blocker_code_counts` previously depended on
   how many safe rows `--max-items` returned. The count now reflects the full
   rejected row count and is invariant under output truncation.
5. Python's `urlsplit` is not a full URL validator, so malformed percent
   escapes such as `%`, `%ZZ`, and `/path/%ZZ` passed. Every percent escape
   must now be followed by exactly two hexadecimal digits.
6. The older census helper deliberately treated Boolean `true` as a count of
   one. Reusing that tolerant behavior in a strict alignment plan produced a
   false positive. The evidence plan now has its own strict extractor: when a
   known omission-count field is present, exactly one must contain a
   non-Boolean integer within the bounded range. Strings, Booleans, duplicate
   declarations, negative values, and oversized values block instead of being
   coerced.
7. The first strict extractor also treated a missing count as corrupt for
   every Notion canonical. That incorrectly blocked an otherwise valid
   marker-free, unaffected canonical. A missing count is now distinguished as
   zero: it is harmless when the body has no omission marker, while an
   affected selected zet still fails the downstream positive-count and
   marker/count equality gates.

Strengthening canonical schema validation also exposed that the test fixture
omitted the required `provenance.derived_from` and
`visibility.allowed_archives` arrays. The fixture was repaired instead of
weakening production validation.

## Verification So Far

- focused evidence-plan CLI/schema:
  `21 passed, 259 subtests passed`;
- runtime routing and MCP non-exposure:
  `3 passed, 12 subtests passed`;
- capability, package-resource, public privacy, public link, and release
  readiness tests:
  `175 passed, 3904 subtests passed`;
- complete staged source suite:
  `1761 tests passed, 19 environment-dependent skips, 0 failures`;
- final independent P1/P2 review after all seven corrections:
  no remaining actionable finding;
- `python wom-kit/tools/check_release_readiness.py`: all four gates passed;
- `python wom-kit/tools/sync_package_resources.py --check`:
  102 files synchronized for v0.3.287;
- `py_compile`: passed;
- staged and unstaged `git diff --check`: passed.

One initial package-resource test invocation imported the user's existing
editable installation from the main worktree and reported two wrong-root
assertions. This was a local test-environment contamination, not a product
failure. Re-running with this worktree's `wom-kit/src` explicitly first on
`PYTHONPATH` produced the green 175-test result above.

## Python 3.10 JSON Depth Classification Correction

PR CI exposed one cross-version classification difference in the valid
1,200-level nested JSON regression. Python 3.12 decoded that row and allowed
WOM's explicit 32-level structural limit to return
`row_json_depth_or_node_limit_exceeded`. Python 3.10 raised `RecursionError`
inside `json.loads` first. The original shared exception handler classified
that parser guard as `row_json_invalid`.

Parser `RecursionError` now maps directly to the same content-free
`row_json_depth_or_node_limit_exceeded` blocker. JSON syntax/value failures
remain `row_json_invalid`. A direct regression injects the earlier-decoder
behavior so the branch is exercised even on Python 3.12, without retaining or
echoing the exception text or private row content.

Correction verification: all 20 CLI evidence-plan tests plus the direct
decoder-recursion regression passed on Python 3.12; `py_compile` and
`git diff --check` also passed.

## Pending Release Gates

- exact reparenting onto the eventual v0.3.286 merge commit if needed;
- clean exact-commit wheel verification;
- PR, exact main and tag CI, public Release, unauthenticated download, fresh
  install, four entry points, onboarding, and strict Doctor.

No pending gate is claimed complete in the v0.3.287 release note.
