# Product Philosophy: WOM, Zettel-Kasten, And Zet

Status: public philosophy baseline
Date: 2026-05-23

This document explains the design philosophy behind WOM, `zettel-kasten`, and `zet`.

`WOM` is the umbrella name: `Widesider of Modernity`.

`zettel-kasten` is the historical root and local archive method. `zet` is the active product primitive.

It is intentionally not only a technical spec. It explains why the system exists.

For the longer public product planning document, read:

- [Foundational Product Whitepaper](foundational-product-whitepaper.md)
- [Korean Foundational Product Whitepaper](foundational-product-whitepaper.ko.md)
- [Naming And Terminology](naming-and-terminology.md)
- [Zet Sharing Lifecycle Terminology](zet-sharing-lifecycle.md)

## 1. Thesis

AI does not only need prompts.

AI needs durable, inspectable, user-owned memory.

WOM uses a local-first archive node for that memory.

`zet` is the text unit that lets a person or organization turn source material, AI conversations, and human judgment into durable archive memory.

The future `zet` sharing layer then lets selected zets move between people, teams, and archives without making a central platform the source of truth.

## 2. Human Data Primitives

The project starts from a simple human-facing model:

```text
text / language
sound
image
```

These are not file extensions. They are human data primitives.

Examples:

- speech can become text through transcription, but the original sound remains sound;
- an image can be captioned or OCR'd, but the original image remains image;
- a document file may contain text, but the file format is not the deepest conceptual layer.

This matters because `zet` is always text.

A `zet` can cite sound, image, video, files, screenshots, PDFs, documents, and external sources, but the `zet` does not become those originals.

The archive must preserve:

```text
original source object
derived text
human interpretation
minted zet
```

as different layers.

## 3. Original Text Versus Derived Text

The system must not treat every text-like artifact as the same authority.

Authority ladder:

```text
L0 original source object
L1 born-digital editable text
L2 parser-extracted text
L3 OCR / speech-to-text / AI transcription
L4 human-reviewed derived text
L5 minted zet
```

An `.hwp`, `.hwpx`, `.docx`, `.txt`, or `.md` document may contain original editable text.

OCR from a screenshot, scanned PDF, image, or video frame is different. It is derived by a tool or model and may improve later.

Both belong in `zettel-kasten`, but they need different provenance.

See:

- `ai-archive-kit/docs/text-provenance-hierarchy.md`
- `ai-archive-kit/docs/source-object-storage-policy.md`

## 4. Why Zettel-Kasten Matters In AX

Here, AX means AI Transformation: the shift from ordinary software workflows to AI-assisted operating workflows.

Most AX attempts start by adding a chatbot to an existing app.

This project starts from a different premise:

```text
AI is only as useful as the memory it can inspect, trust, and act on.
```

Without an archive layer, AI conversations evaporate.

Without provenance, AI cannot tell what came from an original source, OCR, a model guess, a human correction, or an approved decision.

Without receipts, AI actions become difficult to audit.

Without a private-first memory layer, social sharing pressures can distort thinking before it is ready.

`zettel-kasten` is designed as the memory substrate for AX:

```text
source/original data
-> provenance-aware metadata
-> AI-assisted drafts
-> human-reviewed minted zets
-> receipts and versioned archive memory
-> optional sharing, collaboration, and automation
```

The goal is not to replace every app at once.

The goal is to make AI work over durable memory instead of loose files, transient chats, and scattered SaaS silos.

## 5. Zettel-Kasten Memo Philosophy

Traditional zettel thinking treats each note as a durable unit of thought.

This project extends that idea for AI-native archives.

A `zet` is not just a note.

It is:

```text
text body
+ metadata envelope
+ source references
+ provenance
+ relationships
+ lifecycle state
+ authority and review record
```

The user should write and read it like a document.

The system should inspect and verify it like an archive object.

That is the memo philosophy:

```text
human-readable enough to think with,
machine-readable enough to govern,
durable enough to become memory.
```

## 6. Private Archive First

The base system assumes no social network exists.

Minting a `zet` means:

```text
draft zet -> human review -> private canonical archive record
```

Minting is not posting.

Minting is not sharing.

Minting is not publishing to a feed.

This protects the thinking process. A private archive should not become performative social media by accident.

## 7. Zet Sharing And Web3

The future `zet` sharing layer is Web3-like in the infrastructural sense, not in the hype sense.

It does not need to start with tokens, coins, or a public blockchain.

The relevant Web3 principles are:

- subject-owned identity,
- user-owned data,
- portable records,
- verifiable actions,
- relationship-scoped sharing,
- optional peer-to-peer or relay transport,
- no central platform as the only source of truth.

In this model:

```text
1:1 zet sharing       -> messenger
1:many zet sharing    -> social feed / SNS
many:many zet sharing -> collaboration workspace
```

But all of them begin from the same root:

```text
private minted zet
-> share envelope
-> scoped capability or copy/access policy
-> recipient archive or client
```

The preferred lifecycle language for future sharing is:

```text
mint -> delegate -> attest -> anchor
```

In this vocabulary, `attest` is not liking or agreeing. It is the recipient archive's distributed witness that a foreign `zet` existed with a given issuer, hash, protocol profile, and delegated condition.

`delegate` should not mean a reusable public link. The preferred model is an attestation-bound capability: it is either issued to a known counterparty, or it can be claimed once and then becomes bound to the claiming identity. This preserves the decentralized contact ledger: the issuer knows whom it delegated to, and the recipient can prove whom it received from.

The server, if one exists, should help transport, discovery, relay, or sync.

It should not become the canonical owner of the user's archive.

## 8. Versioned Public Chain

The public repository is the reference chain for:

- code,
- specs,
- schemas,
- release notes,
- upgrade rules,
- public examples.

Users may follow the latest release or stay on an older release.

Same major protocol version should mean expected compatibility. Different major versions may need migration or compatibility bridges.

This is why the public repository must be carefully versioned.

## 9. What This Project Is Not

This project is not:

- a generic note app,
- a normal cloud drive,
- a chatbot wrapper,
- a public SNS clone,
- a blockchain token project,
- a replacement for every collaboration tool on day one.

It is a foundation for:

- AI-native private archives,
- provenance-aware zettels,
- local-first memory,
- controlled sharing,
- future messenger/SNS/collaboration layers built from zets.

## 10. Implementation Implication

The correct implementation order is:

```text
local archive
-> source/object model
-> draft zet
-> mint transaction
-> receipts and provenance
-> search/index
-> share packages
-> capability-based sharing
-> local-first collaboration
-> optional P2P/relay/social transport
```

The project should not begin with the hardest social-network layer.

It should first make private memory trustworthy.
