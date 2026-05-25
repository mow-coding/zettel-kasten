# Work Log: v0.2.34 Foreign Block Quarantine Decision Preview

Date: 2026-05-25

Branch:

```text
codex/v0.2.34-foreign-block-quarantine-decision-preview
```

## Goal

Implement a read-only decision preview for one existing untrusted foreign block quarantine case.

The preview is intentionally narrow:

- inspect one quarantine case,
- inspect its matching quarantine write receipt,
- propose a future decision path,
- keep the foreign block untrusted and unimported,
- keep MCP read-only.

## Implemented

- Added service-layer `foreign_block_quarantine_decision_preview`.
- Added CLI `archive quarantine-decision <archive-root> --case-id <safe-id> --dry-run --format json`.
- Added optional `--decision-intent`, `--reviewer`, and `--review-note`.
- Added read-only MCP `foreign_block_quarantine_decision_check`.
- Added decision proposals:
  - `keep_quarantined`,
  - `reject_and_keep_record`,
  - `eligible_for_attestation_review`,
  - `needs_more_review`.
- Reused v0.2.33 case and receipt consistency checks.
- Added safeguards against unsafe case ids, unsafe reviewer values, unsafe notes, malformed cases, missing cases, contradictory receipts, and true import/trust/attest/mint/provider flags.
- Added CLI and MCP regression tests for no-write behavior and non-dry-run rejection.
- Updated public docs, release notes, CLI/MCP docs, and runtime skill guidance.

## Explicit Non-Goals

v0.2.34 does not implement:

- quarantine decision apply or write,
- quarantine decision acceptance,
- foreign block import,
- foreign block trust,
- foreign attestation writes,
- minting from foreign blocks,
- anchoring,
- delegation,
- ZET transport,
- signing,
- wallet key management,
- provider sync,
- OCR,
- LLM classification,
- full-auto execution.

## Privacy

The preview emits archive-relative paths only and blocks unsafe local paths, provider URLs, token-like values, private keys, seed phrases, and secret-like strings without echoing the unsafe value.

Review notes are summarized by presence and length only; their content is not echoed in output.

