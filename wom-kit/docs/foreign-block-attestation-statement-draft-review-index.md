# Foreign Block Attestation Statement Draft Review Index

Status: v0.2.43 baseline, with v0.2.44 decision preview

## Principle

```text
Reviewing recorded statement drafts is not attestation.
It is a read-only inventory and consistency check for local human review records.
It does not trust, import, sign, mint, anchor, delegate, share, apply, or run ZET transport.
```

## Purpose

`attestation-statement-draft-review` answers:

```text
Which untrusted statement draft records exist, do their receipts match,
and does the current upstream quarantine/candidate/decision chain still agree?
```

It reads only local metadata records:

- `quarantine/foreign-blocks/<case-id>/attestation-statement-draft.json`,
- `receipts/quarantine/<case-id>.foreign-block-attestation-statement-draft.json`,
- the current attestation review candidate record and receipt,
- the current quarantine case and receipt,
- the current quarantine decision record and receipt.

It does not read the original foreign payload, source payload, objet body, provider URL target, or external provider state.

## CLI

```bash
archive attestation-statement-draft-review <archive-root> --format json
```

Optional filters:

```bash
archive attestation-statement-draft-review <archive-root> \
  --case-id <safe-case-id> \
  --statement-style minimal|review_checklist|human_readable|all \
  --review-scope identity|source_refs|header_hashes|prompt_boundary|full_human_review|all \
  --include-receipts \
  --format json
```

Defaults:

- `--statement-style all`,
- `--review-scope all`,
- receipts omitted unless `--include-receipts` is supplied.

`--statement-style` and `--review-scope` filter displayed records only. They do not hide blockers from other discovered statement draft records. `--case-id` intentionally scopes the consistency verdict to one case.

## JSON Shape

Every path returns:

- `ok`,
- `dry_run: true`,
- `lifecycle_action: foreign_block_attestation_statement_draft_review_index`,
- `trust_state: untrusted_foreign`,
- `attestation_status: not_created`,
- `signature_status: not_created`,
- `index_status: indexed_not_modified`,
- filters and counts,
- `statement_drafts`,
- `cases`,
- `blockers`,
- `warnings`,
- `next_safe_actions`,
- `would_change: []`.

Mutation flags remain false:

- `foreign_block_imported`,
- `foreign_block_trusted`,
- `attestation_created`,
- `signature_created`,
- `mint_performed`,
- `provider_api_called`,
- `zet_created`,
- `block_shared`.

## Validation

The index treats recorded files as untrusted metadata and re-checks:

- archive-relative path shape,
- safe `case_id`,
- statement draft record lifecycle and status fields,
- `trust_state: untrusted_foreign`,
- `attestation_status: not_created`,
- `signature_status: not_created`,
- all mutation flags false,
- safe `reviewed_by`,
- absence of raw review-note bodies,
- statement text boundaries such as `not_verified`, `not_trusted`, and not proof of authenticity,
- matching receipt kind, paths, source hashes, and receipt flags,
- current candidate, quarantine, and decision chain consistency.

Unknown safe optional keys warn. Unsafe values block.

## MCP

MCP exposes only:

```text
foreign_block_attestation_statement_draft_review_index
```

MCP is read-only. `dry_run` must be boolean `true`. It writes nothing and does not expose statement draft review apply/write/approve, foreign block attest/sign/trust/import/accept, mint, anchor, provider sync, or full-auto tools.

## Decision Preview

v0.2.44 adds a separate read-only `attestation-statement-draft-decision` preview for one indexed statement draft.

The decision preview reuses the v0.2.43 review index for the requested case, revalidates the current statement draft record and receipt plus upstream candidate/quarantine/decision metadata, and returns one non-binding next review route. It records no decision and does not accept, trust, import, attest, sign, mint, publish, call providers, or run ZET transport.

## Non-Goals

v0.2.44 still does not implement:

- statement draft acceptance,
- statement draft decision writes,
- attestation creation,
- signature creation,
- real trust/apply/import,
- foreign block import,
- minting from foreign blocks,
- anchoring,
- delegation,
- real ZET transport,
- provider sync,
- token or wallet signing,
- full-auto execution.
