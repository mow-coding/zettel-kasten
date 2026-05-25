# Work Log: v0.2.29 Foreign Block Trust Preview

Date: 2026-05-25

## Intent

Add the next safe ZET-sharing step after foreign block intake: a read-only trust / attestation preview.

The feature consumes a foreign-block intake report. It does not read the original foreign artifact again.

## Implemented

- Added CLI `foreign-block-trust`.
- Added service-layer `foreign_block_trust_preview`.
- Added read-only MCP `foreign_block_trust_check`.
- Added report validation for v0.2.28 `foreign_block_intake` outputs.
- Added `proposed_trust_action` values: `reject`, `manual_review_required`, and `eligible_for_future_attestation`.
- Added hash, reference, and prompt-boundary assessments.
- Added tests for valid reports, blocker reports, prompt warnings, Markdown intake reports, tampered reports, stdin input, invalid JSON, unsafe paths, and MCP dry-run guards.

## Safety Decisions

- Foreign blocks remain `untrusted_foreign`.
- Trust preview never creates trust.
- Attestation preview always has `would_attest: false`.
- Claimed hashes remain `not_verified`.
- The original foreign artifact is not re-read.
- No files are written.

## Not Implemented

- No real trust/apply/import.
- No attestation writes.
- No minting, anchoring, or delegation.
- No real ZET transport.
- No signing, payment, staking, consensus, blockchain, wallet key management, provider sync, OCR, LLM classification, or full-auto execution.

## Pre-Merge Review Fixes

- Added MCP path-based `foreign_block_trust_check` coverage for archive-relative intake reports.
- Added CLI regression coverage that a claimed hash with `verification_state: "verified"` is rejected.
- Added CLI regression coverage that unsafe values inside the intake report are rejected without echoing the unsafe value.
- Added CLI clean-failure coverage for bad claimed hash shape, empty stdin, and empty JSON.
- Added MCP clean-failure coverage for an empty structured `intake_report`.
- Replaced the trust-preview report text assertion with an explicit blocker path.
