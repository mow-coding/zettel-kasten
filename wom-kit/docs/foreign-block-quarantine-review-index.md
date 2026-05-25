# Foreign Block Quarantine Review Index

Status: v0.2.36 compatible baseline

## Principle

```text
Review indexing is not trust.
Review indexing is not import.
Review indexing is not acceptance.
Review indexing is read-only.
```

## Purpose

`quarantine-review` is the read-only step after a CLI-only approved `quarantine-foreign-block` isolation write.

It inventories existing untrusted foreign block quarantine cases so a human/operator can see what is waiting for review. It also checks whether the matching quarantine write receipt is present and internally consistent.

It does not read the original foreign artifact again.

## CLI

```bash
archive quarantine-review <archive-root> --format json
archive quarantine-review <archive-root> --case-id case-review-001 --format json
archive quarantine-review <archive-root> --include-receipts --format json
```

Options:

- `--case-id <safe-id>` filters to one archive-relative quarantine case id.
- `--status written_untrusted|all` defaults to `written_untrusted`.
- `--include-receipts` includes sanitized receipt summaries.

## Output Boundary

The output keeps:

- `dry_run: true`,
- `lifecycle_action: foreign_block_quarantine_review_index`,
- `trust_state: untrusted_foreign`,
- `would_change: []`.

Each case summary includes archive-relative paths, quarantine status, trust state, receipt presence, receipt consistency, claimed hash summary, prompt-boundary summary, reference summary, disallowed actions, blockers, warnings, and next safe review actions.

## Read Boundary

The command reads only:

```text
quarantine/foreign-blocks/<case-id>/quarantine-case.json
receipts/quarantine/<case-id>.foreign-block-quarantine.json
```

It does not read foreign artifact bodies, provider URLs, objet bodies, source files, or the whole disk.

## Decision Preview

v0.2.34 adds a read-only decision preview for one indexed quarantine case:

```bash
archive quarantine-decision <archive-root> --case-id case-review-001 --dry-run --format json
```

The preview may propose `keep_quarantined`, `reject_and_keep_record`, `eligible_for_attestation_review`, or `needs_more_review`. It records no decision and does not trust, import, attest, mint, anchor, delegate, sign, execute, accept, or apply the foreign block.

v0.2.35 adds a CLI-only decision record after a saved preview is reviewed:

```bash
archive record-quarantine-decision <archive-root> --decision-preview workbench/foreign-block-quarantine-decision.json --dry-run --format json
archive record-quarantine-decision <archive-root> --decision-preview workbench/foreign-block-quarantine-decision.json --approve --reviewed-by person:reviewer --format json
```

The write is limited to one decision JSON and one decision receipt. It keeps the case untrusted and isolated.

v0.2.36 adds a read-only index over recorded decisions:

```bash
archive quarantine-decision-review <archive-root> --format json
archive quarantine-decision-review <archive-root> --decision all --include-receipts --format json
```

The decision review index does not accept, trust, import, attest, mint, anchor, delegate, sign, execute, apply, share, or call providers.

## MCP

MCP exposes only:

```text
foreign_block_quarantine_review_index
```

The MCP tool is read-only. It writes nothing and has a strict `dry_run is True` guard.

MCP does not expose quarantine review apply, accept, import, trust, attest, mint, anchor, delegate, signing, provider sync, ZET transport, or full-auto tools.

## Non-Goals

v0.2.36 does not implement:

- quarantine decision acceptance, trust, or apply,
- quarantine review apply or acceptance,
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

