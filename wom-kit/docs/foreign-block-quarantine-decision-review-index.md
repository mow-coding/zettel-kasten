# Foreign Block Quarantine Decision Review Index

Status: v0.2.36 baseline

## Principle

```text
A quarantine decision review index is read-only.
It lists recorded local decisions.
It does not trust, import, attest, mint, anchor, delegate, sign, accept, apply, share, or call providers.
```

## Purpose

`quarantine-decision-review` answers:

```text
Which foreign block quarantine decisions have been recorded,
and are their decision records and receipts still internally consistent
with the current quarantine case?
```

The command reads only quarantine metadata and receipts. It never reads original foreign artifact bodies, source documents, provider objects, or objet payload bodies.

## CLI

```bash
archive quarantine-decision-review <archive-root> --format json
```

Useful filters:

```bash
--case-id case-review-001
--decision keep_quarantined|reject_and_keep_record|eligible_for_attestation_review|needs_more_review|all
--include-receipts
```

The default decision filter is `all`.

`--decision` filters only the displayed decision summaries. It does not relax consistency validation. Every discovered decision record, matching decision receipt, current quarantine case, and original quarantine receipt is still checked, and top-level `ok` reflects the whole discovered index.

## Read Boundary

The command may read:

```text
quarantine/foreign-blocks/<case-id>/quarantine-case.json
quarantine/foreign-blocks/<case-id>/quarantine-decision.json
receipts/quarantine/<case-id>.foreign-block-quarantine.json
receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json
```

It writes nothing and returns `would_change: []`.

## Output Boundary

The output keeps:

- `dry_run: true`,
- `lifecycle_action: foreign_block_quarantine_decision_review_index`,
- `trust_state: untrusted_foreign`,
- `review_status: indexed_not_modified`,
- `decision_count`,
- `displayed_decision_count`,
- `total_decision_count`,
- `filter_applied`,
- safe `decisions` summaries,
- safe case-level `cases` summaries.

`decision_count` remains the displayed decision count for compatibility. `total_decision_count` reports the number of discovered decision records that were validated.

`decisions` is the displayed decision-record view. `cases` is a separate case-level projection with one entry per case, including decision counts, displayed counts, case/receipt presence, consistency statuses, latest safe review timestamp, and blocker/warning counts. The two payloads are intentionally not byte-identical.

Missing decision receipts warn. Missing original quarantine cases block because the decision cannot be reviewed safely.

Contradictions, trust-boundary violations, unsafe private values, non-UTC decision timestamps, mismatched case ids, mismatched decisions, inconsistent receipt paths, and mutation flags set to true block the index.

When `--include-receipts` is used, `receipt_summary` uses direct boolean semantics. For example, `trust_granted: false` means trust was not granted, and `provider_api_called: false` means no provider API call was recorded.

## MCP

MCP exposes only:

```text
foreign_block_quarantine_decision_review_index
```

The MCP tool is read-only and has a strict `dry_run is True` guard.

MCP does not expose quarantine decision review apply, write, accept, import, trust, attest, mint, auto-accept, full-auto, provider sync, ZET transport, or receipt-write tools.

## Non-Goals

v0.2.36 does not implement:

- quarantine decision acceptance,
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
