# Public Documentation Map

Status: public navigation baseline
Date: 2026-05-24

This repository intentionally separates four kinds of public project records:

```text
1. product blueprint / design philosophy
2. implementation reference research
3. implementation plans
4. work logs
```

This separation is part of the project philosophy. The public repository should not only show code. It should show why the system exists, what references informed it, how it will be implemented, and what work has already been done.

## 1. Product Blueprint / Design Philosophy

These documents explain the concept, product philosophy, archive model, and `ZET` communication model.

Start here:

- [WOM Naming And Terminology](concepts/naming-and-terminology.md)
- [Korean WOM Naming And Terminology](concepts/naming-and-terminology.ko.md)
- [Foundational Product Whitepaper](concepts/foundational-product-whitepaper.md)
- [Korean Foundational Product Whitepaper](concepts/foundational-product-whitepaper.ko.md)
- [Product Philosophy](concepts/product-philosophy.md)
- [Korean Product Philosophy](concepts/product-philosophy.ko.md)
- [WOM Safe HTML Profile](concepts/wom-safe-html-profile.md)
- [Korean WOM Safe HTML Profile](concepts/wom-safe-html-profile.ko.md)
- [ZET Sharing Lifecycle Terminology](concepts/zet-sharing-lifecycle.md)
- [Korean ZET Sharing Lifecycle Terminology](concepts/zet-sharing-lifecycle.ko.md)
- [Zettel-Kasten, zet, and ZET Product Blueprint](../specs/zettelkasten-zet-product-blueprint.md)

Supporting philosophy and model docs:

- [Zettel Spec](../specs/zettel.md)
- [Zettel Lifecycle](../specs/zettel-lifecycle.md)
- [Zettel-Kasten Layer](../specs/zettel-kasten.md)
- [Source Object Storage Policy](source-object-storage-policy.md)
- [Text Provenance Hierarchy](text-provenance-hierarchy.md)

These documents cover:

- human data primitives: text/language, sound, image,
- why `zet` is always text,
- why source/original data remains separate from minted zets,
- why private archive memory comes before social sharing,
- why `WOM`, `zet`, `ZET`, and `node` are the preferred product-language anchors,
- why future sharing verbs are framed as `mint -> delegate -> attest -> anchor`,
- how `ZET` sharing can later become messenger, SNS/feed, or collaboration workspace,
- why Markdown remains an authoring/import compatibility format while WOM Safe HTML Profile becomes the long-term canonical/interchange/rendering target,
- why this model is relevant to AI Transformation (AX).
- how the same authority model supports HITL workflows and scoped AI-agent harnesses.

## 2. Implementation Reference Research

This document maps the product idea to existing standards, protocols, and open-source references.

Main research document:

- [Implementation Research](../specs/zettelkasten-zet-implementation-research.md)

It covers references such as:

- W3C PROV,
- IPFS-style content addressing,
- BagIt,
- RO-Crate,
- Basic Memory,
- Model Context Protocol,
- JSON Schema,
- SQLite FTS5,
- DID,
- Verifiable Credentials,
- UCAN,
- Nostr,
- Secure Scuttlebutt,
- Radicle,
- Automerge,
- Yjs,
- Anytype / AnySync,
- Briar,
- SimpleX,
- Matrix,
- MLS.

The purpose is not to claim the project invented every technical component. The purpose is to show which known ideas should be reused or studied so implementation does not start from a blank page.

## 3. Implementation Plans

These documents explain how the project should be built in phases.

Primary current plan:

- [Phase 8 Minting Implementation Plan](../plans/phase-8-minting-implementation-plan.md)

Earlier and supporting plans:

- [Phase 2 Implementation Plan](../plans/phase-2-implementation-plan.md)
- [Phase 3 Implementation Plan](../plans/phase-3-implementation-plan.md)
- [Phase 4 Lineage And Trust Plan](../plans/phase-4-lineage-trust-plan.md)
- [Phase 7 Ownership Transfer Plan](../plans/phase-7-ownership-transfer-plan.md)
- [Ownership Lineage Next Thread Prompt](../plans/next-thread-prompt-ownership-lineage.md)

Onboarding and setup plans:

- [AI-Assisted Onboarding And Provider Setup](ai-assisted-onboarding-and-provider-setup.md)
- [WOM AI Runtime Skill And Plugin Layer](wom-ai-runtime-skill-plugin-layer.md)
- [WOM Profile Registry](wom-profile-registry.md)
- [WOM Profile Wallet Model](wom-profile-wallet-model.md)
- [Prompt Injection Boundary](prompt-injection-boundary.md)
- [Responsible Use](responsible-use.md)
- [Runtime Model Guidance](runtime-model-guidance.md)
- [Foreign Block Intake](foreign-block-intake.md)
- [Foreign Block Trust Preview](foreign-block-trust-preview.md)
- [Foreign Block Attestation Packet Preview](foreign-block-attestation-packet.md)
- [One-Command Setup](one-command-setup.md)
- [New User Flow](new-user-flow.md)
- [External Imports](external-imports.md)

The current implementation priority is:

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

## 4. Work Logs

These documents record public-safe work already performed.

- [Blueprint Consolidation Work Log](../plans/work-log-2026-05-22-zettelkasten-zet-blueprint.md)
- [GitHub Publication Work Log](../plans/work-log-2026-05-23-github-publication.md)
- [Versioning And Storage Work Log](../plans/work-log-2026-05-23-versioning-and-storage.md)
- [Product Whitepaper Depth Correction Work Log](../plans/work-log-2026-05-23-product-whitepaper-depth.md)
- [ZET Sharing Lifecycle Terminology Work Log](../plans/work-log-2026-05-23-zet-sharing-lifecycle-terminology.md)
- [ZET Sharing Dry-Run Lifecycle Work Log](../plans/work-log-2026-05-23-zet-sharing-dry-run-lifecycle.md)
- [WOM Safe HTML Profile Work Log](../plans/work-log-2026-05-23-wom-safe-html-profile.md)
- [WOM Safe HTML Validator Work Log](../plans/work-log-2026-05-23-safe-html-validator.md)
- [WOM AI Runtime Context Work Log](../plans/work-log-2026-05-24-ai-runtime-context.md)
- [WOM Profile Registry Work Log](../plans/work-log-2026-05-24-profile-registry.md)
- [WOM Profile Wallet Concept Work Log](../plans/work-log-2026-05-25-profile-wallet-concept.md)
- [Prompt Injection Boundary Work Log](../plans/work-log-2026-05-25-prompt-injection-boundary.md)
- [Foreign Block Attestation Packet Preview Work Log](../plans/work-log-2026-05-25-foreign-block-attestation-packet-preview.md)
- [Draft Provenance Work Log](../plans/work-log-2026-05-24-draft-provenance.md)
- [WOM-kit Naming Cleanup Work Log](../plans/work-log-2026-05-25-wom-kit-naming-cleanup.md)
- [Delegate Capability Binding Work Log](../plans/work-log-2026-05-23-delegate-capability-binding.md)
- [v0.2.11 Delegate Capability Contract Work Log](../plans/work-log-2026-05-23-delegate-capability-contract.md)
- [Changelog](../../CHANGELOG.md)
- [Release Notes](releases/)

Work logs are not the same as product specs.

They exist so future contributors can see:

- what changed,
- why it changed,
- what was verified,
- what still remains unfinished.

## 5. Runtime Specs And Schemas

Specs:

- [Archive](../specs/archive.md)
- [Archive Identity](../specs/archive-identity.md)
- [Archive Lineage](../specs/archive-lineage.md)
- [Object Manifest](../specs/object-manifest.md)
- [Provider Bindings](../specs/provider-bindings.md)
- [Source Bindings](../specs/source-bindings.md)
- [View](../specs/view.md)
- [Workpack](../specs/workpack.md)

Schemas:

- [Schemas Directory](../schemas/)

These documents are closer to implementation contracts. They should stay more precise than product philosophy documents.

## 6. Public/Private Boundary

Not every project record belongs in the public repository.

Public:

- product philosophy,
- public-safe design blueprints,
- implementation research,
- implementation plans,
- public-safe work logs,
- fake examples,
- schemas,
- source code.

Private:

- real user archives,
- real zets,
- real source maps,
- real receipts,
- provider tokens,
- local filesystem paths,
- private AI conversations,
- private meeting minutes containing sensitive context.

See:

- [Open Source Publication Model](open-source-publication-model.md)
- [Security Policy](../../SECURITY.md)
- [Disclaimer](../../DISCLAIMER.md)
