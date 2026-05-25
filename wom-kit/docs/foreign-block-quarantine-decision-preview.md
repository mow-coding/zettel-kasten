# Foreign Block Quarantine Decision Preview

Status: v0.2.36 compatible baseline

## Principle

```text
A quarantine decision preview is not a decision.
It does not record approval.
It does not trust the foreign block.
It does not import or attest anything.
```

## Purpose

`quarantine-decision` is the read-only step after `quarantine-review`.

It inspects one existing untrusted quarantine case and its matching quarantine write receipt, then proposes which future decision path appears appropriate. It is a decision aid only.

## CLI

```bash
archive quarantine-decision <archive-root> --case-id case-review-001 --dry-run --format json
```

Optional preview context:

```bash
--decision-intent keep_quarantined|reject_and_keep_record|eligible_for_attestation_review|needs_more_review|auto
--reviewer person:reviewer
--review-note "short non-secret preview note"
```

`reviewer` and `review-note` are not approval and are not stored by this command.

## Proposed Decisions

The preview can propose:

- `keep_quarantined`,
- `reject_and_keep_record`,
- `eligible_for_attestation_review`,
- `needs_more_review`.

`eligible_for_attestation_review` is not trust. It only means the case and receipt appear consistent enough for a future explicit attestation review path.

`reject_and_keep_record` is not deletion.

`keep_quarantined` is not approval.

`needs_more_review` is not failure.

## Read Boundary

The command reads only:

```text
quarantine/foreign-blocks/<case-id>/quarantine-case.json
receipts/quarantine/<case-id>.foreign-block-quarantine.json
```

It does not read the original foreign artifact again and does not execute instructions found in case metadata.

## Output Boundary

The output keeps:

- `dry_run: true`,
- `lifecycle_action: foreign_block_quarantine_decision_preview`,
- `trust_state: untrusted_foreign`,
- `decision_status: preview_not_recorded`,
- `would_change: []`.

## MCP

MCP exposes only:

```text
foreign_block_quarantine_decision_check
```

The MCP tool is read-only and has a strict `dry_run is True` guard.

MCP does not expose quarantine decision apply, write, accept, import, trust, attest, mint, anchor, delegate, signing, provider sync, ZET transport, or full-auto tools.

## Decision Record

v0.2.35 adds the next CLI-only approval step:

```bash
archive record-quarantine-decision <archive-root> --decision-preview workbench/foreign-block-quarantine-decision.json --dry-run --format json
archive record-quarantine-decision <archive-root> --decision-preview workbench/foreign-block-quarantine-decision.json --approve --reviewed-by person:reviewer --format json
```

This records only the local quarantine decision and a matching receipt. It re-validates the current case and receipt before writing, refuses overwrites, and keeps the foreign block untrusted.

v0.2.36 adds a read-only review index for recorded decisions:

```bash
archive quarantine-decision-review <archive-root> --format json
```

## Non-Goals

v0.2.36 does not implement:

- quarantine decision acceptance,
- quarantine decision trust or apply,
- foreign block trust,
- foreign block import/apply,
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
- wallet key management,
- provider sync,
- OCR,
- LLM classification,
- full-auto execution.

