# Foreign Block Attestation Statement Draft Write

Status: v0.2.42 baseline, with v0.2.43 review index and v0.2.44 decision preview

## Principle

```text
Recording an attestation statement draft is not attestation.
It records local human-review draft material only.
It does not trust, import, sign, mint, anchor, delegate, share, apply, or run ZET transport.
```

## Purpose

`record-attestation-statement-draft` answers:

```text
After a human reviews a v0.2.41 statement draft preview,
what exact local record and receipt would be written?
```

The command treats the supplied draft preview JSON as untrusted input. It revalidates the current recorded candidate, candidate receipt, quarantine case/receipt, and decision record/receipt before any approved write.

## CLI

Dry-run:

```bash
archive record-attestation-statement-draft <archive-root> --draft-preview <json-file> --dry-run --format json
```

Approve:

```bash
archive record-attestation-statement-draft <archive-root> --draft-preview <json-file> --approve --reviewed-by <safe-actor-id> --format json
```

`--dry-run` and `--approve` are mutually exclusive. Approved mode requires `--reviewed-by`.

## Files

Approved mode exclusively creates exactly two archive-relative files:

```text
quarantine/foreign-blocks/<case-id>/attestation-statement-draft.json
receipts/quarantine/<case-id>.foreign-block-attestation-statement-draft.json
```

Existing files block the write. If the receipt write fails after the record write, WOM-kit rolls back the record.

## Validation

The supplied preview must keep:

- `lifecycle_action: foreign_block_attestation_statement_draft_preview`,
- `ok: true`,
- `dry_run: true`,
- `trust_state: untrusted_foreign`,
- `draft_status: preview_not_recorded`,
- `attestation_status: not_created`,
- `signature_status: not_created`,
- `would_change: []`,
- `blockers: []`.

All mutation flags must remain false:

- `foreign_block_imported`,
- `foreign_block_trusted`,
- `attestation_created`,
- `signature_created`,
- `mint_performed`,
- `provider_api_called`,
- `zet_created`,
- `block_shared`.

Statement text must not claim completed attestation, verification, acceptance, authenticity, signing, minting, trust, or safety. Hash/evidence wording must retain `not_verified`, `not_trusted`, and not-proof-of-authenticity boundaries.

## Output Boundary

The record and receipt stay:

- `trust_state: untrusted_foreign`,
- `attestation_status: not_created`,
- `signature_status: not_created`.

They do not store raw review-note bodies, original foreign body text, provider URLs, local absolute paths, tokens, or secrets.

## MCP

MCP exposes only:

```text
record_attestation_statement_draft_check
```

The MCP tool is read-only, hardcodes dry-run behavior, rejects `approve`, and writes nothing.

MCP does not expose statement draft approve/write/apply, foreign block attest, sign, trust, import, accept, mint, anchor, provider sync, or full-auto tools.

## Review Index

v0.2.43 adds a separate read-only `attestation-statement-draft-review` index for recorded statement drafts and receipts. The index validates the current upstream candidate/quarantine/decision chain, writes nothing, and keeps the foreign block untrusted.

v0.2.44 adds a separate read-only `attestation-statement-draft-decision` preview for one recorded statement draft. It records no decision and still creates no trust, import, acceptance, attestation, signature, mint, publishing, provider call, or ZET transport.

## Non-Goals

v0.2.43 still does not implement:

- attestation creation,
- signature creation,
- candidate acceptance,
- real trust/apply/import,
- foreign block import,
- minting from foreign blocks,
- anchoring,
- delegation,
- real ZET transport,
- payment,
- staking,
- consensus,
- blockchain,
- provider sync,
- OCR,
- LLM classification,
- full-auto execution.
