# Foreign Block Quarantine Plan

Status: v0.2.31 baseline

## Principle

```text
Quarantine is not trust.
Quarantine is not import.
A quarantine plan is not a write.
```

## Purpose

`foreign-block-quarantine` is the read-only step after `foreign-block-attestation`.

It consumes a v0.2.30+ `foreign_block_attestation_packet_preview` report and proposes where a future isolated review copy could be held. It does not create that copy.

## CLI

```bash
archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json
archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json
```

Optional preview context:

```bash
--quarantine-case-id case-review-001
--reviewer person:reviewer
--quarantine-policy hold_for_human_review
```

These fields are preview metadata only. They are not approval.

## Output Boundary

The output keeps:

- `trust_state: untrusted_foreign`,
- `quarantine_status: planned_not_written`,
- `quarantine_plan.would_quarantine: false`,
- `quarantine_plan.quarantine_write_status: not_created`,
- `would_change: []`.

The `proposed_quarantine_action` can be:

- `blocked`,
- `hold_for_human_review`,
- `ready_for_future_quarantine_write`.

`ready_for_future_quarantine_write` is not trust, not import, not quarantine, and not approval. It only means a future explicit quarantine-write workflow could be shown to a human/operator.

## Proposed Paths

The plan may preview archive-relative paths such as:

```text
quarantine/foreign-blocks/<case-id>/quarantine-plan.json
```

Those paths are not created in v0.2.31.

## Non-Goals

v0.2.31 does not implement:

- real quarantine writes,
- real trust/apply/import,
- attestation writes,
- receipt writes,
- minting,
- anchoring,
- delegation,
- real ZET transport,
- signing,
- payment,
- staking,
- consensus,
- blockchain,
- wallet key management,
- provider sync,
- OCR,
- LLM classification,
- full-auto execution.
