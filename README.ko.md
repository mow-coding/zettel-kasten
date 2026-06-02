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
v0.2.58 pre-release
```

이 저장소는 공개 전시용이자 reference implementation 작업공간입니다. 아직 production-ready 제품은 아닙니다.

현재 포함된 것:

- WOM / zet / ZET 설계 기준, specs, schemas, fake archive, release notes, work logs,
- `wom-kit/` 안의 local CLI와 MCP tooling,
- doctor, draft, mint, delegate, receipt, search, metadata review 같은 private archive lifecycle 도구,
- runtime context, profile, source/objet intake, block header, prompt boundary, foreign block review, projection, shared update review/index를 위한 read-only preview layer,
- 사람 승인 뒤에만 동작하는 일부 local write path,
- public link, Korean product language, privacy, release readiness, branch-protection planning을 위한 local hygiene tool.

각 기능이 실제 구현인지, read-only preview인지, 승인 write인지, 문서만 있는지 보려면 [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md)를 보세요.

아직 없는 것:

- production-grade 설치와 platform support,
- live provider integration 또는 provider API sync,
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
- [Public Privacy Hygiene](wom-kit/docs/public-privacy-hygiene.md)
- [Release Readiness Gate](wom-kit/docs/release-readiness-gate.md)
- [Main Branch Protection Readiness](wom-kit/docs/main-branch-protection-readiness.md)
- [ZET Shared Update Record Baseline](wom-kit/docs/zet-shared-update-record-baseline.md)
- [ZET Shared Update Record Review Preview](wom-kit/docs/zet-shared-update-record-review-preview.md)
- [ZET Shared Update Record Review Index](wom-kit/docs/zet-shared-update-record-review-index.md)
- [공개 문서 지도](wom-kit/docs/public-documentation-map.ko.md)

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
v0.3.0
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
