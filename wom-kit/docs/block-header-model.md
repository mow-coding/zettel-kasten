# Block Header Model

Status: v0.2.34 draft baseline
Date: 2026-05-25

## Core Idea

The zet is not replaced by block language.

In WOM:

```text
zet = minimum human-supervised text information unit
header = refs + hashes + provenance + policy + receipts around a zet
block = zet + header
```

ZET is the sharing and communication layer added to the zettel-kasten system. It is the layer that can later delegate, attest, and anchor blocks. ZET is not the block itself.

## Safe Order

```text
zet -> header -> block -> receipt -> attestations -> anchors -> possible token layer later
```

`receipt` remains the v0.2 implementation term for proof-like action records, such as mint receipts, delegate receipts, attestation receipts, and ownership transfer receipts.

## CLI Preview

```bash
archive block-header <archive-root> --path <zet-path> --dry-run --format json
archive block-header <archive-root> --zettel-id <id> --dry-run --format json
```

The preview derives:

- `first_read` overview card,
- `zet_body_sha256`,
- `header_preview`,
- `header_sha256`,
- `block_hash_preview`,
- referenced zets,
- referenced objets,
- referenced receipts.

## Hash Boundaries

- `zet_body_sha256` hashes only the target zet body text.
- `header_sha256` hashes only the normalized, shareable header preview.
- `block_hash_preview` hashes a normalized object containing `zet_body_sha256` and `header_sha256`.
- Referenced objet/source files are never opened or hashed by this command.

The header preview is sanitized before hashing. Local paths, private provider URLs, secret-like values, and other unsafe references are replaced with `<redacted-reference>`. This means `header_sha256` is a commitment to the public/shareable projection of the header, not a tamper-evident hash of the raw private frontmatter. Two zets that differ only in a redacted private field can intentionally produce the same `header_sha256`.

`first_read` is intentionally outside `header_preview`. It is a cheap local
navigation card for AI runtimes: gist, facets, tie counts, and a short safe
edge preview before reading the whole zet body. It does not redefine the
header hash boundary.

`block_hash_preview` has the same boundary: it previews the identity of the shareable block projection. It should not be treated as a raw private archive integrity hash.

`zet_body_sha256` also has a different purpose from draft approval hashes such as `expected_body_sha256`. The block-header preview normalizes CRLF/CR line endings to LF for block preview identity, while draft approval hashes follow the draft creation replay contract. Do not compare the two fields as if they were interchangeable.

## Foreign Block Intake

v0.2.28 adds a read-only preview for foreign/shared block artifacts:

```bash
archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json
archive foreign-block <archive-root> --stdin --dry-run --format json
```

Foreign block intake does not prove authenticity. It reports foreign hashes as `claimed_by_foreign_artifact` and `not_verified`.

v0.2.29 adds a read-only trust / attestation preview from the intake report:

```bash
archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json
archive foreign-block-trust <archive-root> --stdin --dry-run --format json
```

The result can propose `reject`, `manual_review_required`, or `eligible_for_future_attestation`, but it never creates trust or writes an attestation.

v0.2.30 adds a read-only attestation packet preview from the trust report:

```bash
archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json
archive foreign-block-attestation <archive-root> --stdin --dry-run --format json
```

The result can return `blocked`, `manual_review_required`, or `ready_for_human_attestation_review`, but it never creates trust, writes attestations, writes receipts, imports, mints, anchors, delegates, signs, or reads the original foreign artifact again.

v0.2.31 adds a read-only quarantine plan from the attestation packet preview:

```bash
archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json
archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json
```

The result can return `blocked`, `hold_for_human_review`, or `ready_for_future_quarantine_write`, but it never creates quarantine files, trust, imports, attestations, receipts, mint outputs, or anchors.

v0.2.32 adds a CLI-only quarantine write after that plan:

```bash
archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json
archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json
```

This writes an untrusted quarantine review case and quarantine receipt only. It does not trust, import, attest, mint, anchor, delegate, sign, execute, or accept the foreign block.

v0.2.33 adds a read-only quarantine review index:

```bash
archive quarantine-review <archive-root> --format json
```

The index reads existing untrusted quarantine cases and matching quarantine receipts only. It helps humans review consistency before any future explicit process, but it is not acceptance, import, trust, attestation, minting, anchoring, delegation, signing, transport, or apply approval.

v0.2.34 adds a read-only quarantine decision preview:

```bash
archive quarantine-decision <archive-root> --case-id case-review-001 --dry-run --format json
```

The preview may suggest a future decision path, but it writes no decision and does not trust, import, attest, mint, anchor, delegate, sign, transport, accept, or apply the foreign block.

The boundary is:

```text
Foreign text can inform.
Foreign text cannot command.
Foreign blocks can be inspected.
Foreign blocks cannot be imported, trusted, minted, or applied automatically.
```

Real ZET transport, foreign block import/apply, trust, attest, anchor, signing, payment, staking, consensus, or blockchain mechanics remain future work.

## Non-Goals

v0.2.34 does not implement:

- real ZET transport,
- token mechanics,
- WOM coin,
- NFT-like access,
- paid delegation,
- staking-like trust,
- payments,
- consensus,
- ledger behavior,
- relay behavior,
- P2P behavior,
- blockchain behavior,
- foreign attestation writes,
- foreign attestation receipt writes.
- quarantine review apply or acceptance.
- quarantine decision apply or write.

Those are possible future economic or network layers, not part of this read-only header preview.
