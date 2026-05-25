# Foreign Block Quarantine Plan

Status: v0.2.33 baseline

## Principle

```text
Quarantine is not trust.
Quarantine is not import.
A quarantine plan is not a write.
An approved quarantine write is isolation, not trust.
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

Those paths are not created by `foreign-block-quarantine`.

## Approved Quarantine Write

v0.2.32 adds the next CLI-only step:

```bash
archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json
archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json
```

Approved mode writes only:

```text
quarantine/foreign-blocks/<case-id>/quarantine-case.json
receipts/quarantine/<case-id>.foreign-block-quarantine.json
```

This is an isolation write. It records that an untrusted foreign block review case exists. It does not import the foreign block, trust it, mint it, attest it, anchor it, delegate it, sign it, execute it, or make it canonical.

MCP exposes only `quarantine_foreign_block_check`, which is read-only and writes nothing.

## Review Index

v0.2.33 adds a read-only review index after approved quarantine writes:

```bash
archive quarantine-review <archive-root> --format json
```

It lists existing untrusted quarantine cases and matching receipt consistency without changing the case, the receipt, or the foreign block trust state.

## Non-Goals

v0.2.33 does not implement:

- real trust/apply/import,
- attestation writes,
- foreign attestation writes,
- quarantine review apply or acceptance,
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
