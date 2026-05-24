# Work Log: v0.2.28 Foreign Block Intake Preview

Date: 2026-05-25

## Intent

Add the next safe ZET-sharing step after block header preview: a read-only intake preview for foreign/shared blocks.

The feature is intentionally inspect-only.

## Implemented

- Added CLI `foreign-block`.
- Added service-layer `foreign_block_intake_check`.
- Added read-only MCP `foreign_block_intake_check`.
- Added conservative block-header JSON intake.
- Added Markdown-compatible foreign zet intake.
- Added claimed hash summaries marked `not_verified`.
- Added prompt-boundary recommendations without executing foreign text.
- Added tests for JSON artifacts, Markdown artifacts, invalid JSON, unsafe paths, unsafe refs, MCP dry-run behavior, and MCP tool surface.

## Safety Decisions

- Foreign artifacts remain `untrusted_foreign`.
- Claimed hashes are not treated as proof.
- Full body text is not echoed for Markdown-compatible foreign zets.
- Unsafe local paths, provider locators, and secret-like strings are redacted or blocked.
- Prompt-injection-looking foreign text becomes a warning/recommendation, not a command.
- No files are written.

## Not Implemented

- No real ZET transport.
- No foreign block import/apply/trust path.
- No draft creation from foreign content.
- No minting, attesting, or anchoring foreign content.
- No provider sync.
- No OCR.
- No LLM classification.
- No signing, payment, staking, consensus, ledger, blockchain, or full-auto behavior.

## Pre-Merge Review Fixes

- Added CLI `--stdin` regression coverage for Markdown-compatible foreign zet text.
- Added CLI `--stdin` coverage for prompt-injection-looking text.
- Added CLI `--stdin` coverage for JSON block header artifacts with claimed hashes kept `not_verified`.
- Added CLI coverage for omitting `--dry-run`.
- Added CLI coverage for malformed claimed hash shape.
- Strengthened MCP `foreign_block_intake_check` so `dry_run` must be the boolean value `true`; truthy values such as `"yes"` or `1` are rejected.
