# Foreign Block Attestation Review Candidate Plan

Status: v0.2.38 baseline

## Principle

```text
An attestation review candidate is not an attestation.
It does not trust the foreign block.
It does not import, sign, mint, anchor, delegate, share, or apply anything.
It only prepares safe metadata for a human review step.
```

## Purpose

`attestation-review-candidate` answers:

```text
Given a recorded quarantine decision that is eligible for attestation review,
what safe candidate packet could a human review next?
```

The command re-reads the current quarantine case, original quarantine receipt, recorded quarantine decision, and decision receipt before returning a plan.

## CLI

```bash
archive attestation-review-candidate <archive-root> --case-id case-review-001 --dry-run --format json
```

Optional replay and context:

```bash
--expected-decision eligible_for_attestation_review
--expected-outcome prepare_attestation_review_candidate
--prospective-attestor person:reviewer
--review-scope identity|source_refs|header_hashes|prompt_boundary|full_human_review
--review-note "short non-secret operator context"
```

`review-note` is local context only. WOM-kit returns summary metadata such as `provided`, `length`, `stored: false`, and `content_included: false`. The raw note body is not echoed.

## Output Boundary

The output keeps:

- `dry_run: true`,
- `lifecycle_action: foreign_block_attestation_review_candidate_plan`,
- `trust_state: untrusted_foreign`,
- `candidate_status: planned_not_recorded` when a candidate is available,
- `candidate_status: blocked_not_planned` when blockers prevent candidate planning,
- `attestation_status: not_created`,
- `would_change: []`,
- all import, trust, attestation, mint, provider, sharing, and signature flags false.

When `ok` is false, `attestation_review_candidate` is `null`. A blocked result must not be treated as a candidate packet.

When `ok` is true, the candidate includes safe evidence summaries, missing human checks, disallowed actions, and next safe actions. Hashes retained from sanitized records are commitments or claims only. They are not proof of authenticity.

## MCP

MCP exposes only:

```text
foreign_block_attestation_review_candidate_plan
```

The MCP tool is read-only and has a strict `dry_run is True` guard.

MCP does not expose candidate apply, write, accept, import, trust, attest, sign, mint, auto-accept, full-auto, provider sync, ZET transport, or receipt-write tools.

## Non-Goals

v0.2.38 does not implement:

- attestation review candidate acceptance,
- real trust/apply/import,
- attestation writes,
- signature creation,
- foreign block import,
- minting from foreign blocks,
- anchoring,
- delegation,
- real ZET transport,
- signing,
- payment,
- staking,
- consensus,
- blockchain,
- provider sync,
- OCR,
- LLM classification,
- full-auto execution.
