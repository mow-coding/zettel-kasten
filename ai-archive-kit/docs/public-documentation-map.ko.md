# 공개 문서 지도

상태: 공개 navigation baseline
날짜: 2026-05-23

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
- [Source Object Storage Policy](source-object-storage-policy.md)
- [Text Provenance Hierarchy](text-provenance-hierarchy.md)

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
- [One-Command Setup](one-command-setup.md)
- [New User Flow](new-user-flow.md)
- [External Imports](external-imports.md)

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
