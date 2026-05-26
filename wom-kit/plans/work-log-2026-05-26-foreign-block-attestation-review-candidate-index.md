# Work Log: v0.2.40 Foreign Block Attestation Review Candidate Index

Date: 2026-05-26

## Goal

Add a read-only index after v0.2.39 foreign block attestation review candidate recording.

The index should let a human or AI runtime inspect recorded untrusted candidates without accepting, applying, trusting, importing, attesting, signing, minting, sharing, calling providers, or running ZET transport.

## Implemented

- Added CLI `attestation-candidate-review`.
- Added MCP `foreign_block_attestation_review_candidate_index`.
- Added shared service validation for candidate records, candidate receipts, upstream quarantine cases/receipts, and decision records/receipts.
- Added filters for case id and review scope while preserving full discovered-record validation.
- Added optional sanitized receipt summaries.
- Added focused CLI and MCP tests.

## Boundaries

- Dry-run/read-only only.
- No original foreign artifact reads.
- No source payload, objet body, provider URL, or private local file reads.
- No write/apply/accept/trust/import/attest/sign/mint path.
- MCP exposes only the read-only index tool.

## Notes

The command returns `ok: true` when no candidate records exist, with a warning that the index is empty.

Unsafe values are blocked without echoing the unsafe value. Unknown optional keys warn only when their values are safe.
