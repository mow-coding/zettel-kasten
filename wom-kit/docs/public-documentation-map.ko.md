# 공개 문서 지도

상태: 공개 navigation baseline
날짜: 2026-05-27
갱신: 2026-08-22
철학 갱신: 2026-07-15
하네스 호환 경계 갱신: 2026-07-16

현재 v0.4.3 변경점: `ExactOperationManifest v1`이 정확한 승인, checkpoint,
resume, 독립 검증, 필드 단위 revert를 위한 공통 기반을 제공합니다. 기존 Git
계획 계열은 정확한 commit·non-force push·원격 ref 재조회를 추가하고,
`archive migrate`는 Letter 138의 손실 없는 `source_properties` 보강을,
`project-version-update`는 승인에 결속된 영수증을, feedback draft는 CAS
개정과 delivered 이후 새 ID supersession을 제공합니다. 공개 기능의 존재만으로
비공개 보관함의 실제 결과가 증명되지는 않습니다.

Git 백업의 상세 경계: `git-backup-plan`은 제한된 read-only 점검으로
유지됩니다. 기존 `git-backup-reconcile-plan` 명령군에는 모든 변경을 정확히
한 번 분류하는 비공개 그룹 manifest 검증, manifest SHA-256에 묶인 네이티브
사람 승인, literal 경로 상한을 지키는 commit, 저장된 비대화형 인증을 쓰는
일반 non-force push, 정확한 remote ref 재조회, checkpoint resume, content-free
완료 receipt가 추가됩니다. pull, fetch, merge, rebase, reset, clean, delete,
force-push, remote URL/credential 노출, MCP writer는 없습니다. dry-run은 계속
아무것도 쓰지 않으며, 일치한 `ls-remote` 결과는 계정 소유권이나 branch
policy/provider audit log가 아니라 Git transport 근거입니다.

같은 v0.4.3 후보의 Letter 138 변경점(현재 작업 트리에 구현됐지만 아직
릴리스되지 않음):
`archive migrate --target notion-source-properties`가 Letter 138의 로컬
Notion `source_properties` 복구를 계획하고, 승인 후 적용하고, 중단 시 재개하고,
독립 검증하고, 해당 필드만 되돌릴 수 있습니다. 첫 dry-run이 집계 acceptance의
정확한 bytes를 ignored `profiles/local/` 아래에 create-only로 저장하고, 다음 계획은
그 동일 파일과 완전한 로컬 raw mirror를 결속해야 합니다. 적용과 철회는 서로 다른
native exact-human 승인/manifest를 쓰며, 공통 archive writer lock, 승인 직전
canonical projection 재검사, durable checkpoint, 최종 결과 receipt를 재사용합니다.
parser inventory의 approval 가능 표시는 이 target에만 조건부이고 다른 migrate
target의 승인 쓰기는 계속 fixed-close입니다. Notion API를 호출하지 않고
속성값, source page id, 로컬 경로를 출력하지 않습니다. 자세한 운영 절차는
[Notion Source Properties Recovery](notion-source-properties-recovery.md)를 봅니다.

이전 v0.4.2 변경점: `git-backup-plan`과
`git-backup-reconcile-plan`이 제한된 content-free CLI 전용 Git 점검과 remote
ref 재조정 계획을 제공합니다. add, commit, fetch, pull, push, delete, ref
변경은 전혀 하지 않으며 두 명령은 항상 `ready_for_write: false`,
`writer_available: false`, `would_change: []`를 유지합니다. 일치한
`ls-remote` 결과는 Git transport 근거일 뿐 provider 확인이 아닙니다.
v0.4.2는 Letter 139의 read-only 계획 기반만 다루며, 요청된 end-to-end 백업
writer를 구현하지 않습니다.

이전 v0.4.1 쓰기 경계: `zettel-objet-link --approve` 하나에는 작업 전용 로컬
exact-human binding이 있습니다. v0.4.3에서도 대응하는 revert, Objet capture,
project collision, bytecode 쓰기는 계속 고정 차단됩니다. `archive
capabilities --machine`이 parser에서 직접 만든 inventory는 제공된 모든 고정
차단 항목과 일치해야 합니다. 이 inventory는 archive별 선행 조건을 검사하지
않으며, `--approve`가 없다는 사실만으로 read-only라고 단정할 수 없습니다.

과거 v0.4.0 쓰기 경계: compound, batch, revert, archive-authority, durable,
external 범주의 canonical top-level 명령 79개는 각 명령의 plan/dry-run/audit 동작만
유지합니다. 승인 branch는 비공개 target, project, input, credential, provider를
읽기 전에 `compound_exact_human_approval_binding_required`로 실패하며 아무것도
쓰지 않습니다. 제목에 “write”, “revert”, “recovery”가 남은 링크는 미리보기
형태와 과거 receipt를 설명할 뿐, 실행 가능한 승인 지시가 아닙니다.
중첩 derive capture, exact AI 경로가 아닌 draft 생성, 실제 init,
parcel/pack 생성은 별도로 고정 차단됩니다.

과거 v0.4.0 범위 기록: Letter 138은 v0.4.0 기능이 아닌 긴급 후속
범위입니다. 현재 Notion recovery는 page body 또는 location만 다루며 완전한
source mirror가 아니고, 과거 typed-property 유실을 탐지하거나 복구하지
않습니다.

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

또한 WOM의 아티팩트 우선 경계를 설명합니다. 오래 남는 인간의 기록이 다시
만들 수 있는 엔티티·그래프 투영보다 우선하며, 달라지는 의미를 조용히
정규화하지 않고 추적 가능하게 보존합니다.

먼저 볼 문서:

- [WOM 명칭과 용어 기준](concepts/naming-and-terminology.ko.md)
- [WOM Naming And Terminology](concepts/naming-and-terminology.md)
- [한국어 제품 언어 기준선](concepts/korean-product-language-baseline.ko.md)
- [기초 제품 백서](concepts/foundational-product-whitepaper.ko.md)
- [Foundational Product Whitepaper](concepts/foundational-product-whitepaper.md)
- [Product Philosophy](concepts/product-philosophy.md)
- [한국어 Product Philosophy](concepts/product-philosophy.ko.md)
- [WOM 설계 철학 구현 근거](philosophy-implementation-evidence.ko.md)
- [영문 WOM Philosophy Implementation Evidence](philosophy-implementation-evidence.md)
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
- [원문 충실도와 비공개 verbatim 보존](source-fidelity-and-private-verbatim.md)
- [v0.3.313 원문 충실도 결정 기록](archive-infra-decision-log-2026-08-10-v03313-source-fidelity.md)
- [v0.3.314 Letter 126 복구 결정 기록](archive-infra-decision-log-2026-08-11-v03314-letter126.md)
- [v0.3.315 Letter 127 업데이트 미리보기 일치 결정 기록](archive-infra-decision-log-2026-08-11-v03315-letter127.md)
- [v0.3.315 Letter 128 paired batch 결정 기록](archive-infra-decision-log-2026-08-11-v03315-letter128.md)
- [v0.3.316 Letter 129 전체 충돌 집합 복구 결정 기록](archive-infra-decision-log-2026-08-12-v03316-letter129.md)
- [v0.3.317 Letter 130 staged-cleanup 증거 결정 기록](archive-infra-decision-log-2026-08-13-v03317-letter130-staged-cleanup-evidence.md)
- [Letter 131 자격증명 콘솔 paste와 실패 단계](letter131-credential-console-paste-and-failure-stages.md)
- [v0.3.318 Letter 131 자격증명 입력 결정 기록](archive-infra-decision-log-2026-08-13-v03318-letter131-credential-input.md)
- [Letter 132 네이티브 자격증명 팝업과 인과 근거](letter132-credential-console-keyboard-readiness-and-causal-evidence.md)
- [v0.3.319 Letter 132 자격증명 입력 근거 결정 기록](archive-infra-decision-log-2026-08-14-v03319-letter132-credential-input-evidence.md)
- [v0.3.320 자격증명 capability broker 결정 기록](archive-infra-decision-log-2026-08-15-v03320-credential-capability-broker.md)
- [Credential Capability Contract](credential-capability-contract.md)
- [정확한 사람 승인 계약](exact-human-approval-contract.md)
- [v0.4.0 정확한 사람 제어와 운영 마찰 개선 결정](archive-infra-decision-log-2026-08-20-v0400-letter136-operator-friction.md)
- [v0.4.1 Letter 140 정확 링크 복구 결정](archive-infra-decision-log-2026-08-21-v041-letter140-exact-link-recovery.md)
- [v0.4.2 Letter 139 읽기 전용 Git 백업 계획 결정](archive-infra-decision-log-2026-08-21-v042-letter139-read-only-git-backup-planning.md)
- [v0.4.3 Letter 138 Notion source property 복구 결정](archive-infra-decision-log-2026-08-22-v043-letter138-notion-source-properties-recovery.md)
- [Human Artifact Store와 비공개 registry 계약](human-artifact-store-contract.md)
- [프로젝트 버전 업데이트](project-version-update.md)
- [Derived Text Capture와 paired batch 복구](derived-text.md)
- [Letter 120·123 인덱스 수명주기와 피드백 본문](letter120-123-index-lifecycle-and-feedback-body.md)
- [v0.3.312 인덱스 권위와 피드백 본문 결정 기록](archive-infra-decision-log-2026-08-10-v03312-index-authority-and-feedback-body.md)
- [Approval Handoff Lifecycle](approval-handoff-lifecycle.md)
- [Approval Handoff Audit](approval-handoff-audit.md)
- [Operation Status Taxonomy](operation-status-taxonomy.md)
- [제한된 Operation Control](operation-control.md)
- [Input Provenance Taxonomy](input-provenance-taxonomy.md)
- [Secret Signal Taxonomy](secret-signal-taxonomy.md)
- [Local Sovereignty And Backup Authority](local-sovereignty-and-backup-authority.md)
- [로컬 백업 근거 상태](backup-evidence-status.md)
- [Git 백업 계획과 재조정 계획](git-backup-plan.md)
- [AI 스타팅 메뉴얼 빠른 안내와 전체 검진](ai-start-here.md)
- [아카이브 신원 일치 dry-run 점검과 v0.4.0 고정 차단](archive-identity-reconcile.md)
- [빠른 인수인계 문서와 전체 검진](runtime-context-quick-and-full-inspection.md)
- [장시간 명령 진행 표시와 제한된 결과 저장](large-command-progress-and-output.md)
- [AI Response Contract](ai-response-contract.md)
- [Operator Envelope Classes](operator-envelope-classes.md)
- [Objet Capture Enablement](capture-enablement.md)
- [AI 응대 개념 설명 가이드](ai-response-concept-guide.md)
- [zet 초록과 Live Catalog](zet-abstract-catalog.md)
- [zet Catalog 준비 상태 신호](zet-catalog-readiness-signals.md)
- [zet Catalog 규모와 Token Budget](zet-catalog-scale-and-token-budget.md)
- [zet Catalog 응답 Envelope 예산](zet-catalog-response-envelope-budget.md)
- [zet Catalog Compact Continuation](zet-catalog-compact-continuations.md)
- [zet Catalog Pass 임시 파일 수명주기](zet-catalog-pass-artifact-lifecycle.md)
- [zet 초록 보충 계획](zet-abstract-backfill-plan.md)
- [zet 초록 보충 쓰기 미리보기](zet-abstract-backfill-write.md)
- [zet 초록 보충 되돌리기 미리보기](zet-abstract-backfill-revert.md)
- [zet 초록 수정 영수증 전체 검진](zet-abstract-backfill-receipt-audit.md)
- [zet 초록 일괄 작업 읽기 전용 복구 계획](zet-abstract-backfill-recovery-plan.md)
- [zet 초록 일괄 작업 복구 미리보기](zet-abstract-backfill-recover.md)
- [검토된 zet 제목 리맵 계획](zet-title-remap-plan.md)
- [zet 제목 리맵 쓰기 미리보기](zet-title-remap-write.md)
- [zet 제목 리맵 영수증·중단 감사](zet-title-remap-receipt-audit.md)
- [zet 제목 리맵 읽기 전용 복구 판단](zet-title-remap-recovery-plan.md)
- [zet 제목 리맵 단일 사건 복구 미리보기](zet-title-remap-recover.md)
- [zet 제목 리맵 완료 영수증 되돌리기 계획](zet-title-remap-revert-plan.md)
- [zet 제목 리맵 완료 영수증 되돌리기 미리보기](zet-title-remap-revert.md)
- [zet 제목 리맵 되돌리기 중단 복구 계획](zet-title-remap-revert-recovery-plan.md)
- [zet 제목 리맵 되돌리기 중단 복구 미리보기](zet-title-remap-revert-recover.md)
- [연속 Node 읽기](zet-catalog-contiguous-reading.md)
- [Seed 기반 연결 읽기 순서](seeded-connection-reading-order.md)
- [Seed 기반 읽기 경로 근거](seeded-reading-route-evidence.md)
- [Archive Status Board](archive-status-board.md)
- [First-Read Readiness](first-read-readiness.md)
- [명시적 초록 데이터 발행 게이트](explicit-abstract-publication.md)
- [초록 데이터 최신성 검진](abstract-freshness.md)
- [정본 zet 3건 초록 데이터 보완 표본 절차](abstract-backfill-pilot.ko.md)
- [정본 zet 3건 초록 데이터 보완 표본 절차 - English](abstract-backfill-pilot.md)
- [정본 zet 수정 계획](zet-revision-plan.md)
- [정본 zet 수정 쓰기](zet-revision-write.md)
- [정본 zet 수정 이력 검진](zet-revision-receipt-audit.md)
- [이전-상태 보존본에서 복원안 만들기](zet-revision-restore-proposal-from-snapshot.md)
- [정본 zet 복구 계획](zet-revision-restore-plan.md)
- [정본 zet 정확 바이트 복원 쓰기](zet-revision-restore-write.md)
- [Derived Artifact Staleness](derived-artifact-staleness.md)
- [zet Quality Check](zet-quality-check.md)
- [Source Object Storage Policy](source-object-storage-policy.md)
- [Text Provenance Hierarchy](text-provenance-hierarchy.md)
- [Derived Text Capture](derived-text.md)
- [Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)
- [Notion Objet Link Index](notion-objet-link-index.md)
- [Notion Source Properties Recovery](notion-source-properties-recovery.md)
- [Notion Objet Import Clue Audit](notion-objet-import-clue-audit.md)
- [Notion Import Locator-Loss Audit](notion-import-locator-loss-audit.md)
- [Notion Import Locator Evidence Plan](notion-import-locator-evidence-plan.md)
- [AI Command-Path Routing](ai-command-path-routing.md)
- [Checked-Layer Objet Rediscovery Plan](objet-rediscovery-plan.md)
- [Private Objet Metadata And Safe Labels](private-objet-metadata-safe-label.md)
- [Inbox Pipeline Audit](inbox-pipeline-audit.md)
- [Activity-Group Membership Plan](activity-group-membership-plan.md)
- [Activity-Group Membership Removal Plan](activity-group-membership-removal-plan.md)
- [Activity-Group Membership Write And Recovery](activity-group-membership-write.md)
- [Activity-Group Membership Removal Write And Recovery](activity-group-membership-removal-write.md)
- [Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)
- [Notion Objet Link Rewrite Plan](notion-objet-link-rewrite-plan.md)
- [Notion Objet Link Convert](notion-objet-link-convert.md)
- [Notion Objet Manifest Locator Label](notion-objet-manifest-locator-label.md)
- [View Recommendation Plan](view-recommendation-plan.md)
- [Saved-View Write And Exact Revert](saved-view-write.md)

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

- [WOM-kit Python 도구 설치](python-tool-install.ko.md)
- [영문 Python 도구 설치](python-tool-install.md)
- [WOM 아카이브 Agent Skill과 단계별 읽기](runtime-skill-progressive-disclosure.md)
- [AI 호스트에 Agent Skill 설치 또는 제거](runtime-skill-install.ko.md)
- [영문 Agent Skill 호스트 설치 안내](runtime-skill-install.md)
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
- [Credential Capability Contract](credential-capability-contract.md)
- [Credential Access Approval Plan](credential-access-approval-plan.md)
- [Credential Policy Check](credential-policy-check.md)
- [Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md)
- [Credential KeePassXC Write](credential-keepassxc-write.md)
- [Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)
- [Credential Adapter Manifest Plan](credential-adapter-manifest-plan.md)
- [Credential Adapter Audit Plan](credential-adapter-audit-plan.md)
- [편지 118·119 자격 증명 연속성과 검토된 Notion 페이지 회수](letter118-119-credential-continuity-and-notion-page-recovery.md)
- [편지 118·119 자격 증명 수명주기 결정](archive-infra-decision-log-2026-08-10-v03311-letter118-119-credential-lifecycle.md)
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
- [레거시 조율 상태 정리](legacy-coordination-cleanup.md)
- [Letter 115 완료 가이드](letter115-completion.md)
- [Letter 116 완료 가이드](letter116-completion.md)
- [Letter 117 완료 가이드](letter117-completion.md)
- [Artifact Lifecycle Inventory](artifact-lifecycle-inventory.md)
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
- [Notion Import Locator-Loss Audit](notion-import-locator-loss-audit.md)
- [Notion Import Locator Evidence Plan](notion-import-locator-evidence-plan.md)
- [Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)
- [Notion Objet Link Rewrite Plan](notion-objet-link-rewrite-plan.md)
- [Notion Objet Link Convert](notion-objet-link-convert.md)
- [Notion Objet Manifest Locator Label](notion-objet-manifest-locator-label.md)
- [WOM AI Runtime Skill And Plugin Layer](wom-ai-runtime-skill-plugin-layer.md)
- [AI Command-Path Routing](ai-command-path-routing.md)
- [Checked-Layer Objet Rediscovery Plan](objet-rediscovery-plan.md)
- [Inbox Pipeline Audit](inbox-pipeline-audit.md)
- [Activity-Group Membership Plan](activity-group-membership-plan.md)
- [Activity-Group Membership Removal Plan](activity-group-membership-removal-plan.md)
- [Activity-Group Membership Write And Recovery](activity-group-membership-write.md)
- [Activity-Group Membership Removal Write And Recovery](activity-group-membership-removal-write.md)
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
- [Saved-View Write And Exact Revert](saved-view-write.md)
- [Version Truth Source](version-truth-source.md)
- [프로젝트 버전 갱신](project-version-update.md)
- [한 프로세스 zet 카탈로그 완주](zet-catalog-one-process-pass.md)
- [Runtime Canonical Entry Points](runtime-canonical-entrypoints.md)
- [Operational Context](operational-context.md)
- [Session Handoff Checkpoint](session-handoff-checkpoint.md)
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
- [v0.4.6 릴리스 노트](releases/v0.4.6.md)
- [v0.4.5 릴리스 노트](releases/v0.4.5.md)
- [v0.4.4 릴리스 노트](releases/v0.4.4.md)
- [v0.4.3 릴리스 노트](releases/v0.4.3.md)
- [v0.4.2 릴리스 노트](releases/v0.4.2.md)
- [v0.4.1 릴리스 노트](releases/v0.4.1.md)
- [v0.4.0 릴리스 노트](releases/v0.4.0.md)
- [v0.3.320 릴리스 노트](releases/v0.3.320.md)
- [v0.3.308 릴리스 노트](releases/v0.3.308.md)
- [v0.3.309 릴리스 노트](releases/v0.3.309.md)
- [v0.3.310 릴리스 노트](releases/v0.3.310.md)
- [v0.3.311 릴리스 노트](releases/v0.3.311.md)
- [v0.3.312 릴리스 노트](releases/v0.3.312.md)
- [v0.3.313 릴리스 노트](releases/v0.3.313.md)
- [v0.3.314 릴리스 노트](releases/v0.3.314.md)
- [v0.3.315 릴리스 노트](releases/v0.3.315.md)
- [v0.3.316 릴리스 노트](releases/v0.3.316.md)
- [v0.3.317 릴리스 노트](releases/v0.3.317.md)
- [v0.3.319 릴리스 노트](releases/v0.3.319.md)
- [v0.3.318 릴리스 노트](releases/v0.3.318.md)

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
- [Source-Fidelity Draft Receipt Schema](../schemas/source-fidelity-draft-receipt.schema.json)
- [Content-Free CLI Error Envelope Schema](../schemas/cli-error-v0.1.schema.json)
- [Command Approval Status Inventory v0.2 Schema](../schemas/command-approval-status-inventory-v0.2.schema.json)
- [과거 Command Approval Status Inventory v0.1 Schema](../schemas/command-approval-status-inventory-v0.1.schema.json)
- [Exact-Human Operation Approval Schema](../schemas/operation-exact-human-approval-v0.1.schema.json)
- [Zettel-Objet Link Receipt v0.1/v0.2 Reader Schema](../schemas/zettel-objet-link-receipt.schema.json)
- [IMAP Mailbox Adapter Manifest Schema](../schemas/imap-mailbox-adapter-manifest.schema.json)
- [Credential Capability v0.1 Schema](../schemas/credential-capability-v0.1.schema.json)

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
