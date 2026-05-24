# Work Log: v0.2.24 Block Header Preview

Date: 2026-05-25

## Goal

Add a read-only dry-run preview that derives a block header from an existing draft or canonical zet.

## Implemented

- Added CLI `archive block-header`.
- Added `--path` and `--zettel-id` target modes.
- Added dry-run-only shared service `block_header_preview`.
- Added deterministic body, header, and block hash previews.
- Collected referenced zets from edges.
- Collected referenced objets from assets, source refs, and source intake metadata.
- Collected referenced receipts from mint, promotion, and source intake metadata.
- Added MCP read-only `block_header_check`.
- Added focused CLI and MCP regression tests.
- Updated v0.2.24 documentation, release notes, and version metadata.

## Safety Decisions

- The command reads only the target zet file.
- It writes nothing.
- It does not mint.
- It does not modify existing zets.
- It does not read referenced objet/source file bodies.
- It does not calculate referenced source hashes.
- It does not follow provider URLs.
- It does not call provider APIs.
- Local absolute paths and unsafe references are redacted from header output.
- `header_sha256` commits to the sanitized/shareable header projection, not raw private frontmatter.
- `zet_body_sha256` is block-preview specific and is not interchangeable with draft approval replay hashes.

## Concept Decision

The block model is:

```text
block = zet + header
```

The zet remains the minimum human-supervised text information unit. ZET is the sharing layer for delegate, attest, and anchor flows, not the block itself.

The current block hash is a preview identity for a shareable projection. It is deliberately not a financial primitive, blockchain consensus hash, or raw private archive integrity proof.

## Not Implemented

- Real ZET transport.
- Token mechanics.
- WOM coin.
- NFT-like access.
- Paid delegation.
- Staking-like trust.
- Payments.
- Consensus, ledger, relay, P2P, or blockchain behavior.
