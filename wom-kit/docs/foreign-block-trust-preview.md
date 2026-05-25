# Foreign Block Trust Preview

Status: v0.2.32 baseline

## Principle

```text
Foreign blocks can be inspected.
Foreign blocks cannot become trusted automatically.
Attestation requires explicit future human or policy approval.
```

## Purpose

`foreign-block-trust` is a read-only decision aid after `foreign-block` intake.

It consumes a v0.2.28+ `foreign_block_intake` report and answers whether the report should be rejected, manually reviewed, or considered eligible for a future attestation workflow.

It does not trust the foreign block.

## CLI

```bash
archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json
archive foreign-block-trust <archive-root> --stdin --dry-run --format json
```

The command reads only the intake report. It does not read the original foreign artifact again.

## Attestation Packet Preview

v0.2.30 adds one more read-only step:

```bash
archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json
archive foreign-block-attestation <archive-root> --stdin --dry-run --format json
```

`foreign-block-attestation` consumes the trust preview report. It does not read the original foreign artifact again and does not create trust, write attestations, write receipts, import, mint, anchor, delegate, sign, or call provider APIs.

The output is a human-review packet preview. `ready_for_human_attestation_review` is not trust and not approval.

## Quarantine Plan

v0.2.31 adds the next read-only step:

```bash
archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json
archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json
```

`foreign-block-quarantine` consumes the attestation packet preview. It plans future archive-relative holding paths but does not create quarantine files, trust, imports, attestations, receipts, or mint outputs.

`ready_for_future_quarantine_write` is not trust, not import, and not approval.

## Quarantine Write

v0.2.32 adds a CLI-only approved isolation write:

```bash
archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json
archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json
```

This writes only a sanitized quarantine case and quarantine write receipt. It does not trust, import, mint, attest, anchor, delegate, sign, execute, or accept the foreign block.

## Output Boundary

The output keeps:

- `trust_state: untrusted_foreign`,
- `attestation_preview.would_attest: false`,
- `attestation_preview.attestation_status: not_created`,
- `would_change: []`.

The `proposed_trust_action` can be:

- `reject`,
- `manual_review_required`,
- `eligible_for_future_attestation`.

`eligible_for_future_attestation` is not trust. It means the report shape is clean enough for a future explicit attestation workflow.

## Non-Goals

v0.2.32 does not implement:

- real trust/apply/import,
- attestation writes,
- foreign attestation writes,
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
