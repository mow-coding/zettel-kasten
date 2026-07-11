# 공개 문서 지도

상태: 공개 navigation baseline
날짜: 2026-05-27

이 저장소는 공개 프로젝트 기록을 의도적으로 네 종류로 나눕니다.

```text
1. 제품 기획안 / 설계 철학
2. 구현을 위한 레퍼런스 조사
3. 구현 계획
4. 작업일지
```

이 구분은 프로젝트 철학의 일부입니다. 공개 저장소는 코드만 보여주는 곳이 아닙니다. 왜 이 시스템이 필요한지, 어떤 레퍼런스를 참고했는지, 어떻게 구현할 것인지, 지금까지 어떤 작업을 했는지를 함께 보여줘야 합니다.

## 1. 제품 기획안 / 설계 철학

이 문서들은 concept, 제품 철학, archive model, `ZET` 통신 모델을 설명합니다.

먼저 볼 문서:

- [WOM 명칭과 용어 기준](concepts/naming-and-terminology.ko.md)
- [WOM Naming And Terminology](concepts/naming-and-terminology.md)
- [한국어 제품 언어 기준선](concepts/korean-product-language-baseline.ko.md)
- [기초 제품 백서](concepts/foundational-product-whitepaper.ko.md)
- [Foundational Product Whitepaper](concepts/foundational-product-whitepaper.md)
- [Product Philosophy](concepts/product-philosophy.md)
- [한국어 Product Philosophy](concepts/product-philosophy.ko.md)
- [WOM Safe HTML Profile](concepts/wom-safe-html-profile.md)
- [한국어 WOM Safe HTML Profile](concepts/wom-safe-html-profile.ko.md)
- [ZET Sharing Lifecycle Terminology](concepts/zet-sharing-lifecycle.md)
- [한국어 ZET Sharing Lifecycle Terminology](concepts/zet-sharing-lifecycle.ko.md)
- [Zettel-Kasten, zet, and ZET Product Blueprint](../specs/zettelkasten-zet-product-blueprint.md)

보조 철학/모델 문서:

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
- [AI Response Contract](ai-response-contract.md)
- [Operator Envelope Classes](operator-envelope-classes.md)
- [Objet Capture Enablement](capture-enablement.md)
- [AI 응대 개념 설명 가이드](ai-response-concept-guide.md)
- [zet 초록과 Live Catalog](zet-abstract-catalog.md)
- [zet Catalog 준비 상태 신호](zet-catalog-readiness-signals.md)
- [zet Catalog 규모와 Token Budget](zet-catalog-scale-and-token-budget.md)
- [zet Catalog 응답 Envelope 예산](zet-catalog-response-envelope-budget.md)
- [zet Catalog Compact Continuation](zet-catalog-compact-continuations.md)
- [연속 Node 읽기](zet-catalog-contiguous-reading.md)
- [Seed 기반 연결 읽기 순서](seeded-connection-reading-order.md)
- [Seed 기반 읽기 경로 근거](seeded-reading-route-evidence.md)
- [Archive Status Board](archive-status-board.md)
- [Derived Artifact Staleness](derived-artifact-staleness.md)
- [zet Quality Check](zet-quality-check.md)
- [Source Object Storage Policy](source-object-storage-policy.md)
- [Text Provenance Hierarchy](text-provenance-hierarchy.md)
- [Derived Text Capture](derived-text.md)
- [Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)
- [Notion Objet Link Index](notion-objet-link-index.md)
- [Notion Objet Import Clue Audit](notion-objet-import-clue-audit.md)
- [Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)
- [Notion Objet Link Rewrite Plan](notion-objet-link-rewrite-plan.md)
- [Notion Objet Link Convert](notion-objet-link-convert.md)
- [Notion Objet Manifest Locator Label](notion-objet-manifest-locator-label.md)
- [View Recommendation Plan](view-recommendation-plan.md)

이 문서들이 다루는 내용:

- 인간이 생성하는 데이터의 세 원형: 텍스트/언어, 소리, 이미지,
- 왜 `zet`는 항상 텍스트인지,
- 왜 source/original data와 minted zet를 분리해야 하는지,
- 왜 social sharing보다 private archive memory가 먼저인지,
- 왜 `WOM`, `zet`, `ZET`, `node`를 제품 언어의 중심축으로 삼는지,
- 왜 미래 공유 동사를 `mint -> delegate -> attest -> anchor`로 잡는지,
- `ZET` 공유가 어떻게 messenger, SNS/feed, collaboration workspace로 확장되는지,
- 왜 Markdown은 authoring/import compatibility로 유지하고 WOM Safe HTML Profile은 장기 canonical/interchange/rendering target으로 삼는지,
- 이 모델이 AX, 즉 AI Transformation 흐름에서 왜 중요한지.
- 같은 authority model이 어떻게 HITL workflow와 제한된 AI-agent harness를 함께 지원하는지.

## 2. 구현을 위한 레퍼런스 조사

이 문서는 제품 아이디어를 기존 표준, 프로토콜, 오픈소스 레퍼런스와 연결합니다.

주요 리서치 문서:

- [Implementation Research](../specs/zettelkasten-zet-implementation-research.md)

다루는 레퍼런스 예시:

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

목적은 이 프로젝트가 모든 기술 요소를 처음 발명했다고 주장하는 것이 아닙니다. 좋은 레퍼런스를 공부하고 재사용해서 맨땅에서 시작하지 않기 위함입니다.

## 3. 구현 계획

이 문서들은 프로젝트를 어떤 순서로 구현할지 설명합니다.

현재 주요 계획:

- [Phase 8 Minting Implementation Plan](../plans/phase-8-minting-implementation-plan.md)

이전/보조 계획:

- [Phase 2 Implementation Plan](../plans/phase-2-implementation-plan.md)
- [Phase 3 Implementation Plan](../plans/phase-3-implementation-plan.md)
- [Phase 4 Lineage And Trust Plan](../plans/phase-4-lineage-trust-plan.md)
- [Phase 7 Ownership Transfer Plan](../plans/phase-7-ownership-transfer-plan.md)
- [Ownership Lineage Next Thread Prompt](../plans/next-thread-prompt-ownership-lineage.md)

온보딩/설치 계획:

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
- [Notion Objet Link Index](notion-objet-link-index.md)
- [Notion Objet Import Clue Audit](notion-objet-import-clue-audit.md)
- [Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)
- [Notion Objet Link Rewrite Plan](notion-objet-link-rewrite-plan.md)
- [Notion Objet Link Convert](notion-objet-link-convert.md)
- [Notion Objet Manifest Locator Label](notion-objet-manifest-locator-label.md)
- [WOM AI Runtime Skill And Plugin Layer](wom-ai-runtime-skill-plugin-layer.md)
- [WOM Profile Registry](wom-profile-registry.md)
- [WOM Profile Wallet Model](wom-profile-wallet-model.md)
- [Prompt Injection Boundary](prompt-injection-boundary.ko.md)
- [Responsible Use](responsible-use.ko.md)
- [Runtime Model Guidance](runtime-model-guidance.ko.md)
- [Public Release Link Hygiene](public-release-link-hygiene.md)
- [Public Privacy Hygiene](public-privacy-hygiene.md)
- [Release Readiness Gate](release-readiness-gate.md)
- [Main Branch Protection Readiness](main-branch-protection-readiness.md)
- [WOM-kit Capability Matrix](capability-matrix.md)
- [View Recommendation Plan](view-recommendation-plan.md)
- [Version Truth Source](version-truth-source.md)
- [Runtime Canonical Entry Points](runtime-canonical-entrypoints.md)
- [Operational Context](operational-context.md)
- [한국어 제품 언어 기준선](concepts/korean-product-language-baseline.ko.md)
- [한국어 제품 언어 Hygiene](korean-product-language-hygiene.md)
- [ZET Publication Surface Baseline](zet-publication-surface-baseline.md)
- [ZET Projection Plan Preview](zet-projection-plan-preview.md)
- [ZET Surface Prototypes](zet-surface-prototypes.md)
- [ZET Closed Sharing Model Baseline](zet-closed-sharing-model-baseline.md)
- [ZET Radio-Frequency Recommendation Model](zet-radio-frequency-recommendation-model.md)
- [ZET Shared Update Record Baseline](zet-shared-update-record-baseline.md)
- [ZET Shared Update Record Review Preview](zet-shared-update-record-review-preview.md)
- [ZET Shared Update Record Review Index](zet-shared-update-record-review-index.md)
- [Shared Update Attestation Review Write](shared-update-attestation-review-write.md)
- [Shared Update Route Preview](shared-update-route-preview.ko.md)
- [Shared Update Route Preview Example](shared-update-route-preview-example.ko.md)
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

현재 구현 우선순위:

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

## 4. 작업일지

이 문서들은 공개 가능한 작업 기록입니다.

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
- [한국어 제품 언어 기준선 작업일지](../plans/work-log-2026-05-27-korean-product-language-baseline.md)
- [한국어 제품 언어 Hygiene Checker 작업일지](../plans/work-log-2026-05-27-korean-product-language-hygiene-checker.md)
- [Draft Provenance Work Log](../plans/work-log-2026-05-24-draft-provenance.md)
- [WOM-kit Naming Cleanup Work Log](../plans/work-log-2026-05-25-wom-kit-naming-cleanup.md)
- [Delegate Capability Binding Work Log](../plans/work-log-2026-05-23-delegate-capability-binding.md)
- [v0.2.11 Delegate Capability Contract Work Log](../plans/work-log-2026-05-23-delegate-capability-contract.md)
- [Changelog](../../CHANGELOG.md)
- [Release Notes](releases/)

작업일지는 제품 명세가 아닙니다.

작업일지는 미래 기여자가 다음을 알 수 있게 하기 위한 기록입니다.

- 무엇이 바뀌었는지,
- 왜 바뀌었는지,
- 무엇을 검증했는지,
- 아직 무엇이 남았는지.

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

이 문서들은 구현 계약에 가깝습니다. 제품 철학 문서보다 더 정확하고 엄격해야 합니다.

## 6. 공개/비공개 경계

모든 프로젝트 기록이 공개 저장소에 들어가야 하는 것은 아닙니다.

공개:

- 제품 철학,
- 공개 가능한 설계 기획안,
- 구현 레퍼런스 조사,
- 구현 계획,
- 공개 가능한 작업일지,
- fake examples,
- schemas,
- source code.

비공개:

- 실제 사용자 archive,
- 실제 zets,
- 실제 source maps,
- 실제 receipts,
- provider tokens,
- local filesystem paths,
- private AI conversations,
- 민감 맥락이 포함된 private meeting minutes.

참고:

- [Open Source Publication Model](open-source-publication-model.md)
- [Security Policy](../../SECURITY.md)
- [Disclaimer](../../DISCLAIMER.md)
