# Foreign Block Attestation Statement Draft Preview

Status: v0.2.41 baseline

## Principle

```text
An attestation statement draft is not an attestation.
It does not trust the foreign block.
It does not import, sign, mint, anchor, delegate, share, write a receipt, or apply anything.
It only gives a human a non-binding statement draft to review later.
```

## Purpose

`attestation-statement-draft` answers:

```text
If a human later chooses to attest something about this foreign block,
what exact non-binding statement draft should they review?
```

The command starts from one recorded v0.2.39 attestation review candidate and re-checks current v0.2.40 index consistency before returning a draft.

## CLI

```bash
archive attestation-statement-draft <archive-root> --case-id <safe-case-id> --dry-run --format json
```

Optional context:

```bash
--expected-review-scope identity|source_refs|header_hashes|prompt_boundary|full_human_review
--prospective-attestor <safe-actor-id>
--statement-style minimal|review_checklist|human_readable
--review-note "short non-secret operator context"
```

`review-note` is preview context only. WOM-kit returns summary metadata such as `provided`, `length`, `stored: false`, and `content_included: false`. The raw note body is not echoed or stored.

## Output Boundary

The output keeps:

- `dry_run: true`,
- `lifecycle_action: foreign_block_attestation_statement_draft_preview`,
- `trust_state: untrusted_foreign`,
- `draft_status: preview_not_recorded`,
- `attestation_status: not_created`,
- `signature_status: not_created`,
- `would_change: []`.

All mutation flags remain false:

- `foreign_block_imported`,
- `foreign_block_trusted`,
- `attestation_created`,
- `signature_created`,
- `mint_performed`,
- `provider_api_called`,
- `zet_created`,
- `block_shared`.

## Validation

Before returning a draft, WOM-kit re-reads:

- the current quarantine case,
- the original quarantine receipt,
- the recorded quarantine decision,
- the quarantine decision receipt,
- the recorded attestation review candidate,
- the attestation review candidate receipt.

The recorded candidate must remain `untrusted_foreign`, `recorded_untrusted_candidate`, and `not_created`.

Expected review scope and prospective attestor inputs are replay guards only. A mismatch blocks the draft preview.

Any hash recomputation in this preview is metadata consistency validation over existing archive records. It is not a new full hash over foreign artifacts, source payloads, or objet payloads, and it is not a new authenticity commitment.

## Statement Meaning

Allowed statement meaning:

- the reviewer may review listed metadata and records,
- the draft is a candidate for future human review,
- the foreign block remains untrusted,
- no attestation has been created,
- no signature has been created,
- hash commitments are not proof of authenticity.

Disallowed statement meaning:

- no completed attestation,
- no completed trust,
- no completed import,
- no completed signing,
- no completed minting,
- no provider data check,
- no source/object payload read,
- no claim that the foreign block is safe or authentic.

## MCP

MCP exposes only:

```text
foreign_block_attestation_statement_draft_preview
```

The MCP tool is read-only and rejects any `dry_run` value other than boolean `true`.

MCP does not expose statement draft write/apply, foreign block attest, sign, trust, import, accept, receipt-write, auto-accept, full-auto, provider, or ZET transport tools.

## Non-Goals

v0.2.41 does not implement:

- attestation statement writes,
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
