# Foreign Block Quarantine Write

Status: v0.2.34 baseline

## Principle

```text
Quarantine is isolation.
Quarantine is not trust.
Quarantine is not import.
Quarantine is not attestation.
```

An approved quarantine write records that a local archive has opened an untrusted foreign block review case.

It does not make the foreign block canonical archive memory. It does not create a trusted relationship, import source material, mint a zet, attest a claim, anchor anything, delegate access, sign data, call providers, or execute foreign text.

## CLI

Dry-run:

```bash
archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json
```

Approved write:

```bash
archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json
```

Optional safe replay checks:

```bash
--expected-case-id case-review-001
--review-note "Short non-secret operator note"
```

`review-note` is local review context only. It is not trust, attestation, mint approval, delegation, anchor approval, or signing.

## Inputs

The command consumes a v0.2.31+ `foreign_block_quarantine_plan` JSON report.

The plan must still be:

- `ok: true`,
- `dry_run: true`,
- `lifecycle_action: foreign_block_quarantine_plan`,
- `trust_state: untrusted_foreign`,
- `quarantine_status: planned_not_written`,
- `proposed_quarantine_action: ready_for_future_quarantine_write`,
- free of blockers,
- free of unsafe local paths, provider URLs, token-like values, private keys, seed phrases, and secret-like strings.

Plans that still require hold/manual review are refused in v0.2.32.

## Writes

Approved mode writes only:

```text
quarantine/foreign-blocks/<case-id>/quarantine-case.json
receipts/quarantine/<case-id>.foreign-block-quarantine.json
```

The quarantine case is sanitized. It contains summary metadata, claimed hash metadata, prompt-boundary summary, reference summary, retained/excluded material labels, review metadata, and explicit disallowed actions.

The receipt records only the quarantine write itself and keeps these flags false:

- `foreign_block_imported`,
- `foreign_block_trusted`,
- `attestation_created`,
- `mint_performed`,
- `provider_api_called`.

## MCP

MCP exposes only:

```text
quarantine_foreign_block_check
```

The MCP tool is read-only and dry-run only. It writes nothing and has a strict `dry_run is True` guard.

MCP does not expose quarantine write/apply, import, trust, attest, mint, anchor, delegate, signing, provider sync, ZET transport, or full-auto tools.

## Review Index

v0.2.33 adds a read-only review index for existing quarantine cases:

```bash
archive quarantine-review <archive-root> --format json
archive quarantine-review <archive-root> --case-id case-review-001 --include-receipts --format json
```

The index reads only existing quarantine case JSON and matching quarantine write receipts. It reports case count, case summaries, receipt presence, receipt consistency, blockers, warnings, and next safe review actions.

The review index does not change trust state. A listed case is still untrusted foreign material, not imported archive memory and not an accepted block.

## Decision Preview

v0.2.34 adds a read-only decision preview after the review index:

```bash
archive quarantine-decision <archive-root> --case-id case-review-001 --dry-run --format json
```

This is a candidate decision aid only. It does not record approval, write a decision, trust, import, attest, mint, anchor, delegate, sign, execute, accept, or apply the foreign block.

## Non-Goals

v0.2.34 does not implement:

- quarantine decision apply or write,
- foreign block trust,
- foreign block import/apply,
- foreign attestation writes,
- quarantine review apply or acceptance,
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
