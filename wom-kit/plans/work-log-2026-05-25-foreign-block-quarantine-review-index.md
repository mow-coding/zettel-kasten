# Work Log: v0.2.33 Foreign Block Quarantine Review Index

Date: 2026-05-25

Branch:

```text
codex/v0.2.33-foreign-block-quarantine-review-index
```

## Goal

Implement a read-only review index for existing untrusted foreign block quarantine cases after the v0.2.32 approved isolation write.

The index is intentionally narrow:

- list quarantine cases,
- validate basic case and receipt consistency,
- keep the foreign block untrusted and unimported,
- keep MCP read-only.

## Implemented

- Added service-layer `foreign_block_quarantine_review_index`.
- Added CLI `archive quarantine-review <archive-root> --format json`.
- Added `--case-id`, `--status`, and `--include-receipts`.
- Added read-only MCP `foreign_block_quarantine_review_index`.
- Added consistency checks for:
  - archive-relative quarantine case paths,
  - safe case ids,
  - `trust_state: untrusted_foreign`,
  - `quarantine_status: written_untrusted`,
  - disallowed true write/trust/attestation/mint/provider flags,
  - matching quarantine write receipt paths and flags.
- Added regression tests for read-only behavior, filtering, malformed cases, receipt contradictions, unsafe private values, missing receipts, and MCP no-write behavior.
- Updated public docs, release notes, CLI/MCP docs, and runtime skill guidance.

## Explicit Non-Goals

v0.2.33 does not implement:

- quarantine review apply or acceptance,
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

The index emits archive-relative paths only and blocks unsafe local paths, provider URLs, token-like values, private keys, seed phrases, and secret-like strings without echoing the unsafe value.

Public docs use placeholder ids and no real local paths, secrets, private filenames, or private user data.

