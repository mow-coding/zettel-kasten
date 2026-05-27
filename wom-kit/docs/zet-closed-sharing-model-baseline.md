# ZET Closed Sharing Model Baseline

Date: 2026-05-26

## Summary

v0.2.47 clarifies the future ZET sharing model before user-level sharing is implemented.

The short version:

```text
base zettel-kasten system -> zet/objet units -> ZET closed sharing layer -> user-selected surfaces
```

GitHub can help the base system track reviewable records and history, but ZET is not simply a GitHub-based SNS. WordPress can be a projection surface, but it is not the WOM or ZET core.

v0.2.48 extends this model with a recommendation philosophy baseline: followed/neighbor feeds should come from explicit relationships, while recommended/broadcast feeds should use user/node-owned and inspectable selector logic.

## 1. Base zettel-kasten Layer

The base zettel-kasten system is local-first infrastructure for archive memory.

In the current architecture:

- GitHub primarily tracks machine-readable metadata, zet documents, version history, and reviewable changes.
- Object storage holds most human-created source/original materials.
- A DB stores relationships between GitHub-tracked records and object-storage materials.

Think of this layer as the archive foundation. It stores, links, and reviews memory before any social or publication surface is involved.

## 2. Unit Layer: zet And objet

`zet` is the smallest organized document unit for a thought.

A `zet` can be private archive memory, a draft under review, or a future candidate for sharing. In the base system, zet documents are tracked through the GitHub side of the archive because they are text records with history.

`objet` is WOM product language for source/original material stored outside Git. The cloud/storage substrate may call this object storage, but the product term stays `objet` when we talk about source materials in WOM.

That distinction matters:

- `zet`: the organized text unit.
- `objet`: the source/original material.
- object storage: the technical storage substrate for many objets.

## 3. Sharing Layer: ZET Closed Sharing/SNS

ZET is the future sharing and communication layer for zets.

A zet can remain private. A zet can also later be shared with specific people, groups, archives, agents, or workspaces.

In user-facing product terms, ZET can become a Web 3.0-style closed SNS/SaaS:

- closed relationship and permission graph,
- shared zet updates,
- verification or attestation before local acceptance or re-projection,
- participant-specific views and surfaces.

This is closed sharing, not a public repost feed by default. It should avoid public-link assumptions, blind reposting, and automatic trust.

GitHub may be one implementation substrate or coordination example. A future closed sharing SaaS may also use DB/object storage or another substrate. The product model is ZET-based sharing above the base zettel-kasten system.

## 4. Surface Layer

Shared zets need UI/UX for reading, searching, gathering, and re-projecting.

The surface layer is user-selected and pluggable. Possible surfaces include:

- custom user SaaS,
- open-source ZET UI,
- static site,
- private archive UI,
- feed/RSS-like app,
- team workspace,
- WordPress as one possible projection surface,
- future dedicated ZET client.

The surface is not the canonical archive and not the whole ZET architecture.

## 5. Feed And Recommendation Boundary

Closed sharing should keep relationship-based content and recommendation-shaped content distinguishable.

The default ZET feed model should start from:

- known neighbor nodes,
- delegated access,
- groups and workspaces,
- permission scopes,
- receiver-side review or attestation state.

Recommended or broadcast content may exist later, but it should not be hidden inside the neighbor feed as if it came from explicit relationships. A node should be able to inspect which selector, frequency/channel, source scope, and observation window produced a recommended item.

See [ZET Radio-Frequency Recommendation Model](zet-radio-frequency-recommendation-model.md).

## 6. Attestation In The Closed SNS Flow

In beginner terms, attestation is the receiver-side review step before a shared zet update affects a local view, neighbor feed, mirror, or projection.

It asks:

- Is this really from the expected neighbor, issuer, archive, or relationship?
- Does the shared zet/update record match its claimed hashes, receipts, and scope?
- Does the permission allow this receiver to see, mirror, re-project, or route it?
- Should the receiver keep it under review, mirror/re-project it, reject it, or send it to another review path?

Attestation is not a like, endorsement, blind repost, automatic follow, or automatic feed update.

In v0.2.x, attestation is also not necessarily a real cryptographic signature. The current foreign-block and attestation-review line is a conservative review path that points toward future closed ZET sharing:

```text
foreign/shared candidate
-> intake/review
-> attestation-style verification
-> optional local surface update later
```

## Non-Goals

v0.2.47 does not:

- implement shared zet update CLI,
- implement neighbor feed CLI,
- implement mirror/re-project CLI,
- call providers,
- publish to WordPress,
- write projection records or projection receipts,
- implement real ZET transport,
- automatically update neighbor feeds,
- mint, trust, import, accept, attest, sign, anchor, apply, or transport anything,
- introduce Redis, queues, background workers,
- implement SaaS server or UI app,
- introduce payments, staking, consensus, blockchain, WOM coin, token mechanics,
- train models, run backpropagation, or enable full-auto execution.
