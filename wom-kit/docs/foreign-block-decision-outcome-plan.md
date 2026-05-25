# Foreign Block Decision Outcome Plan

Status: v0.2.39 compatible baseline

## Principle

```text
An outcome plan is not an outcome apply.
It does not trust the foreign block.
It does not import or attest anything.
It only routes a recorded decision to the next safe non-mutating path.
```

## Purpose

`quarantine-decision-outcome` answers:

```text
Given this recorded quarantine decision,
what is the next safe non-mutating path?
```

The command is read-only. It re-reads the current quarantine case, original quarantine receipt, recorded quarantine decision, and decision receipt before returning a plan.

## CLI

```bash
archive quarantine-decision-outcome <archive-root> --case-id case-review-001 --dry-run --format json
```

Optional replay and local review context:

```bash
--expected-decision keep_quarantined|reject_and_keep_record|eligible_for_attestation_review|needs_more_review
--reviewer person:reviewer
--review-note "short non-secret operator context"
```

`review-note` is context only. WOM-kit returns only summary metadata such as `provided`, `accepted_as_context`, `length`, `stored: false`, and `content_included: false`. The raw note body is not echoed.

## Decision Routing

- `keep_quarantined` -> `keep_quarantined`
- `reject_and_keep_record` -> `reject_and_keep_record`
- `needs_more_review` -> `needs_more_review`
- `eligible_for_attestation_review` -> `prepare_attestation_review_candidate`

`eligible_for_attestation_review` is still not trust. It only means the case may be a candidate for a future explicit attestation review workflow.

In v0.2.38 that next read-only layer is:

```bash
archive attestation-review-candidate <archive-root> --case-id case-review-001 --dry-run --format json
```

That candidate planner is still not an attestation. It prepares human-review metadata only.

In v0.2.39 a human/operator can record that candidate through a separate CLI-only approval path:

```bash
archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --approve --reviewed-by person:reviewer --format json
```

That write records only an untrusted candidate and receipt. It still does not create an attestation.

## Output Boundary

The output keeps:

- `dry_run: true`,
- `lifecycle_action: foreign_block_decision_outcome_plan`,
- `trust_state: untrusted_foreign`,
- `outcome_status: planned_not_applied`,
- `would_change: []`,
- all mutation flags false.

The planner blocks if current state is missing, contradictory, unsafe, or no longer consistent. A missing decision receipt or original quarantine receipt blocks this single-case planner.

## MCP

MCP exposes only:

```text
foreign_block_decision_outcome_plan
```

The MCP tool is read-only and has a strict `dry_run is True` guard.

MCP does not expose decision outcome apply, write, accept, import, trust, attest, mint, auto-accept, full-auto, provider sync, ZET transport, or receipt-write tools.

## Non-Goals

v0.2.39 does not implement:

- quarantine decision outcome acceptance,
- attestation review candidate acceptance,
- quarantine decision trust or apply,
- foreign block import,
- foreign block trust,
- foreign attestation writes,
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
