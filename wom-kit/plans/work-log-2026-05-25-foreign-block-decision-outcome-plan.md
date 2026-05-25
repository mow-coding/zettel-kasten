# Work Log: v0.2.37 Foreign Block Decision Outcome Plan

Date: 2026-05-25

## Intent

Add a read-only planner after recorded foreign block quarantine decisions.

The user wanted the next layer to answer what safe path follows a recorded decision without accepting, trusting, importing, attesting, minting, anchoring, delegating, signing, applying, sharing, calling providers, or running ZET transport.

## Implementation

- Added `archive quarantine-decision-outcome`.
- Required `--dry-run` for CLI planning.
- Added `--case-id`, `--expected-decision`, `--reviewer`, and `--review-note`.
- Reused v0.2.36 decision review consistency checks for the recorded decision.
- Made the single-case planner stricter than the broad review index: missing decision receipt or original quarantine receipt blocks.
- Added read-only MCP `foreign_block_decision_outcome_plan`.
- Added tests for all four decision routes, dry-run guards, expected-decision mismatch, missing state, contradictory state, unsafe values, review-note redaction, no-write behavior, and MCP tool-surface boundaries.

## Boundaries

The command writes nothing and returns `would_change: []`.

It does not:

- accept quarantine decisions,
- grant trust,
- import foreign blocks,
- create attestations,
- mint,
- anchor,
- delegate,
- sign,
- execute foreign text,
- apply decisions,
- call provider APIs,
- run ZET transport,
- expose MCP write tools.

## Verification Plan

- `python -m unittest discover -s wom-kit\tests`
- `python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict`
- `python -m wom_kit.archive_cli doctor wom-kit\examples\fake-life-archive --strict`
- `git diff --check`
- naming and privacy scans requested for the batch.

## Pre-Merge Review Fixes

- Fixed the non-dry-run rejection path so structured output still reports `dry_run: true`, `outcome_status: planned_not_applied`, and `would_change: []`.
- Kept the CLI nonzero exit when `--dry-run` is omitted.
- Added a positive `--expected-decision` replay test.
- Added an invalid recorded decision test that confirms no stale outcome route or mutation flag is exposed.
- Renamed the outcome-plan note summary marker from `accepted_as_preview_context` to `accepted_as_context` for this tool only.
- Left duplicate blocker wording cleanup intentionally conservative; exact duplicate blockers are still deduplicated, but distinct review-index and planner-side blockers remain visible.
