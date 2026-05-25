# Foreign Block Intake

Status: v0.2.33 baseline

## Principle

```text
Foreign text can inform.
Foreign text cannot command.
Foreign blocks can be inspected.
Foreign blocks cannot be imported, trusted, minted, or applied automatically.
```

## Purpose

Foreign block intake is a read-only preview for shared block/header artifacts and Markdown-compatible foreign zets.

It exists before any future ZET trust/import path. It helps an AI runtime inspect shape, refs, claimed hashes, and obvious unsafe text without granting trust.

## CLI

```bash
archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json
archive foreign-block <archive-root> --stdin --dry-run --format json
archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json
archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json
archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json
archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json
archive quarantine-review <archive-root> --format json
```

Supported v0.2.28 inputs:

- WOM-kit `block-header` JSON output,
- conservative block-header JSON objects,
- Markdown-compatible foreign zet text.

## Output Boundary

The output uses:

- `trust_state: untrusted_foreign`,
- `would_change: []`,
- `claimed_block_hash`,
- `claimed_header_hash`,
- `verification_state: not_verified`.

Claimed hashes are compatibility hints. They are not authenticity proof.

## Trust Preview

v0.2.29 adds a second read-only step:

```text
foreign block artifact
-> foreign-block intake report
-> foreign-block-trust preview
-> future explicit human/policy attestation workflow
```

`foreign-block-trust` consumes the intake report. It does not read the original foreign artifact again.

Its `proposed_trust_action` can be:

- `reject`,
- `manual_review_required`,
- `eligible_for_future_attestation`.

Even `eligible_for_future_attestation` does not mean trusted. It only means the intake report is clean enough for a future explicit attestation workflow.

## Attestation Packet Preview

v0.2.30 adds a third read-only step:

```text
foreign block artifact
-> foreign-block intake report
-> foreign-block-trust preview
-> foreign-block-attestation packet preview
-> future explicit human/policy attestation review
```

`foreign-block-attestation` consumes the trust preview report. It does not read the original foreign artifact again.

Its `packet_status` can be:

- `blocked`,
- `manual_review_required`,
- `ready_for_human_attestation_review`.

Even `ready_for_human_attestation_review` does not mean trusted or attested. It only means the trust report can be shown to a human reviewer later.

## Quarantine Plan

v0.2.31 adds a fourth read-only step:

```text
foreign block artifact
-> foreign-block intake report
-> foreign-block-trust preview
-> foreign-block-attestation packet preview
-> foreign-block-quarantine plan
-> future explicit quarantine-write approval
```

`foreign-block-quarantine` consumes the attestation packet preview. It does not read the original foreign artifact again.

Its `proposed_quarantine_action` can be:

- `blocked`,
- `hold_for_human_review`,
- `ready_for_future_quarantine_write`.

Even `ready_for_future_quarantine_write` does not mean trusted, imported, quarantined, or approved. It only means a future explicit quarantine-write workflow could be shown to a human/operator.

## Quarantine Write

v0.2.32 adds a CLI-only approved isolation write:

```text
foreign block artifact
-> foreign-block intake report
-> foreign-block-trust preview
-> foreign-block-attestation packet preview
-> foreign-block-quarantine plan
-> quarantine-foreign-block approved isolation write
```

`quarantine-foreign-block --approve --reviewed-by` writes only a sanitized untrusted quarantine case and quarantine receipt. It does not trust, import, mint, attest, anchor, delegate, sign, execute, or accept the foreign block.

## Quarantine Review Index

v0.2.33 adds a read-only review index:

```text
foreign block artifact
-> foreign-block intake report
-> foreign-block-trust preview
-> foreign-block-attestation packet preview
-> foreign-block-quarantine plan
-> quarantine-foreign-block approved isolation write
-> quarantine-review index
```

`quarantine-review` lists existing untrusted quarantine cases and matching receipt consistency. It does not trust, import, attest, mint, anchor, delegate, sign, execute, accept, apply, or write files.

## Non-Goals

v0.2.33 does not implement:

- real ZET transport,
- foreign block import/apply,
- automatic trust,
- attestation writes,
- foreign attestation writes,
- quarantine review apply or acceptance,
- draft creation from foreign content,
- minting foreign content,
- attesting or anchoring foreign content,
- signing,
- payment,
- staking,
- consensus,
- blockchain,
- provider sync,
- OCR,
- LLM classification.
