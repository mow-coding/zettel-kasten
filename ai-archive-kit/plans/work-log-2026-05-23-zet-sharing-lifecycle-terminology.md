# Work Log: Zet Sharing Lifecycle Terminology

Date: 2026-05-23
Status: public-safe work log

## Context

After stabilizing `mint` as the product-facing lifecycle word in `v0.2.9`, the next conceptual gap was the future `zet` sharing flow.

The project should not describe this future layer with ordinary SaaS verbs as its core philosophy.

The ordinary SaaS language is:

```text
create -> share -> download -> save
```

The preferred `zet` sharing terminology candidate is:

```text
mint -> delegate -> attest -> anchor
```

## Work Performed

Added a public concept document:

- `ai-archive-kit/docs/concepts/zet-sharing-lifecycle.md`
- `ai-archive-kit/docs/concepts/zet-sharing-lifecycle.ko.md`

Updated public navigation and philosophy documents so the terminology is discoverable:

- `ai-archive-kit/docs/public-documentation-map.md`
- `ai-archive-kit/docs/public-documentation-map.ko.md`
- `ai-archive-kit/docs/concepts/product-philosophy.md`
- `ai-archive-kit/docs/concepts/product-philosophy.ko.md`
- `ai-archive-kit/specs/zettelkasten-zet-product-blueprint.md`

## Recorded Terms

`mint`

: Issue a `zet` into a subject's own private archive as canonical memory.

`delegate`

: Candidate verb for giving another subject, archive, agent, or workspace a scoped capability around a minted `zet`.

`attest`

: Preferred verb for verifying a delegated foreign `zet` and recording evidence of its issuer, hash, protocol profile, and delegated condition.

`anchor`

: Candidate verb for placing an attested foreign `zet` into the recipient archive's meaning network while preserving foreign provenance.

## Design Notes

`attest` is not liking, agreeing, endorsing, reposting, or adopting the idea as one's own.

Attestation is a distributed witness action. If many independent subjects attest the same minted `zet`, later tampering becomes easier to expose through receipt and hash mismatch.

`anchor` is not merely saving a file. It gives a foreign `zet` local context, local relationships, retrieval paths, and a place in the recipient archive's knowledge map.

## Verification

Ran:

```bash
rg "mint -> delegate -> attest -> anchor"
rg "attest|attestation|입증|분산 증인"
rg "delegate|위임|anchor|정박"
```

Results:

- the core lifecycle phrase is present in public docs, the product blueprint, work logs, and private meeting minutes,
- `attest` and attestation language are present with the distributed witness explanation,
- `delegate` and `anchor` are present with capability and meaning-network boundaries,
- no private biographical detail was added to public docs.

## Follow-Up

The next design batch can use this terminology to plan:

- delegate receipts,
- attestation receipts,
- anchor metadata,
- trust/capability compatibility checks,
- and the first dry-run-only sharing validation commands.
