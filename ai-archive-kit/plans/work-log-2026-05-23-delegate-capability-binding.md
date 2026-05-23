# Work Log: Delegate Capability Binding

Date: 2026-05-23
Status: public-safe work log

## Context

After `v0.2.10` introduced dry-run `delegate-zet`, `attest-zet`, and `anchor-zet`, the next product question was whether delegation means:

```text
one reusable key/link for everyone
```

or:

```text
a capability that becomes bound to the actor who receives or claims it
```

The chosen direction is the second model.

## Decision Recorded

`delegate` should not default to a public link.

The future protocol should treat delegation as an attestation-bound capability:

- `counterparty_bound` for a known recipient archive, subject, agent, group member, or workspace identity,
- `claimable_once` for a one-time invite capability that can be claimed once,
- `spent` after that one-time capability has been claimed and attested,
- `public_link` only as an explicit non-default mode for intentionally public material.

## Why This Matters

In a decentralized system, a central platform should not be the only actor that knows who contacted whom.

The issuer should keep evidence of whom it delegated access to.

The recipient should keep evidence of whom it received a foreign `zet` from.

This preserves the self-sovereign contact ledger implied by the project philosophy.

## Blockchain And Settlement Extension

The core `zet` protocol should not require coins, tokens, payment, or a public blockchain.

However, the capability model leaves a clean extension point for future optional settlement:

- free delegation,
- paid delegation,
- licensed delegation,
- token-gated delegation,
- institutional delegation,
- smart-contract-settled delegation.

Payment or settlement should grant access, capability, or license rights only under explicit terms. It should not silently transfer authorship, provenance, or ownership of the original `zet`.

## Documents Updated

- `ai-archive-kit/docs/concepts/zet-sharing-lifecycle.md`
- `ai-archive-kit/docs/concepts/zet-sharing-lifecycle.ko.md`
- `ai-archive-kit/docs/concepts/product-philosophy.md`
- `ai-archive-kit/docs/concepts/product-philosophy.ko.md`
- `ai-archive-kit/docs/concepts/foundational-product-whitepaper.md`
- `ai-archive-kit/docs/concepts/foundational-product-whitepaper.ko.md`
- `ai-archive-kit/specs/zettelkasten-zet-product-blueprint.md`
- `ai-archive-kit/docs/public-documentation-map.md`
- `ai-archive-kit/docs/public-documentation-map.ko.md`

## Future Implementation Inputs

Future real delegation should consider adding:

- delegate id,
- nonce or one-time claim id,
- target policy,
- target archive/subject/key when known,
- counterparty fingerprint,
- expiry/revocation rule,
- claim status,
- spent status,
- attestation acknowledgement,
- optional settlement condition.

`v0.2.10` remains dry-run only. This work log records the next capability contract direction; it does not implement real P2P, relay, blockchain, payment, or write-time delegation.
