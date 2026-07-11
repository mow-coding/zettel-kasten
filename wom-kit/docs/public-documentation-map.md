# Public Documentation Map

Status: public navigation baseline
Date: 2026-06-02
Updated: 2026-06-03

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
- [Korean Product Language Baseline](concepts/korean-product-language-baseline.ko.md)
- [Foundational Product Whitepaper](concepts/foundational-product-whitepaper.md)
- [Korean Foundational Product Whitepaper](concepts/foundational-product-whitepaper.ko.md)
- [Product Philosophy](concepts/product-philosophy.md)
- [Korean Product Philosophy](concepts/product-philosophy.ko.md)
- [WOM Safe HTML Profile](concepts/wom-safe-html-profile.md)
- [Korean WOM Safe HTML Profile](concepts/wom-safe-html-profile.ko.md)
- [WOM Product Roadmap](product-roadmap.md)
- [ZET Sharing Lifecycle Terminology](concepts/zet-sharing-lifecycle.md)
- [Korean ZET Sharing Lifecycle Terminology](concepts/zet-sharing-lifecycle.ko.md)
- [Zettel-Kasten, zet, and ZET Product Blueprint](../specs/zettelkasten-zet-product-blueprint.md)

Supporting philosophy and model docs:

- [Zettel Spec](../specs/zettel.md)
- [Zettel Lifecycle](../specs/zettel-lifecycle.md)
- [Zettel-Kasten Layer](../specs/zettel-kasten.md)
- [Agent Operator Capabilities Manifest](agent-operator-capabilities.md)
- [Operator Feedback Lifecycle](operator-feedback-lifecycle.md)
- [Approval Handoff Lifecycle](approval-handoff-lifecycle.md)
- [Approval Handoff Audit](approval-handoff-audit.md)
- [Operation Status Taxonomy](operation-status-taxonomy.md)
- [Input Provenance Taxonomy](input-provenance-taxonomy.md)
- [Secret Signal Taxonomy](secret-signal-taxonomy.md)
- [Local Sovereignty And Backup Authority](local-sovereignty-and-backup-authority.md)
- [Large-Command Progress And Bounded Output](large-command-progress-and-output.md)
- [AI Response Contract](ai-response-contract.md)
- [Operator Envelope Classes](operator-envelope-classes.md)
- [Objet Capture Enablement](capture-enablement.md)
- [AI Response Concept Guide](ai-response-concept-guide.md)
- [zet Abstract And Live Catalog](zet-abstract-catalog.md)
- [zet Catalog Readiness Signals](zet-catalog-readiness-signals.md)
- [zet Catalog Scale And Token Budget](zet-catalog-scale-and-token-budget.md)
- [zet Catalog Response Envelope Budget](zet-catalog-response-envelope-budget.md)
- [zet Catalog Compact Continuations](zet-catalog-compact-continuations.md)
- [zet Catalog Pass Artifact Lifecycle](zet-catalog-pass-artifact-lifecycle.md)
- [zet Abstract Backfill Plan](zet-abstract-backfill-plan.md)
- [zet Abstract Backfill Write](zet-abstract-backfill-write.md)
- [zet Abstract Backfill Revert](zet-abstract-backfill-revert.md)
- [Contiguous Node Reading](zet-catalog-contiguous-reading.md)
- [Seeded Connection Reading Order](seeded-connection-reading-order.md)
- [Seeded Reading Route Evidence](seeded-reading-route-evidence.md)
- [Archive Status Board](archive-status-board.md)
- [Derived Artifact Staleness](derived-artifact-staleness.md)
- [zet Quality Check](zet-quality-check.md)
- [Source Object Storage Policy](source-object-storage-policy.md)
- [Text Provenance Hierarchy](text-provenance-hierarchy.md)
- [Derived Text Capture](derived-text.md)
- [Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)
- [Notion Page Snapshot Model](notion-page-snapshot-model.md)
- [Objet Ref Resolution](objet-ref-resolution.md)
- [Presigned URL Plan](presigned-url-plan.md)
- [Zettel Objet Links](zettel-objet-links.md)
- [Notion Objet Link Plan](notion-objet-link-plan.md)
- [Notion Objet Link Index](notion-objet-link-index.md)
- [Notion Objet Import Clue Audit](notion-objet-import-clue-audit.md)
- [Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)
- [Notion Objet Link Rewrite Plan](notion-objet-link-rewrite-plan.md)
- [Notion Objet Link Convert](notion-objet-link-convert.md)
- [Notion Objet Manifest Locator Label](notion-objet-manifest-locator-label.md)
- [View Health](view-health.md)
- [View Recommendation Plan](view-recommendation-plan.md)
- [Index Health](index-health.md)

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

- [WOM Product Roadmap](product-roadmap.md)
- [Phase 8 Minting Implementation Plan](../plans/phase-8-minting-implementation-plan.md)

Earlier and supporting plans:

- [Phase 2 Implementation Plan](../plans/phase-2-implementation-plan.md)
- [Phase 3 Implementation Plan](../plans/phase-3-implementation-plan.md)
- [Phase 4 Lineage And Trust Plan](../plans/phase-4-lineage-trust-plan.md)
- [Phase 7 Ownership Transfer Plan](../plans/phase-7-ownership-transfer-plan.md)
- [Ownership Lineage Next Thread Prompt](../plans/next-thread-prompt-ownership-lineage.md)

Onboarding and setup plans:

- [AI-Assisted Onboarding And Provider Setup](ai-assisted-onboarding-and-provider-setup.md)
- [Project Intake Session](project-intake-session.md)
- [Project Intake Cookbook](project-intake-cookbook.md)
- [Credential Store Contract](credential-store-contract.md)
- [Credential Ref Inventory And Onboarding](credential-ref-inventory-and-onboarding.md)
- [Credential Store Recommendations](credential-store-recommendations.md)
- [Credential Vault Onboarding Plan](credential-vault-onboarding-plan.md)
- [Beginner Setup Manual](beginner-setup-manual.md)
- [Connected Accounts](connected-accounts.md)
- [Credential Semantic Extraction Recipe](credential-semantic-extraction-recipe.md)
- [Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md)
- [Credential Access Broker Plan](credential-access-broker-plan.md)
- [Credential Access Approval Plan](credential-access-approval-plan.md)
- [Credential Policy Check](credential-policy-check.md)
- [Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md)
- [Credential KeePassXC Write](credential-keepassxc-write.md)
- [Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)
- [Credential Adapter Manifest Plan](credential-adapter-manifest-plan.md)
- [Credential Adapter Audit Plan](credential-adapter-audit-plan.md)
- [Human Artifact Store Contract](human-artifact-store-contract.md)
- [External Export Plan](external-export-plan.md)
- [Connection Import Plan](connection-import-plan.md)
- [Connection Evidence Parser Contract](connection-evidence-parser-contract.md)
- [Connection Evidence Fixture Parser](connection-evidence-fixture-parser.md)
- [Connection Edge Intelligence Plan](connection-edge-intelligence-plan.md)
- [Notion Nested Tree Plan](notion-nested-tree-plan.md)
- [Notion Ancestor Crawl Plan](notion-ancestor-crawl-plan.md)
- [Notion Ancestor Fetch Adapter Execution Contract](notion-ancestor-fetch-adapter-execution-contract.md)
- [Notion Ancestor Fetch Adapter Run](notion-ancestor-fetch-adapter-run.md)
- [Notion Connection Plan](notion-connection-plan.md)
- [Notion OAuth Connection Preflight](notion-oauth-connection-preflight.md)
- [Notion Recover](notion-recover.md)
- [Notion Media Fetch Adapter Execution Contract](notion-media-fetch-adapter-execution-contract.md)
- [Notion Media Result Verification Plan](notion-media-result-verification-plan.md)
- [Notion Block Mirror Tree Fixture Plan](notion-block-mirror-tree-fixture-plan.md)
- [Notion Ancestor Merge Plan](notion-ancestor-merge-plan.md)
- [Notion Client Issue Verification Plan](notion-client-issue-verification-plan.md)
- [Notion Client Fixture Request Plan](notion-client-fixture-request-plan.md)
- [Tiro Import Plan](tiro-import-plan.md)
- [Tiro Lossless Recovery](tiro-lossless-recovery.md)
- [zet Markdown Style Guide](zet-markdown-style-guide.md)
- [Artifact Hygiene](artifact-hygiene.md)
- [Zettel Edge Write](zettel-edge-write.md)
- [Zettel Edge Batch](zettel-edge-batch.md)
- [Object Storage Recommendations](object-storage-recommendations.md)
- [Object Storage Adapter Readiness Plan](object-storage-adapter-readiness-plan.md)
- [Object Storage Operation Request Plan](object-storage-operation-request-plan.md)
- [Object Storage Adapter Execution Contract](object-storage-adapter-execution-contract.md)
- [Object Storage Upload Evidence](object-storage-upload-evidence.md)
- [Object Storage Upload Evidence Audit](object-storage-upload-evidence-audit.md)
- [IMAP Mailbox Source](imap-mailbox-source.md)
- [IMAP Mailbox Operation Request Plan](imap-mailbox-operation-request-plan.md)
- [IMAP Mailbox Adapter Manifest Plan](imap-mailbox-adapter-manifest-plan.md)
- [IMAP Mailbox Adapter Manifest Write](imap-mailbox-adapter-manifest-write.md)
- [IMAP Mailbox Adapter Readiness Plan](imap-mailbox-adapter-readiness-plan.md)
- [IMAP Mailbox Selection Plan](imap-mailbox-selection-plan.md)
- [IMAP Mailbox Adapter Audit Plan](imap-mailbox-adapter-audit-plan.md)
- [IMAP Mailbox Adapter Audit Write](imap-mailbox-adapter-audit-write.md)
- [IMAP Mailbox Adapter Preflight Plan](imap-mailbox-adapter-preflight-plan.md)
- [IMAP Mailbox Adapter Execution Contract](imap-mailbox-adapter-execution-contract.md)
- [IMAP Mailbox Header Metadata Scan](imap-mailbox-header-metadata-scan.md)
- [IMAP Mailbox Header Scan Receipt Audit](imap-mailbox-header-scan-receipt-audit.md)
- [IMAP Mailbox Material Selection Plan](imap-mailbox-material-selection-plan.md)
- [IMAP Mailbox Material Selection Record](imap-mailbox-material-selection-record.md)
- [IMAP Mailbox Material Capture Request Plan](imap-mailbox-material-capture-request-plan.md)
- [IMAP Mailbox Material Capture Execution Contract](imap-mailbox-material-capture-execution-contract.md)
- [IMAP Mailbox Material Capture Approval Plan](imap-mailbox-material-capture-approval-plan.md)
- [IMAP Mailbox Material Capture Approval Audit](imap-mailbox-material-capture-approval-audit.md)
- [Notion Page Snapshot Model](notion-page-snapshot-model.md)
- [Objet Ref Resolution](objet-ref-resolution.md)
- [Zettel Objet Links](zettel-objet-links.md)
- [Notion Objet Link Index](notion-objet-link-index.md)
- [Notion Objet Import Clue Audit](notion-objet-import-clue-audit.md)
- [Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)
- [Notion Objet Link Rewrite Plan](notion-objet-link-rewrite-plan.md)
- [Notion Objet Link Convert](notion-objet-link-convert.md)
- [Notion Objet Manifest Locator Label](notion-objet-manifest-locator-label.md)
- [WOM AI Runtime Skill And Plugin Layer](wom-ai-runtime-skill-plugin-layer.md)
- [WOM Profile Registry](wom-profile-registry.md)
- [WOM Profile Wallet Model](wom-profile-wallet-model.md)
- [Prompt Injection Boundary](prompt-injection-boundary.md)
- [Responsible Use](responsible-use.md)
- [Runtime Model Guidance](runtime-model-guidance.md)
- [Public Release Link Hygiene](public-release-link-hygiene.md)
- [Korean Product Language Baseline](concepts/korean-product-language-baseline.ko.md)
- [Korean Product Language Hygiene](korean-product-language-hygiene.md)
- [Public Privacy Hygiene](public-privacy-hygiene.md)
- [Release Readiness Gate](release-readiness-gate.md)
- [Main Branch Protection Readiness](main-branch-protection-readiness.md)
- [WOM-kit Capability Matrix](capability-matrix.md)
- [View Recommendation Plan](view-recommendation-plan.md)
- [Version Truth Source](version-truth-source.md)
- [Project Version Update](project-version-update.md)
- [zet Catalog One-Process Pass](zet-catalog-one-process-pass.md)
- [Runtime Canonical Entry Points](runtime-canonical-entrypoints.md)
- [Operational Context](operational-context.md)
- [ZET Publication Surface Baseline](zet-publication-surface-baseline.md)
- [ZET Projection Plan Preview](zet-projection-plan-preview.md)
- [ZET Surface Prototypes](zet-surface-prototypes.md)
- [ZET Closed Sharing Model Baseline](zet-closed-sharing-model-baseline.md)
- [ZET Radio-Frequency Recommendation Model](zet-radio-frequency-recommendation-model.md)
- [ZET Shared Update Record Baseline](zet-shared-update-record-baseline.md)
- [ZET Shared Update Record Review Preview](zet-shared-update-record-review-preview.md)
- [ZET Shared Update Record Review Index](zet-shared-update-record-review-index.md)
- [Shared Update Attestation Review Write](shared-update-attestation-review-write.md)
- [Shared Update Route Preview](shared-update-route-preview.md)
- [Shared Update Route Preview Example](shared-update-route-preview-example.md)
- [ZET Transport Threat Model](zet-transport-threat-model.md)
- [v0.2.x Freeze And v0.3.0 Entry Boundary](v02x-freeze-v03-entry-boundary.md)
- [Foreign Block Intake](foreign-block-intake.md)
- [Foreign Block Trust Preview](foreign-block-trust-preview.md)
- [Foreign Block Attestation Packet Preview](foreign-block-attestation-packet.md)
- [Foreign Block Quarantine Plan](foreign-block-quarantine-plan.md)
- [Foreign Block Quarantine Write](foreign-block-quarantine-write.md)
- [Foreign Block Quarantine Review Index](foreign-block-quarantine-review-index.md)
- [Foreign Block Quarantine Decision Preview](foreign-block-quarantine-decision-preview.md)
- [Foreign Block Quarantine Decision Write](foreign-block-quarantine-decision-write.md)
- [Foreign Block Quarantine Decision Review Index](foreign-block-quarantine-decision-review-index.md)
- [Foreign Block Decision Outcome Plan](foreign-block-decision-outcome-plan.md)
- [Foreign Block Attestation Review Candidate Plan](foreign-block-attestation-review-candidate-plan.md)
- [Foreign Block Attestation Statement Draft Decision Preview](foreign-block-attestation-statement-draft-decision-preview.md)
- [One-Command Setup](one-command-setup.md)
- [New User Flow](new-user-flow.md)
- [External Imports](external-imports.md)
- [Derived Text Capture](derived-text.md)
- [Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)
- [Derived Text Completeness Signal](derived-text-completeness-signal.md)

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
- [Foreign Block Quarantine Plan Work Log](../plans/work-log-2026-05-25-foreign-block-quarantine-plan.md)
- [Foreign Block Quarantine Write Work Log](../plans/work-log-2026-05-25-foreign-block-quarantine-write.md)
- [Foreign Block Quarantine Review Index Work Log](../plans/work-log-2026-05-25-foreign-block-quarantine-review-index.md)
- [Foreign Block Quarantine Decision Preview Work Log](../plans/work-log-2026-05-25-foreign-block-quarantine-decision-preview.md)
- [Foreign Block Quarantine Decision Write Work Log](../plans/work-log-2026-05-25-foreign-block-quarantine-decision-write.md)
- [Foreign Block Quarantine Decision Review Index Work Log](../plans/work-log-2026-05-25-foreign-block-quarantine-decision-review-index.md)
- [Foreign Block Decision Outcome Plan Work Log](../plans/work-log-2026-05-25-foreign-block-decision-outcome-plan.md)
- [Foreign Block Attestation Review Candidate Plan Work Log](../plans/work-log-2026-05-25-foreign-block-attestation-review-candidate-plan.md)
- [Foreign Block Attestation Statement Draft Decision Preview Work Log](../plans/work-log-2026-05-26-foreign-block-attestation-statement-draft-decision-preview.md)
- [ZET Publication Surface Baseline Work Log](../plans/work-log-2026-05-26-zet-publication-surface-baseline.md)
- [ZET Projection Plan Preview Work Log](../plans/work-log-2026-05-26-zet-projection-plan-preview.md)
- [ZET Closed Sharing Model Baseline Work Log](../plans/work-log-2026-05-26-zet-closed-sharing-model-baseline.md)
- [ZET Radio-Frequency Recommendation Model Work Log](../plans/work-log-2026-05-27-zet-radio-frequency-recommendation-model.md)
- [Public Release Link Hygiene Work Log](../plans/work-log-2026-05-27-public-release-link-hygiene.md)
- [Korean Product Language Baseline Work Log](../plans/work-log-2026-05-27-korean-product-language-baseline.md)
- [Korean Product Language Hygiene Checker Work Log](../plans/work-log-2026-05-27-korean-product-language-hygiene-checker.md)
- [Public Privacy Hygiene Checker Work Log](../plans/work-log-2026-05-27-public-privacy-hygiene-checker.md)
- [Release Readiness Gate Work Log](../plans/work-log-2026-05-27-release-readiness-gate.md)
- [Main Branch Protection Readiness Work Log](../plans/work-log-2026-05-27-main-branch-protection-readiness.md)
- [ZET Shared Update Record Baseline Work Log](../plans/work-log-2026-05-27-zet-shared-update-record-baseline.md)
- [ZET Shared Update Record Review Preview Work Log](../plans/work-log-2026-05-27-zet-shared-update-record-review-preview.md)
- [Capability Matrix And README Readability Work Log](../plans/work-log-2026-06-02-capability-matrix-readability.md)
- [ZET Shared Update Record Review Index Work Log](../plans/work-log-2026-06-02-shared-update-review-index.md)
- [ZET Transport Threat Model And Would-Plan Work Log](../plans/work-log-2026-06-02-zet-transport-threat-model-would-plan.md)
- [v0.2.x Freeze And v0.3.0 Entry Boundary Work Log](../plans/work-log-2026-06-02-v02x-freeze-v03-entry-boundary.md)
- [Shared Update Attestation Review Write Work Log](../plans/work-log-2026-06-03-shared-update-attestation-review-write.md)
- [Shared Update Route Preview Work Log](../plans/work-log-2026-06-04-shared-update-route-preview.md)
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
- [IMAP Mailbox Adapter Manifest Schema](../schemas/imap-mailbox-adapter-manifest.schema.json)

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
