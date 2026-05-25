# Foreign Block Attestation Review Candidate Write

Status: v0.2.39 baseline

## Principle

```text
Recording an attestation review candidate is not an attestation.
It does not trust the foreign block.
It does not import, sign, mint, anchor, delegate, share, or apply anything.
It only records that a human approved this case as an untrusted review candidate.
```

## CLI

Dry-run:

```bash
archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --dry-run --format json
```

Approved local write:

```bash
archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --approve --reviewed-by person:reviewer --format json
```

Optional replay guards:

```bash
--expected-case-id <case-id>
--expected-review-scope identity|source_refs|header_hashes|prompt_boundary|full_human_review
--expected-attestor <actor-id>
--review-note "short non-secret operator context"
```

Exactly one of `--dry-run` or `--approve` is required. Approve mode requires a safe `--reviewed-by` actor id.

## What Is Written

Dry-run writes nothing and returns exactly two archive-relative paths in `would_change`.

Approved mode writes exactly:

```text
quarantine/foreign-blocks/<case-id>/attestation-review-candidate.json
receipts/quarantine/<case-id>.foreign-block-attestation-review-candidate.json
```

The command refuses overwrites. If the candidate record is created but the receipt write fails, the partial candidate record is rolled back.

## Validation

The supplied v0.2.38 candidate plan is treated as untrusted input. WOM-kit requires:

- successful dry-run candidate plan,
- `trust_state: untrusted_foreign`,
- `candidate_status: planned_not_recorded`,
- `attestation_status: not_created`,
- empty blockers and `would_change: []`,
- populated `attestation_review_candidate`,
- all mutation flags false.

Before dry-run or approve output, WOM-kit re-reads the current quarantine case, original quarantine receipt, decision record, and decision receipt. The regenerated candidate must still match the supplied plan for case id, review scope, prospective attestor, and safe evidence summary.

## Boundaries

The approved candidate remains:

- `trust_state: untrusted_foreign`,
- `candidate_status: recorded_untrusted_candidate`,
- `attestation_status: not_created`.

It does not create trust, import, attestation, signature, mint, provider call, ZET sharing, transport, acceptance, or apply behavior.

## MCP

MCP exposes only:

```text
record_attestation_review_candidate_check
```

The MCP tool is read-only and mirrors the dry-run preview. It rejects approve arguments and any `dry_run` value other than boolean `true`.

MCP does not expose candidate approve, write, apply, accept, trust, import, attest, sign, mint, provider, or full-auto tools.
