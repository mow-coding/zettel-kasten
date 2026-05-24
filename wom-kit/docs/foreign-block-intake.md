# Foreign Block Intake

Status: v0.2.28 baseline

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

## Non-Goals

v0.2.28 does not implement:

- real ZET transport,
- foreign block import/apply,
- automatic trust,
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
