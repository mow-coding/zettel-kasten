# Foreign Block Attestation Review Candidate Index

Status: v0.2.41 compatible baseline

## Principle

```text
Indexing an attestation review candidate is not an attestation.
It does not trust the foreign block.
It does not accept, import, sign, mint, anchor, delegate, share, or apply anything.
It only gives a reviewer a safe list of already recorded untrusted candidates.
```

## Purpose

`attestation-candidate-review` answers:

```text
Which foreign block attestation review candidates have been recorded,
and do their candidate records, receipts, quarantine cases, and decisions still match?
```

This command is the read-only index after v0.2.39 candidate recording.

v0.2.41 adds the next read-only step after the index: a non-binding statement draft preview for one recorded candidate.

## CLI

```bash
archive attestation-candidate-review <archive-root> --format json
```

Optional filters:

```bash
--case-id <safe-case-id>
--review-scope identity|source_refs|header_hashes|prompt_boundary|full_human_review|all
--include-receipts
```

The default review scope is `all`.

`--case-id` and `--review-scope` filter the displayed `candidates` list only. WOM-kit still validates every discovered candidate record before setting top-level `ok`, so a malformed hidden candidate can still create a blocker.

## Output Boundary

The output keeps:

- `dry_run: true`,
- `lifecycle_action: foreign_block_attestation_review_candidate_index`,
- `trust_state: untrusted_foreign`,
- `index_status: indexed_not_modified`,
- `would_change: []`.

When no candidates exist, `ok` is true with a warning. An empty index is not an error.

When blockers exist, `ok` is false. Unsafe values are blocked without echoing the unsafe value.

## What Is Read

The index may read only:

- `quarantine/foreign-blocks/<case-id>/attestation-review-candidate.json`,
- `receipts/quarantine/<case-id>.foreign-block-attestation-review-candidate.json`,
- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`,
- `quarantine/foreign-blocks/<case-id>/quarantine-decision.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json`.

It must not read the original foreign artifact, source payloads, objet bodies, provider URLs, or local private files.

## Validation

WOM-kit checks that recorded candidates remain:

- `trust_state: untrusted_foreign`,
- `candidate_status: recorded_untrusted_candidate`,
- `attestation_status: not_created`,
- non-mutating, with all write/import/trust/attest/sign/provider flags false.

It also checks matching candidate receipts, required upstream quarantine and decision records, safe UTC `reviewed_at` values, safe actor ids, safe review scopes, and safe summary-only notes.

Unknown optional keys warn when their values are safe. Unsafe values block.

## MCP

MCP exposes only:

```text
foreign_block_attestation_review_candidate_index
```

The MCP tool is read-only and rejects any `dry_run` value other than boolean `true`.

MCP does not expose candidate review apply, approve, write, accept, import, trust, attest, sign, mint, receipt-write, auto-accept, full-auto, provider, or ZET transport tools.

## Statement Draft Preview

After a recorded candidate passes index checks, a reviewer may preview a non-binding statement draft:

```bash
archive attestation-statement-draft <archive-root> --case-id <case-id> --dry-run --format json
```

The statement draft re-reads the current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt. It is not an attestation, not trust, not signing, not import, not minting, not a receipt write, and not ZET transport.

## Non-Goals

v0.2.41 does not implement:

- attestation review candidate acceptance,
- candidate apply,
- attestation statement writes,
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
