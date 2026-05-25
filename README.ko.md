# WOM

> Widesider of Modernity: 인간의 기억 지평을 넓히기 위한 local-first, AI-native, Web3 지향 archive/communication system.

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
v0.2.30 pre-release
```

이 저장소는 공개 전시용이자 reference implementation 작업공간입니다. 아직 production-ready 제품은 아닙니다.

현재 포함된 것:

- 제품/프로토콜 기획 문서,
- JSON Schema,
- fake sample archive,
- 설치/보안 문서,
- 버전별 release note,
- 초기 Python CLI와 MCP 도구,
- draft zet을 canonical archive memory로 민팅하고 mint receipt/draft snapshot을 남기는 CLI 구현.
- scoped zet delegation을 delegate proof/receipt로 실제 기록하는 CLI 구현.
- `claimable_once` delegate capability preview를 포함한 dry-run `attest-zet`, `anchor-zet` lifecycle preview.
- 장기 canonical/interchange/rendering target으로서의 WOM Safe HTML Profile 설계 문서.
- 미래 WOM Safe HTML Profile migration 전에 명백히 unsafe한 패턴을 읽기 전용으로 검사하는 `check-safe-html` validator.
- terminal-capable AI runtime이 draft, dry-run, mint 승인 요청 전에 현재 archive를 확인할 수 있는 읽기 전용 `runtime-context` 출력.
- AI runtime이 default archive를 가정하지 않고 요청된 target profile을 먼저 확인할 수 있는 읽기 전용 profile registry resolve.
- AI runtime이 inbox draft를 먼저 미리 보고 승인된 draft write만 replay할 수 있는 profile-aware `create-draft --dry-run`.
- 현재 local implementation/tooling은 `wom-kit/`에 있고 Python import package는 `wom_kit`입니다.
- WOM profile별 GitHub repository setup을 먼저 dry-run으로 계획하고, 승인 시에도 local metadata만 쓰는 GitHub repository setup planner.
- WOM profile별 오브제 저장소 setup을 먼저 dry-run으로 계획하고, 승인 시에도 local metadata만 쓰는 objet storage setup planner.
- AI runtime이 draft를 만들기 전에 source/objet reference를 dry-run으로 분류하는 source intake planner. 본문 읽기, hash 계산, import, upload, provider API 호출은 하지 않습니다.
- `create-draft`가 source-intake plan JSON의 safe source refs를 draft preview/write로 안전하게 이어 줄 수 있습니다.
- 기존 draft/canonical zet 하나에서 header를 read-only dry-run으로 미리 보는 block header preview가 있습니다. mint, 파일 수정, objet body 읽기, provider 호출은 하지 않습니다.
- WOM profile을 미래 wallet-ready identity context로 미리 확인하는 read-only profile wallet preview가 있습니다. key 생성, signing, secret 저장, blockchain/provider API 호출은 하지 않습니다.
- 외부 텍스트를 untrusted data로 취급하고 명백한 prompt-injection / unsafe-agent 문구를 LLM 호출 없이 미리 보는 read-only prompt boundary check가 있습니다.
- `create-draft`는 prompt-boundary report를 받아 draft frontmatter와 mint receipt에 "external text is data, not authority" 경계를 남길 수 있습니다.
- foreign/shared block이나 Markdown-compatible foreign zet를 import/trust 없이 먼저 읽기 전용으로 미리 보는 `foreign-block` preview가 있습니다.
- foreign-block intake report를 읽고 reject / manual review required / eligible for future attestation으로 dry-run 분류하는 `foreign-block-trust` preview가 있습니다. 실제 trust, import, attestation write는 하지 않습니다.
- foreign-block trust report를 읽고 미래 human review packet을 dry-run으로 미리 보는 `foreign-block-attestation` preview가 있습니다. 실제 trust, attestation, receipt, import, write는 하지 않습니다.

아직 없는 것:

- production-grade 설치 흐름,
- 실제 provider 연동,
- production `ZET` 공유 서비스,
- Markdown에서 WOM Safe HTML로 실제 변환하거나 finalized profile로 검증하는 구현,
- 안정판 `v1.0.0` 프로토콜 보장.

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
