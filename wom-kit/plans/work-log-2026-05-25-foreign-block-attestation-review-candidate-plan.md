# Work Log: v0.2.38 Foreign Block Attestation Review Candidate Plan

Date: 2026-05-25

## Intent

Add a read-only planner after v0.2.37 decision outcome planning.

The user wanted a safe layer that answers what a human could review next when a recorded quarantine decision is `eligible_for_attestation_review`.

## Implementation

- Added `archive attestation-review-candidate`.
- Required `--dry-run` for CLI planning.
- Added `--case-id`, `--expected-decision`, `--expected-outcome`, `--prospective-attestor`, `--review-scope`, and `--review-note`.
- Reused v0.2.37 outcome planning so the current case, original quarantine receipt, decision record, and decision receipt are re-read before a candidate is returned.
- Required the recorded decision to be `eligible_for_attestation_review`.
- Required the planned outcome to be `prepare_attestation_review_candidate`.
- Added read-only MCP `foreign_block_attestation_review_candidate_plan`.
- Added CLI and MCP tests for dry-run guards, eligible and ineligible decisions, replay mismatches, unsafe values, missing state, contradictory state, mutation flags, no-write behavior, and MCP tool-surface boundaries.

## Boundaries

The command writes nothing and returns `would_change: []`.

It does not:

- accept quarantine decisions,
- grant trust,
- import foreign blocks,
- create attestations,
- create signatures,
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

- Changed blocked candidate output so `ok: false` returns `candidate_status: blocked_not_planned` and `attestation_review_candidate: null`.
- Kept the valid eligible path unchanged: `ok: true` still returns a populated candidate with `candidate_status: planned_not_recorded`.
- Added tests that ineligible decisions and contradictory records do not emit populated candidate packets.
- Added review-scope tests for scope-appropriate missing human checks.
- Added evidence privacy checks for raw note/body non-disclosure and hash commitment labels.
- Left duplicate ineligibility blocker cleanup intentionally conservative; distinct outcome-plan and candidate-plan blockers remain visible.
- Confirmed retained SHA-256 values may appear as non-secret commitments only when labeled `not_verified`, `not_trusted`, or not proof of authenticity; no new full source hashes are calculated.
