# Work Log: v0.2.31 Foreign Block Quarantine Plan

Date: 2026-05-25

## Intent

Add the next safe ZET-sharing step after foreign block attestation packet preview: a read-only quarantine plan.

The feature consumes a foreign-block attestation packet preview. It does not read the original foreign artifact again.

## Implemented

- Added CLI `foreign-block-quarantine`.
- Added service-layer `foreign_block_quarantine_plan`.
- Added read-only MCP `foreign_block_quarantine_plan`.
- Added validation for v0.2.30 `foreign_block_attestation_packet_preview` outputs.
- Added `proposed_quarantine_action` values: `blocked`, `hold_for_human_review`, and `ready_for_future_quarantine_write`.
- Added preview-only archive-relative quarantine paths under `quarantine/foreign-blocks/<case-id>/...`.
- Added tests for valid ready packets, manual-review packets, blocked packets, tampered packets, stdin input, invalid JSON, unsafe packet values, unsafe options, proposed path safety, and MCP dry-run guards.

## Safety Decisions

- Foreign blocks remain `untrusted_foreign`.
- Quarantine plan never creates quarantine files.
- Quarantine plan always has `would_quarantine: false`.
- Quarantine write status remains `not_created`.
- Claimed hashes must remain `not_verified` and `not_trusted`.
- The original foreign artifact is not re-read.
- No files are written.
- Unsafe local paths, provider URLs, token-like values, and secret-like values are blocked without echoing the unsafe value.

## Not Implemented

- No real quarantine writes.
- No real trust/apply/import.
- No attestation writes.
- No receipt writes.
- No minting, anchoring, or delegation.
- No real ZET transport.
- No signing, payment, staking, consensus, blockchain, wallet key management, provider sync, OCR, LLM classification, or full-auto execution.
