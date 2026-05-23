# ZET Sharing Lifecycle Terminology

Status: public terminology candidate
Date: 2026-05-23

This document records the product-language direction for the future `ZET` communication layer.

In this document, `zet` means the unit document minted inside a zettel-kasten. `ZET` means the communication method/service/protocol layer built from zets.

It does not implement sharing, P2P transport, social feeds, or collaboration yet. It defines the philosophical verbs that future specs, schemas, receipts, and UI should align with.

For the broader WOM naming baseline, including `zet`, `node`, `parcel`, `admit`, `proof`, and `credential`, see [Naming And Terminology](naming-and-terminology.md).

## 1. Why New Verbs Matter

The project should not inherit ordinary SaaS verbs as its primary worldview.

The ordinary SaaS flow is:

```text
create -> share -> download -> save
```

That language treats data as files moving through a platform.

The `ZET` model treats each subject as an archive-bearing actor that can issue, delegate, verify, and place records within its own memory boundary.

The preferred `ZET` lifecycle flow is:

```text
mint -> delegate -> attest -> anchor
```

This is a terminology candidate, not a finished protocol. It is intentionally closer to blockchain, distributed trust, and urban-sociological thinking than to ordinary app vocabulary.

## 2. Lifecycle Verbs

### Mint

`mint` is the act of issuing a `zet` into a subject's own private archive as canonical memory.

In the current implementation:

```text
draft zet -> mint-zet -> canonical private zet -> mint proof/receipt -> draft snapshot
```

Minting is not posting, sharing, broadcasting, or publishing.

It is private archive issuance.

### Delegate

`delegate` is the candidate verb for making a minted `zet` available to a specific subject, group, archive, agent, or workspace.

Delegation is not ownership transfer.

It means the issuer gives another actor a scoped capability, such as:

- the capability to inspect the `zet`,
- the capability to verify its receipt and hash,
- the capability to access referenced source material,
- the capability to receive a copy,
- the capability to create an attestation.

Future implementation may express this through a delegation credential, capability token, parcel, or another portable proof. Current v0.2 implementation still uses `delegate receipt` in schema-backed compatibility paths.

#### Delegate Is Not A Public Link

The default delegation model should not be a reusable public link or one shared key that anyone can use.

Delegation should be expressed as an attestation-bound capability:

- `counterparty_bound`: issued for a known archive, subject, agent, group member, or workspace identity.
- `claimable_once`: issued as a one-time capability for an initially unknown recipient; once claimed, it becomes bound to the claiming identity.
- `spent`: after a one-time capability is claimed and attested, it should no longer be reusable by another actor.
- `public_link`: possible only as an explicit, non-default future mode for intentionally public material.

This matters because a decentralized system does not outsource the contact ledger to a central platform. The issuer should be able to know which counterparty received or claimed access, and the recipient should be able to prove which issuer delegated it.

In practice, a future real delegation should carry a nonce, scope, target policy, expiry or revocation rule, issuer identity, and content/receipt hashes. The later attestation should bind that delegation to the recipient archive identity or public key fingerprint.

If transport is purely peer-to-peer, the issuer can know that a capability was used only when the recipient returns an attestation or acknowledgement receipt. A shared ledger or public blockchain could later make that observation more globally visible, but it is not required for the core protocol.

### Attest

`attest` is the act of verifying a delegated foreign `zet` and recording evidence that it existed in a specific state.

Attestation is not:

- liking,
- agreeing,
- endorsing,
- reposting,
- adopting the idea as one's own.

An attesting archive says, in effect:

```text
I verified that this foreign zet existed,
was minted by this identity or archive,
matched this schema/protocol profile,
had this content hash,
and entered my archive boundary under these delegated conditions.
```

This is why `attest` is central to the future Web3-like model.

If many independent subjects attest the same minted `zet`, the original issuer can still create a new revision, but cannot easily pretend the older state never existed. The recorded hashes, receipts, and attestations become distributed witnesses.

Attestation should eventually produce an `attestation receipt` or equivalent log entry.

### Anchor

`anchor` is the candidate verb for placing an attested foreign `zet` inside the recipient's own zettel-kasten meaning network.

Anchoring is not merely storing a file.

Anchoring gives the foreign `zet`:

- local context,
- local relationships,
- local retrieval paths,
- local interpretive position,
- and a place in the recipient archive's knowledge map.

The foreign `zet` remains foreign in provenance. Anchoring does not erase authorship, issuer identity, delegated scope, or attestation evidence.

The urban-sociological intuition is that a record becomes meaningful when it gains location, relation, and situated context inside a living map.

## 3. Compatibility Language

The future sharing layer should avoid saying that two users simply need the same app version.

The better compatibility model is:

```text
protocol compatibility
schema compatibility
trust profile compatibility
capability compatibility
```

A client may be on a newer release and still understand an older sharing protocol. A recipient may refuse a technically readable `zet` if its trust profile or delegated capability is insufficient.

## 4. Future Proofs And Compatibility Receipts

The terminology points toward three future evidence objects:

```text
delegation credential / delegation proof
attestation
anchor proof / anchor mark
```

Current v0.2 implementation still uses `receipt` in file paths and schemas for compatibility.

As of `v0.2.14`, the lifecycle is still early, but minting and delegation have real local write paths, and the `WOM`/`zet`/`ZET` naming boundary is now documented:

- `mint-zet --dry-run` previews private archive minting. `mint-zettel` remains a compatibility alias.
- `mint-zet --approve --reviewed-by <actor>` writes canonical private archive memory, a mint receipt, and a draft snapshot.
- `delegate-zet --dry-run` returns a delegate receipt preview.
- `delegate-zet --approve --reviewed-by <actor>` writes a local delegate receipt.
- `attest-zet --dry-run` returns an attestation receipt preview.
- `anchor-zet --dry-run` returns anchor metadata preview.
- `ZET` names the future communication layer, while `zet` remains the minted unit document.
- WOM Safe HTML Profile is the long-term canonical/interchange/rendering direction for zets that may be rendered by future `ZET` surfaces.

`delegate-zet --target-policy claimable_once --dry-run` can preview a one-time claimable capability without naming the recipient archive yet. The later `attest-zet --dry-run` preview binds that capability to the attesting archive through `claim_binding`.

Delegate receipt write is real local evidence, but it is not transport or import. Attestation and anchor are still preview-only.

They should be designed later so that:

- delegation is auditable,
- delegation capabilities can be counterparty-bound or one-time claimable,
- attestation is independently verifiable,
- anchoring preserves foreign provenance,
- and private archive minting remains distinct from social sharing.

## 5. Optional Settlement Layer

The core `zet` sharing model should remain non-financial and protocol-neutral.

However, the capability model leaves room for future optional settlement:

- a delegate capability may require no payment,
- a delegate capability may later reference a payment receipt, license term, token-gated condition, or smart-contract settlement,
- payment should grant access, capability, or license under explicit terms,
- payment should not silently transfer authorship, provenance, or ownership of the original `zet`.

This keeps `zet` useful as free personal communication while leaving a clean path for later blockchain, licensing, patronage, paid knowledge exchange, or institutional access models.

## 6. Current Status

Current status:

- `mint` is already the preferred product word for private archive issuance.
- `attest` is the preferred product word for verifying a foreign `zet`.
- `delegate` is the preferred candidate for scoped sharing authority.
- `anchor` is the preferred candidate for placing an attested foreign `zet` into local meaning.
- `v0.2.10` exposes the first dry-run CLI/MCP checks for delegate, attest, and anchor.
- `v0.2.11` adds `counterparty_bound` and `claimable_once` delegate capability previews.
- `v0.2.12` adds CLI-only real delegate receipt writes.
- `v0.2.13` adds the WOM naming baseline and compatibility-safe CLI aliases: `mint-zet`, `parcel`, and `admit`.
- `v0.2.14` adds the `WOM`/`zet`/`ZET` distinction and WOM Safe HTML Profile design baseline.

Short form:

```text
mint -> delegate -> attest -> anchor
```
