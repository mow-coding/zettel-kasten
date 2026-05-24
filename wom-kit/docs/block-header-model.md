# Block Header Model

Status: v0.2.24 draft baseline
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

`block_hash_preview` has the same boundary: it previews the identity of the shareable block projection. It should not be treated as a raw private archive integrity hash.

`zet_body_sha256` also has a different purpose from draft approval hashes such as `expected_body_sha256`. The block-header preview normalizes CRLF/CR line endings to LF for block preview identity, while draft approval hashes follow the draft creation replay contract. Do not compare the two fields as if they were interchangeable.

## Non-Goals

v0.2.24 does not implement:

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
- blockchain behavior.

Those are possible future economic or network layers, not part of this read-only header preview.
