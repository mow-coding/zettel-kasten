# Foreign Block Quarantine Decision Write

Status: v0.2.38 compatible baseline

## Principle

```text
A recorded quarantine decision is still not trust.
It is an operator-reviewed local decision record.
It does not import, attest, mint, anchor, delegate, sign, accept, or apply a foreign block.
```

## Purpose

`record-quarantine-decision` is the smallest safe write layer after `quarantine-decision --dry-run`.

It consumes a saved decision preview, treats that preview as untrusted input, re-reads the current quarantine case and matching quarantine write receipt, and records only the local operator decision if everything still matches.

## CLI

Dry-run:

```bash
archive record-quarantine-decision <archive-root> --decision-preview <json-file> --dry-run --format json
```

Approved write:

```bash
archive record-quarantine-decision <archive-root> --decision-preview <json-file> --approve --reviewed-by person:reviewer --format json
```

Optional replay guards:

```bash
--expected-case-id case-review-001
--expected-decision keep_quarantined
--review-note "short non-secret operator context"
```

The review note is not stored as raw body text. WOM-kit stores only summary metadata such as whether a safe note was provided and its accepted length.

## Write Boundary

Approved mode writes exactly two files and refuses to overwrite either:

```text
quarantine/foreign-blocks/<case-id>/quarantine-decision.json
receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json
```

If the second write fails after the first file is created, WOM-kit rolls back the partial decision file.

## Validation

The command requires the saved preview to be:

- `ok: true`,
- `dry_run: true`,
- `lifecycle_action: foreign_block_quarantine_decision_preview`,
- `trust_state: untrusted_foreign`,
- `decision_status: preview_not_recorded`,
- blocker-free,
- `would_change: []`,
- one of the supported proposed decisions.

Before writing, WOM-kit re-validates the current quarantine case and matching quarantine write receipt. Missing, malformed, contradictory, unsafe, stale, or already-recorded state blocks the write.

## MCP

MCP exposes only the read-only check:

```text
record_quarantine_decision_check
```

The MCP check mirrors dry-run validation and writes nothing. It does not approve, record, trust, import, attest, mint, anchor, delegate, sign, accept, apply, share, call providers, or create receipts.

## Decision Review Index

v0.2.36 adds a read-only index over recorded decisions:

```bash
archive quarantine-decision-review <archive-root> --format json
archive quarantine-decision-review <archive-root> --case-id case-review-001 --include-receipts --format json
```

The index checks decision records, decision receipts, the original quarantine case, and the original quarantine receipt. It writes nothing and keeps the foreign block untrusted.

## Decision Outcome Plan

v0.2.37 adds a read-only planner after a recorded decision passes review:

```bash
archive quarantine-decision-outcome <archive-root> --case-id case-review-001 --dry-run --format json
```

The planner returns `planned_not_applied` and never creates trust, imports, attestations, mint receipts, anchors, delegation, signing, acceptance, provider sync, or ZET transport.

## Attestation Review Candidate Plan

v0.2.38 adds a read-only candidate planner for recorded `eligible_for_attestation_review` decisions:

```bash
archive attestation-review-candidate <archive-root> --case-id case-review-001 --dry-run --format json
```

The candidate plan returns `planned_not_recorded` and never creates trust, imports, attestations, signatures, mint receipts, anchors, delegation, acceptance, provider sync, or ZET transport.

## Non-Goals

v0.2.38 does not implement:

- quarantine decision acceptance,
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
