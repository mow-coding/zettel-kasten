# Foreign Block Attestation Statement Draft Decision Preview

Status: v0.2.44 baseline

## Principle

```text
Previewing a statement draft decision is not acceptance.
It is not attestation, signing, trust, import, minting, publishing, provider sync, or ZET transport.
It is a read-only route preview for human/operator review.
```

## Purpose

`attestation-statement-draft-decision` answers:

```text
Given this recorded statement draft and its current review-index consistency,
what safe next review route can a human/operator consider?
```

The default route intent is `needs_more_review`, because this is the safest non-mutating default in the review chain.

## CLI

```bash
archive attestation-statement-draft-decision <archive-root> --case-id <safe-case-id> --dry-run --format json
```

Optional context:

```bash
archive attestation-statement-draft-decision <archive-root> \
  --case-id <safe-case-id> \
  --dry-run \
  --decision-intent keep_under_review|revise_statement_draft|reject_statement_draft|prepare_future_attestation_statement_review|needs_more_review \
  --reviewer <safe-actor-id> \
  --expected-review-scope identity|source_refs|header_hashes|prompt_boundary|full_human_review \
  --expected-statement-style minimal|review_checklist|human_readable \
  --review-note <operator-authored-note> \
  --format json
```

`--review-note` is preview context only. WOM-kit returns only summary metadata such as `provided`, `length`, `content_included: false`, and `stored: false`. It does not echo or store the raw note body.

## Routes

Supported non-binding routes:

- `keep_under_review`
- `revise_statement_draft`
- `reject_statement_draft`
- `prepare_future_attestation_statement_review`
- `needs_more_review`

`prepare_future_attestation_statement_review` means only that metadata is clean enough for a later explicit review workflow. It is not attestation approval.

If blockers exist, the preview is blocked and the proposed route is forced to `needs_more_review`.

## Read Scope

The preview may read only local metadata records:

- `quarantine/foreign-blocks/<case-id>/attestation-statement-draft.json`
- `receipts/quarantine/<case-id>.foreign-block-attestation-statement-draft.json`
- `quarantine/foreign-blocks/<case-id>/attestation-review-candidate.json`
- `receipts/quarantine/<case-id>.foreign-block-attestation-review-candidate.json`
- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`
- `quarantine/foreign-blocks/<case-id>/quarantine-decision.json`
- `receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json`

It must not read original foreign artifacts, foreign block body text, source documents, provider objects, objet payload bodies, WordPress posts, or provider URLs.

## JSON Invariants

Every output keeps:

- `dry_run: true`
- `lifecycle_action: foreign_block_attestation_statement_draft_decision_preview`
- `trust_state: untrusted_foreign`
- `decision_status: preview_not_recorded`
- `attestation_status: not_created`
- `signature_status: not_created`
- `would_change: []`
- `statement_draft_accepted: false`
- `foreign_block_imported: false`
- `foreign_block_trusted: false`
- `attestation_created: false`
- `signature_created: false`
- `mint_performed: false`
- `provider_api_called: false`
- `zet_created: false`
- `block_shared: false`

## MCP

MCP exposes only:

```text
foreign_block_attestation_statement_draft_decision_preview
```

MCP is read-only. `dry_run` must be boolean `true`.

MCP does not expose decision write/apply, statement draft accept, foreign block attest/sign/trust/import, mint, anchor, provider sync, WordPress publishing, or full-auto tools.

## Non-Goals

v0.2.44 does not implement:

- statement draft acceptance,
- statement draft decision writes,
- attestation creation,
- signature creation,
- real trust/apply/import,
- foreign block import,
- minting from foreign blocks,
- WordPress publishing,
- provider sync,
- anchoring,
- delegation,
- real ZET transport,
- token or wallet signing,
- full-auto execution.
