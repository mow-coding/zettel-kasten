# Zettel-Kasten + Zet

> 로컬 우선, AI-native 아카이브 프로토콜. 개인의 private memory를 오래 남고, 검증 가능하며, 필요한 경우에만 공유 가능한 텍스트로 바꿉니다.

[English README](README.md) · [공개 문서 지도](ai-archive-kit/docs/public-documentation-map.ko.md) · [업그레이드 가이드](UPGRADE.ko.md) · [변경 기록](CHANGELOG.md) · [릴리스 노트](ai-archive-kit/docs/releases/) · [보안 정책](SECURITY.md)

`zettel-kasten`은 중앙 SaaS 서버에 개인/조직의 기억을 통째로 맡기지 않고, 사용자가 자기 아카이브를 직접 소유하면서 AI와 함께 정리할 수 있도록 설계한 시스템입니다.

`zet`는 이 아카이브 안에서 만들어지는 텍스트 중심 단위입니다. 나중에는 이 `zet`가 메시지, SNS 피드, 협업 워크스페이스의 기반이 될 수 있습니다.

## 현재 상태

현재 공개 기준:

```text
v0.2.4 pre-release
```

이 저장소는 공개 전시용이자 reference implementation 작업공간입니다. 아직 production-ready 제품은 아닙니다.

현재 포함된 것:

- 제품/프로토콜 기획 문서,
- JSON Schema,
- fake sample archive,
- 설치/보안 문서,
- 버전별 release note,
- 초기 Python CLI와 MCP 도구.

아직 없는 것:

- production-grade 설치 흐름,
- 실제 provider 연동,
- 최종 minting 구현,
- production `zet` 공유 서비스,
- 안정판 `v1.0.0` 프로토콜 보장.

## 핵심 모델

기본 archive 모델은 다음과 같습니다.

```text
원본/source 데이터 + 메타데이터 + 민팅된 zets
```

쉽게 말하면:

- source/original data는 증거 레이어입니다.
- metadata는 원본을 찾고 검증할 수 있게 해줍니다.
- minted zet는 사람이 승인한 archive memory입니다.

이 시스템은 SNS 앱에서 출발하지 않습니다. 먼저 private archive에서 출발합니다.

인간 데이터 원형, AX 흐름에서의 의미, Web3-like `zet` 공유 모델까지 포함한 전체 설계 철학은 다음 문서를 보세요.

- [Product Philosophy](ai-archive-kit/docs/concepts/product-philosophy.md)
- [한국어 Product Philosophy](ai-archive-kit/docs/concepts/product-philosophy.ko.md)
- [공개 문서 지도](ai-archive-kit/docs/public-documentation-map.ko.md)

공개 프로젝트 기록은 의도적으로 다음처럼 분리합니다.

```text
제품 기획안 / 설계 철학
구현을 위한 레퍼런스 조사
구현 계획
작업일지
```

## Zet란 무엇인가?

`zet`는 항상 텍스트입니다.

사람이 직접 쓰거나, AI가 초안을 만들고 사람이 감독/승인한 Markdown-like 문서입니다. 민팅되면 private archive 안의 공식 기록이 됩니다.

민팅이란:

```text
draft zet -> human review -> canonical private archive record
```

민팅은 공개 게시가 아닙니다. 외부 공유는 별도 행동입니다.

## 왜 중요한가?

대부분의 도구는 사용자를 앱의 구조에 맞추게 합니다.

`zettel-kasten`은 반대로 접근합니다.

```text
사용자의 archive가 중심이고,
AI는 기억을 정리하고 연결하는 조력자이며,
공유는 private memory에서 의도적으로 떼어내는 projection입니다.
```

미래의 `zet` 공유 레이어는 다음 모델을 따릅니다.

```text
1:1 zet 공유       -> 메신저
1:다수 zet 공유    -> SNS / feed
다수:다수 zet 공유 -> 협업 워크스페이스
```

## 저장 모델

객체 스토리지는 사진/영상만 넣는 곳이 아닙니다.

원본으로 사용되는 문서와 캡처도 source object입니다.

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
원본 source 파일 -> local object store 또는 object storage
object identity  -> object manifest
derived text     -> provenance가 있는 derived text record
zets와 metadata  -> Git repository
search text      -> SQLite/search index
```

자세한 내용은 [Source Object Storage Policy](ai-archive-kit/docs/source-object-storage-policy.md)를 보세요.

## 텍스트 provenance

모든 텍스트가 같은 권위를 갖지는 않습니다.

`zettel-kasten`은 텍스트를 다음처럼 구분합니다.

```text
L0 원본 source object
L1 원래부터 편집 가능한 born-digital text
L2 parser로 추출한 text
L3 OCR / 음성인식 / AI 전사 text
L4 사람이 검토한 derived text
L5 minted zet
```

OCR과 AI 전사는 유용하지만, 모델에 따라 달라질 수 있는 derived record입니다. 따라서 source object id, derivation method, tool/model version, confidence, review status를 남겨야 합니다.

자세한 내용은 [Text Provenance Hierarchy](ai-archive-kit/docs/text-provenance-hierarchy.md)를 보세요.

## 버전 관리

`zettel-kasten`과 `zet`는 버전이 있는 protocol family로 관리합니다.

Release tag는 compatibility checkpoint입니다.

```text
v0.2.4
v0.3.0
v1.0.0
```

같은 major version은 핵심 규칙을 공유해야 합니다. 다른 major version 사이에는 migration이나 compatibility bridge가 필요할 수 있습니다.

자세한 내용은 [Versioning](VERSIONING.md)과 [업그레이드 가이드](UPGRADE.ko.md)를 보세요.

## 저장소 구조

```text
ai-archive-kit/
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

- 제품 기획안 / 설계 철학: [공개 문서 지도](ai-archive-kit/docs/public-documentation-map.ko.md)
- 구현을 위한 레퍼런스 조사: [Implementation Research](ai-archive-kit/specs/zettelkasten-zet-implementation-research.md)
- 구현 계획: [Plans Directory](ai-archive-kit/plans/)
- 작업일지: [Work Logs](ai-archive-kit/plans/)

코드부터 보기 전에 프로젝트를 이해하고 싶다면 [공개 문서 지도](ai-archive-kit/docs/public-documentation-map.ko.md)부터 읽는 것을 추천합니다.

## 빠른 검증

```bash
cd ai-archive-kit
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

실제 사용은 private archive repository와 별도 object storage에서 이루어져야 합니다.

자세한 내용은 [Open Source Publication Model](ai-archive-kit/docs/open-source-publication-model.md)을 보세요.

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
