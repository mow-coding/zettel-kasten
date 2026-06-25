# WOM

> Widesider of Modernity: 인간 인식의 지평을 넓히기 위한 local-first, AI-native, Web3 지향 archive/communication system.

[English README](README.md) · [공개 문서 지도](wom-kit/docs/public-documentation-map.ko.md) · [업그레이드 가이드](UPGRADE.ko.md) · [변경 기록](CHANGELOG.md) · [릴리스 노트](wom-kit/docs/releases/) · [보안 정책](SECURITY.md)

`WOM`은 `Widesider of Modernity`의 약자입니다.

이 이름은 modernity의 최전선에서 인간이 인식할 수 있는 지평을 넓히겠다는 의도를 담습니다.

WOM 안에서:

- `zettel-kasten`은 역사적 뿌리이자 local archive method입니다.
- `zet`는 zettel-kasten 안에서 민팅되는 단위 문서입니다.
- `ZET`는 zettel-kasten 기반 통신 계층입니다. 1:1이면 메신저, 1:다수면 SNS/feed, 다수:다수면 협업툴이 될 수 있습니다.
- `node`는 subject/archive participant입니다.
- 선호 lifecycle은 `mint -> delegate -> attest -> anchor`입니다.

`zettel-kasten`은 repository와 archive system의 뿌리로 남지만, 제품 언어는 `WOM`, `zet`, `ZET`, `node`를 중심으로 정리합니다.

## 현재 상태

현재 공개 기준:

```text
v0.3.148 pre-release
```

이전 공개 기준: v0.3.147 pre-release.
이전 공개 기준: v0.3.146 pre-release.
이전 공개 기준: v0.3.145 pre-release.
이전 공개 기준: v0.3.144 pre-release.
이전 공개 기준: v0.3.143 pre-release.
더 이전 공개 기준: v0.3.137 pre-release.
더 이전 공개 기준: v0.3.136 pre-release.
더 이전 공개 기준: v0.3.135 pre-release.
더 이전 공개 기준: v0.3.134 pre-release.
더 이전 공개 기준: v0.3.133 pre-release.

이 저장소는 공개 전시용이자 reference implementation 작업공간입니다. 아직 production-ready 제품은 아닙니다.

현재 포함된 것:

- WOM / zet / ZET 설계 기준, specs, schemas, fake archive, release notes, work logs,
- `wom-kit/` 안의 local CLI와 MCP tooling,
- doctor, draft, mint, delegate, receipt, search, metadata review 같은 private archive lifecycle 도구,
- `zet-self-contained-check`와 AI scratch lifecycle 관리. 공개 외부 인용 URL은 zet 본문이나 `source_refs`에 남길 수 있고, private provider locator와 원본 파일 위치는 여전히 durable WOM ref가 필요하며, `.wom-scratch/`와 `workbench/ai-scratch/`는 git-ignore되는 scratch 영역입니다. 승인된 mint는 명시된 scratch ref를 canonical zet에서 제거하고 cleanup receipt를 남기며 해당 scratch 파일을 소비할 수 있습니다.
- read-only `archive zet-quality-check --dry-run`으로 mint 전 entity-term, document-type, OCR/parse metadata, table-structure, correction-event, source-rights, audience, derived-artifact dependency 위험을 점검합니다. 선택적 `zet-quality-rules.yml` 프로젝트 규칙은 matched term을 출력하지 않으면서 금지 entity alias를 mint blocker로 만들 수 있습니다.
- read-only `archive status-board --dry-run`으로 canonical zet, active draft, retire 대기 minted draft, document/audience metadata gap, source metadata gap, derived-artifact sync gap, 선택적 quality count를 한 번에 요약합니다. title/body/source value/provider URL/local path는 출력하지 않습니다.
- read-only `archive derived-artifact-staleness --dry-run`으로 `derived_artifacts`가 마지막 검토 sync 이후 더 최신 source zet을 놓치고 있는지 확인합니다. 외부 보고서 본문은 열지 않고, artifact ref/title/body/provider URL/local path는 출력하지 않습니다.
- read-only `archive capabilities --machine`으로 AI 운영자가 현재 설치본의 실행 가능한 CLI 명령, alias, 필수 인자, option, nested subcommand, local release identity를 안정된 `ok/state/summary/data/blockers/warnings` 봉투로 확인할 수 있습니다. GitHub나 provider는 호출하지 않습니다.
- `archive doctor`는 archive root의 top-level web/app development artifact와 incomplete `.git` marker를 경고하며, `.gitignore` safe default에 `node_modules/`, `.next/`, `.vercel/`을 포함합니다.
- runtime context, profile, source/objet intake, block header, prompt boundary, foreign block review, projection, shared update review/index, shared update route preview, ZET would-transport planning을 위한 read-only preview layer,
- derived-text coverage/toolchain/doctor/agent-contract read-only gate, PATH에 없는 로컬 추출 도구를 위한 비공개 tool-hint path, 그리고 사람 승인 뒤에만 동작하는 일부 local write path,
- read-only objet reference resolution 및 zettel objet link preview,
- Notion child page/database/view 구조를 `contains` edge type으로 다루는 read-only connection planning, 중첩 child page leaf를 세대 root에 귀속하고 `node_kind` 기반 content class를 보수적으로 도출하며, 큰 fixture가 부분 성공으로 위장하지 않도록 차단하고, 추적불능 parent chain과 조상 crawl 요청 큐를 버리지 않고 보고하며, broad workspace 큐를 generation/ref scope filter로 좁힌 뒤 adapter 입력으로 넘길 수 있게 하고, recursive fetch adapter execution contract를 고정하며, credential approval 뒤에만 동작하는 첫 local Notion ancestor structure fetch adapter로 sanitized ancestor fixture와 non-secret receipt만 쓰고, media byte fetch와 page body capture는 별도 future gate로 남겨두며, 세대가 아직 모르는 untraceable leaf는 generation-id보다 leaf/root/ancestor ref로 좁히라고 안내하고, reviewed block mirror에서 tree fixture preview를 만들고 sanitized ancestor result를 merge/replan하고 sanitized local fixture bundle로 클라이언트 nested-tree issue를 검증하며 클라이언트 follow-up용 최소 sanitized fixture request contract를 패키징하는 read-only nested tree recovery planning, 그리고 맞는 edge type이 없을 때 AI가 억지 매핑하지 않고 model gap으로 올리는 안전 가드,
- mail, OpenAI API, OCR API 등을 위한 read-only beginner setup manual, Notion nested recovery 인간 단계 가이드, `archive notion-recover`의 local `file:<path>` 토큰 파일 fallback(파일 경로와 토큰 값은 출력하지 않음), `archive notion-connection-plan --dry-run`의 one-click Notion connection product contract, `archive notion-oauth-connection-preflight --dry-run`의 secret-blind local OAuth runtime contract preflight, Notion provider failure의 safe action category 분류, live browser OAuth/callback/token exchange/keyring token storage는 아직 future adapter boundary라는 명확한 표시, connected accounts bridge, credential reference planning, inventory, external store recommendation, vault onboarding planning, plaintext migration planning, future access broker planning, local approval receipt preview/write, credential policy checking, KeePassXC command preflight, CLI-only KeePassXC write execution with non-secret execution receipts, adapter readiness planning, adapter manifest preview, adapter audit receipt preview,
- public link, Korean product language, privacy, release readiness, branch-protection planning을 위한 local hygiene tool.

각 기능이 실제 구현인지, read-only preview인지, 승인 write인지, 문서만 있는지 보려면 [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md)를 보세요.

아직 없는 것:

- production-grade 설치와 platform support,
- broad real OS keyring read/write adapter beyond narrow Tiro Windows Credential Manager read, secret retrieval for other providers, OAuth flow, OpenAI API call, paid OCR API call,
- 첫 approval-gated local IMAP header scan과 첫 approval-gated local Notion ancestor structure fetch를 넘어서는 broad live provider sync,
- production `ZET` transport, sharing service, feed update, mirroring delivery,
- real wallet creation, private-key custody, cryptographic signing, token mechanics, payments, staking, consensus, blockchain integration,
- recommendation fetching, ranking, automatic neighbor feed update, provider-backed recommendation service,
- projection-plan apply/write, projection receipt, WordPress publishing, provider-specific publishing,
- real foreign block import/trust/apply, signed attestation statement, receiver-side acceptance, automatic shared-block renewal,
- complete prompt-injection prevention, full-auto execution, model training, backpropagation, Redis, queues, background workers,
- stable `v1.0.0` protocol guarantee.

## 핵심 모델

기본 WOM archive 모델은 다음과 같습니다.

```text
원본/source 데이터 + 메타데이터 + 민팅된 zets
```

쉽게 말하면:

- source/original data는 증거 레이어입니다.
- metadata는 원본을 찾고 검증할 수 있게 해줍니다.
- minted zet는 사람이 승인한 archive memory입니다.

이 시스템은 social app이 아니라 archive node에서 출발합니다.

현재 명칭 기준은 [Naming And Terminology](wom-kit/docs/concepts/naming-and-terminology.ko.md)를 보세요.

인간 데이터 원형, AX 흐름에서의 의미, Web3-like `ZET` 통신 모델까지 포함한 전체 설계 철학은 다음 문서를 보세요.

- [기초 제품 백서](wom-kit/docs/concepts/foundational-product-whitepaper.ko.md)
- [Product Philosophy](wom-kit/docs/concepts/product-philosophy.md)
- [한국어 Product Philosophy](wom-kit/docs/concepts/product-philosophy.ko.md)
- [WOM Safe HTML Profile](wom-kit/docs/concepts/wom-safe-html-profile.ko.md)
- [한국어 제품 언어 기준선](wom-kit/docs/concepts/korean-product-language-baseline.ko.md)
- [한국어 제품 언어 Hygiene](wom-kit/docs/korean-product-language-hygiene.md)
- [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md)
- [Agent Operator Capabilities Manifest](wom-kit/docs/agent-operator-capabilities.md)
- [Archive Status Board](wom-kit/docs/archive-status-board.md)
- [Derived Artifact Staleness](wom-kit/docs/derived-artifact-staleness.md)
- [zet Quality Check](wom-kit/docs/zet-quality-check.md)
- [Public Privacy Hygiene](wom-kit/docs/public-privacy-hygiene.md)
- [Release Readiness Gate](wom-kit/docs/release-readiness-gate.md)
- [Main Branch Protection Readiness](wom-kit/docs/main-branch-protection-readiness.md)
- [ZET Shared Update Record Baseline](wom-kit/docs/zet-shared-update-record-baseline.md)
- [ZET Shared Update Record Review Preview](wom-kit/docs/zet-shared-update-record-review-preview.md)
- [ZET Shared Update Record Review Index](wom-kit/docs/zet-shared-update-record-review-index.md)
- [Shared Update Attestation Review Write](wom-kit/docs/shared-update-attestation-review-write.md)
- [Shared Update Route Preview](wom-kit/docs/shared-update-route-preview.ko.md)
- [ZET Transport Threat Model](wom-kit/docs/zet-transport-threat-model.md)
- [v0.2.x Freeze And v0.3.0 Entry Boundary](wom-kit/docs/v02x-freeze-v03-entry-boundary.md)
- [공개 문서 지도](wom-kit/docs/public-documentation-map.ko.md)
- [Credential Store Contract](wom-kit/docs/credential-store-contract.md)
- [Credential Ref Inventory And Onboarding](wom-kit/docs/credential-ref-inventory-and-onboarding.md)
- [Credential Store Recommendations](wom-kit/docs/credential-store-recommendations.md)
- [Credential Vault Onboarding Plan](wom-kit/docs/credential-vault-onboarding-plan.md)
- [Beginner Setup Manual](wom-kit/docs/beginner-setup-manual.md)
- [Notion Connection Plan](wom-kit/docs/notion-connection-plan.md)
- [Notion OAuth Connection Preflight](wom-kit/docs/notion-oauth-connection-preflight.md)
- [Notion Recover](wom-kit/docs/notion-recover.md)
- [Tiro Import Plan](wom-kit/docs/tiro-import-plan.md)
- [Connected Accounts](wom-kit/docs/connected-accounts.md)
- [Credential Plaintext Migration Plan](wom-kit/docs/credential-plaintext-migration-plan.md)
- [Credential Access Broker Plan](wom-kit/docs/credential-access-broker-plan.md)
- [Credential Access Approval Plan](wom-kit/docs/credential-access-approval-plan.md)
- [Credential Policy Check](wom-kit/docs/credential-policy-check.md)
- [Credential KeePassXC Command Plan](wom-kit/docs/credential-keepassxc-command-plan.md)
- [Credential KeePassXC Write](wom-kit/docs/credential-keepassxc-write.md)
- [Credential Adapter Readiness Plan](wom-kit/docs/credential-adapter-readiness-plan.md)
- [Credential Adapter Manifest Plan](wom-kit/docs/credential-adapter-manifest-plan.md)
- [Credential Adapter Audit Plan](wom-kit/docs/credential-adapter-audit-plan.md)
- [Human Artifact Store Contract](wom-kit/docs/human-artifact-store-contract.md)
- [Object Storage Recommendations](wom-kit/docs/object-storage-recommendations.md)
- [IMAP Mailbox Source](wom-kit/docs/imap-mailbox-source.md)
- [Zettel Objet Links](wom-kit/docs/zettel-objet-links.md)
- [Derived Text Coverage And Toolchain](wom-kit/docs/derived-text-coverage-and-toolchain.md)

공개 프로젝트 기록은 의도적으로 다음처럼 분리합니다.

```text
제품 기획안 / 설계 철학
구현을 위한 레퍼런스 조사
구현 계획
작업일지
```

## zet란 무엇인가?

`zet`는 항상 텍스트입니다.

사람이 직접 쓰거나, AI가 초안을 만들고 사람이 감독/승인한 문서입니다. 민팅되면 private archive 안의 공식 기록이 됩니다.

v0.2에서는 authoring/import compatibility를 위해 Markdown 기반 zets를 유지합니다. 장기 canonical/interchange/rendering target은 arbitrary HTML이 아니라 [WOM Safe HTML Profile](wom-kit/docs/concepts/wom-safe-html-profile.ko.md)입니다.

민팅이란:

```text
draft zet -> human review -> canonical private archive record
```

민팅은 공개 게시가 아닙니다. 외부 공유는 별도 행동입니다.

## 왜 중요한가?

대부분의 도구는 사용자를 앱의 구조에 맞추게 합니다.

WOM은 반대로 접근합니다.

```text
사용자의 archive가 중심이고,
AI는 기억을 정리하고 연결하는 조력자이며,
공유는 private memory에서 의도적으로 떼어내는 projection입니다.
```

미래의 `ZET` 통신 계층은 다음 모델을 따릅니다.

```text
1:1 ZET 관계       -> 메신저
1:다수 ZET 관계    -> SNS / feed
다수:다수 ZET 관계 -> 협업 워크스페이스
```

## 저장 모델

오브제 저장소는 사진/영상만 넣는 곳이 아닙니다.

WOM 제품 언어에서 Git 밖에 두는 source/original file은 `objet`/오브제입니다. Cloud provider API에서만 기술 용어 `object storage`를 씁니다.

원본으로 사용되는 문서와 캡처도 source/original objet입니다.

- `.hwp`
- `.hwpx`
- `.docx`
- `.xlsx`
- `.pdf`
- `.txt`
- `.md`
- `.csv`
- 스크린샷
- 오디오/비디오
- provider export

추천 기본 구조:

```text
원본 source 파일 -> local objet store 또는 object storage provider
object identity  -> object manifest
derived text     -> provenance가 있는 derived text record
zets와 metadata  -> Git repository
search text      -> SQLite/search index
```

자세한 내용은 [Source Object Storage Policy](wom-kit/docs/source-object-storage-policy.md)를 보세요.

## 텍스트 provenance

모든 텍스트가 같은 권위를 갖지는 않습니다.

WOM은 텍스트를 다음처럼 구분합니다.

```text
L0 원본 source object
L1 원래부터 편집 가능한 born-digital text
L2 parser로 추출한 text
L3 OCR / 음성인식 / AI 전사 text
L4 사람이 검토한 derived text
L5 minted zet
```

OCR과 AI 전사는 유용하지만, 모델에 따라 달라질 수 있는 derived record입니다. 따라서 source object id, derivation method, tool/model version, confidence, review status를 남겨야 합니다.

자세한 내용은 [Text Provenance Hierarchy](wom-kit/docs/text-provenance-hierarchy.md)를 보세요.

## 버전 관리

WOM, `zettel-kasten`, `zet`, `ZET`는 버전이 있는 protocol family로 관리합니다.

Release tag는 compatibility checkpoint입니다.

```text
v0.3.148
v0.3.147
v0.3.146
v0.3.145
v0.3.144
v0.3.143
v0.3.137
v0.3.136
v0.3.135
v0.3.134
v0.3.133
v0.3.132
v0.3.131
v0.3.130
v0.3.129
v0.3.128
v0.3.127
v0.3.126
v0.3.125
v0.3.124
v0.3.123
v0.3.122
v0.3.121
v0.3.120
v0.3.119
v0.3.118
v0.3.117
v0.3.116
v0.3.115
v0.3.114
v0.3.113
v0.3.112
v0.3.111
v0.3.110
v0.3.109
v0.3.108
v0.3.107
v0.3.106
v0.3.105
v0.3.104
v0.3.103
v0.3.102
v0.3.101
v0.3.100
v0.3.99
v0.3.98
v0.3.97
v0.3.96
v0.3.95
v0.3.94
v0.3.93
v0.3.92
v0.3.91
v0.3.90
v0.3.89
v0.3.88
v0.3.87
v0.3.86
v0.3.85
v0.3.84
v0.3.83
v0.3.82
v0.3.81
v0.3.80
v0.3.79
v0.3.78
v0.3.77
v0.3.76
v0.3.75
v0.3.74
v0.3.73
v0.3.72
v0.3.71
v0.3.70
v0.3.69
v0.3.68
v0.3.67
v0.3.66
v0.3.65
v0.3.64
v0.3.63
v0.3.62
v0.3.61
v0.3.60
v0.3.59
v0.3.58
v0.3.57
v0.3.56
v0.3.55
v0.3.54
v0.3.53
v0.3.52
v0.3.51
v0.3.50
v0.3.49
v0.3.48
v0.3.47
v0.3.46
v0.3.45
v0.3.44
v0.3.43
v0.3.42
v0.3.41
v0.3.38
v0.3.37
v0.3.31
v0.3.30
v0.3.29
v0.3.28
v0.3.27
v0.3.26
v0.3.25
v0.3.24
v0.3.23
v0.3.22
v0.3.21
v0.3.20
v0.3.19
v0.3.18
v0.3.17
v0.3.16
v0.3.15
v0.3.14
v0.3.13
v0.3.12
v0.3.11
v0.3.10
v0.3.9
v0.3.8
v0.3.7
v0.3.6
v0.3.5
v0.3.4
v0.3.3
v0.3.2
v0.3.1
v0.3.0
v0.2.60
v0.2.59
v0.2.58
v0.2.57
v0.2.56
v0.2.55
v0.2.54
v0.2.53
v0.2.52
v0.2.51
v0.2.50
v0.2.49
v0.2.48
v0.2.47
v0.2.46
v0.2.45
v0.2.44
v0.2.43
v0.2.42
v0.2.41
v0.2.40
v0.2.39
v0.2.38
v0.2.37
v0.2.36
v0.2.35
v0.2.34
v0.2.33
v0.2.32
v0.2.31
v0.2.30
v0.2.29
v0.2.28
v0.2.27
v0.2.26
v0.2.25
v0.2.24
v0.2.23
v0.2.22
v0.2.21
v0.2.20
v0.2.18
v0.2.17
v0.2.16
v0.2.15
v0.2.14
v0.2.13
v0.2.12
v0.2.11
v0.2.10
v0.2.9
v1.0.0
```

같은 major version은 핵심 규칙을 공유해야 합니다. 다른 major version 사이에는 migration이나 compatibility bridge가 필요할 수 있습니다.

자세한 내용은 [Versioning](VERSIONING.md)과 [업그레이드 가이드](UPGRADE.ko.md)를 보세요.

## 저장소 구조

```text
wom-kit/
  specs/        제품/프로토콜 명세
  docs/         설치, 보안, 온보딩, 릴리스, 운영 문서
  plans/        구현 계획과 공개 가능한 작업일지
  schemas/      JSON Schema
  src/          Python package code
  cli/          local CLI entrypoint
  examples/     fake sample archive data
  templates/    personal, family, company archive template
```

## 공개 문서 지도

공개 문서는 목적에 따라 나뉩니다.

- 제품 기획안 / 설계 철학: [공개 문서 지도](wom-kit/docs/public-documentation-map.ko.md)
- 구현을 위한 레퍼런스 조사: [Implementation Research](wom-kit/specs/zettelkasten-zet-implementation-research.md)
- 구현 계획: [Plans Directory](wom-kit/plans/)
- 작업일지: [Work Logs](wom-kit/plans/)

코드부터 보기 전에 프로젝트를 이해하고 싶다면 [공개 문서 지도](wom-kit/docs/public-documentation-map.ko.md)부터 읽는 것을 추천합니다.

## 빠른 검증

```bash
cd wom-kit
python -m unittest discover -s tests
python cli/archive.py doctor examples/fake-life-archive --strict
```

기대 결과:

```text
tests pass
doctor reports 0 errors and 0 warnings
```

## 공개/비공개 경계

이 공개 저장소는 실제 사용자의 private archive가 아닙니다.

커밋하면 안 되는 것:

- provider token,
- local credential,
- 실제 private zet,
- 실제 source map,
- 실제 receipt,
- private AI conversation,
- 개인 파일이나 미디어,
- 로컬 PC 경로 또는 private filename.

실제 사용은 private archive repository와 별도 오브제 저장소/object storage provider에서 이루어져야 합니다.

자세한 내용은 [Open Source Publication Model](wom-kit/docs/open-source-publication-model.md)을 보세요.

## 저자

Original concept, product philosophy, naming, written design, schemas, reference implementation:

```text
Kim Seong Kyun (김성균)
Department of Urban Sociology, University of Seoul
GitHub: mow-coding
Email: mow.coding@gmail.com
Email: ellie0129@uos.ac.kr
```

이 프로젝트가 도움이 되었다면 GitHub star를 남겨주세요. 협업 및 투자 문의는 이메일로 연락할 수 있습니다.

## 라이선스

MIT License. [LICENSE](LICENSE)를 확인하세요.
