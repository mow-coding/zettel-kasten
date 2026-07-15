# 제품 철학: WOM, zettel-kasten, zet, and ZET

상태: 공개 철학 baseline
날짜: 2026-05-23
갱신: 2026-07-15

이 문서는 WOM, `zettel-kasten`, `zet`, `ZET`의 설계 철학을 설명합니다.

`WOM`은 `Widesider of Modernity`의 약자입니다.

`zettel-kasten`은 역사적 뿌리와 local archive method입니다. `zet`는 그 안에서 민팅되는 단위 문서입니다. `ZET`는 미래의 zettel-kasten 기반 통신 계층입니다.

단순한 기술 명세가 아니라, 왜 이 시스템이 필요한지 설명하는 문서입니다.

더 긴 공개 제품 기획 문서는 다음을 보세요.

- [Foundational Product Whitepaper](foundational-product-whitepaper.md)
- [한국어 Foundational Product Whitepaper](foundational-product-whitepaper.ko.md)
- [WOM 명칭과 용어 기준](naming-and-terminology.ko.md)
- [ZET 공유 Lifecycle 용어](zet-sharing-lifecycle.ko.md)
- [WOM Safe HTML Profile](wom-safe-html-profile.ko.md)

## 1. 핵심 주장

AI에게 필요한 것은 prompt만이 아닙니다.

AI에게는 오래 남고, 검증 가능하며, 사용자가 소유하는 memory가 필요합니다.

WOM은 그 memory를 위한 local-first archive node에서 출발합니다.

`zet`는 원본 자료, AI와의 대화, 사람의 판단을 durable archive memory로 바꾸는 텍스트 단위입니다.

미래의 `ZET` 통신 계층은 선택된 `zet`를 사람, 팀, archive 사이에서 이동시킵니다. 이때 중앙 플랫폼이 유일한 진실의 원천이 되지 않도록 설계합니다.

## 1.1 아티팩트 우선과 인간 변화 원칙

WOM은 기업 온톨로지 시스템에서 출처 추적, 문서 종류 구분, 통제된 쓰기,
영수증, 다시 만들 수 있는 색인 같은 운영 규율을 배웁니다. 그러나 전역
엔티티 매핑을 인간 지식의 최종 권위로 삼지는 않습니다.

기업은 고객, 자산, 거래를 안정된 기준정보로 관리해야 할 때가 많습니다.
반면 WOM의 가장 원초적인 사용자는 인간입니다. 인간은 비일관적이고,
감정적이며, 비합리적일 수 있고, 맥락에 따라 의미를 바꿉니다. 같은
`사과`라는 말도 어제 떠올린 사과와 오늘 떠올린 사과의 의미가 다를 수
있습니다. 그 변화는 지워야 할 불량 데이터가 아니라 기억의 일부입니다.

같은 이름이나 단어가 반복된다는 이유만으로 하나의 고정된 엔티티로
합치면, 보기에는 정돈되었지만 그 사람을 잘못 설명하는 그래프가 생길 수
있습니다. 예쁜 그래프가 거짓 그래프일 수 있습니다.

따라서 WOM은 다음 원칙을 따릅니다.

1. 오래 남는 아티팩트가 일차 근거입니다. 원본 오브제, 대화 기록, 초안,
   zet, 정정, 영수증은 특정 시점에 실제로 무엇이 있었는지 보존합니다.
2. 모순, 모호함, 반복, 수정은 의미 있는 변화의 역사일 수 있습니다.
   자동으로 하나의 표현에 맞춰 지우지 않습니다.
3. `정본(canonical)`은 사용자가 자기 아카이브에서 현재 기준으로 선택한
   생명주기 상태입니다. 객관적이거나 영원한 진실이라는 인증이 아닙니다.
4. 노드, 타이, 엣지, 색인, 생성된 그래프는 읽는 순서, 관계에 대한 주장,
   또는 가설입니다. 그것이 가리키는 아티팩트보다 높은 권위를 갖지
   않습니다.
5. 이름이나 라벨이 같다는 이유만으로 아티팩트를 하나의 엔티티로 자동
   병합하지 않습니다. 동일성이나 관계 제안에는 출처, 범위, 사람 검토가
   필요합니다.
6. AI의 해석은 읽는 시점에 계산되며 더 많은 토큰이나 더 강한 모델로 다시
   만들 수 있습니다. 추론이 달라져도 로컬 아티팩트와 그 변화 이력은 오래
   남습니다.

WOM의 목표는 결정론적 지식을 만드는 것이 아닙니다. 비합리적일 수 있는
인간이 AI의 도움을 받아 자신의 기억, 언어, 판단, 모순, 약속이 시간에 따라
어떻게 변하는지 자각하도록 돕는 것입니다. 이것이 WOM이 해결하려는
인간 중심의 메멘토 문제입니다.

## 2. 인간이 생성하는 데이터의 세 가지 원형

이 프로젝트는 인간이 다루는 데이터를 다음 세 가지 원형으로 봅니다.

```text
텍스트 / 언어
소리
이미지
```

이것은 파일 확장자 분류가 아닙니다. 인간에게 보이는 데이터의 원형입니다.

예시:

- 말은 전사를 통해 텍스트가 될 수 있지만, 원본 소리는 여전히 소리입니다.
- 이미지는 caption이나 OCR을 통해 텍스트로 설명될 수 있지만, 원본 이미지는 여전히 이미지입니다.
- 문서 파일은 텍스트를 담을 수 있지만, 파일 포맷 자체가 가장 깊은 개념 단위는 아닙니다.

이 구분이 중요한 이유는 `zet`가 항상 텍스트이기 때문입니다.

`zet`는 소리, 이미지, 비디오, 파일, 스크린샷, PDF, 문서, 외부 source를 참조할 수 있습니다. 하지만 `zet`가 그 원본 자체가 되는 것은 아닙니다.

archive는 다음 레이어를 구분해서 보존해야 합니다.

```text
original source object
derived text
human interpretation
minted zet
```

## 3. 원본 텍스트와 파생 텍스트

모든 text-like artifact가 같은 권위를 갖는 것은 아닙니다.

권위 위계:

```text
L0 original source object
L1 born-digital editable text
L2 parser-extracted text
L3 OCR / speech-to-text / AI transcription
L4 human-reviewed derived text
L5 minted zet
```

`.hwp`, `.hwpx`, `.docx`, `.txt`, `.md` 같은 문서는 원래부터 편집 가능한 텍스트를 담을 수 있습니다.

반면 스크린샷, 스캔 PDF, 이미지, 영상 프레임에서 나온 OCR 텍스트는 도구나 모델이 추론한 파생 텍스트입니다. 모델이 발전하면 결과가 달라질 수 있습니다.

둘 다 `zettel-kasten`에 보관해야 하지만, provenance는 다르게 기록해야 합니다.

참고:

- `wom-kit/docs/text-provenance-hierarchy.md`
- `wom-kit/docs/source-object-storage-policy.md`

## 4. AX 흐름에서 Zettel-Kasten이 중요한 이유

여기서 AX는 AI Transformation, 즉 일반 소프트웨어 workflow가 AI-assisted operating workflow로 바뀌는 흐름을 뜻합니다.

많은 AX 시도는 기존 앱에 chatbot을 붙이는 방식으로 시작합니다.

이 프로젝트는 다른 전제에서 출발합니다.

```text
AI는 자신이 읽고, 믿고, 행동할 수 있는 memory만큼만 유용하다.
```

archive layer가 없으면 AI와의 대화는 사라집니다.

provenance가 없으면 AI는 무엇이 원본 자료인지, OCR인지, 모델 추론인지, 사람이 고친 것인지, 승인된 결정인지 구분할 수 없습니다.

receipt가 없으면 AI가 한 행동을 감사하기 어렵습니다.

private-first memory layer가 없으면 생각이 정리되기도 전에 SNS적 시선에 의해 왜곡될 수 있습니다.

`zettel-kasten`은 AX를 위한 memory substrate입니다.

```text
source/original data
-> provenance-aware metadata
-> AI-assisted drafts
-> human-reviewed minted zets
-> receipts and versioned archive memory
-> optional sharing, collaboration, and automation
```

목표는 모든 앱을 한 번에 대체하는 것이 아닙니다.

목표는 AI가 흩어진 파일, 사라지는 채팅, 분산된 SaaS silo가 아니라 durable memory 위에서 일하게 만드는 것입니다.

## 5. Zettel-Kasten 메모 철학

전통적인 zettel 사고는 각각의 note를 오래 남는 생각의 단위로 봅니다.

이 프로젝트는 그 생각을 AI-native archive로 확장합니다.

`zet`는 단순한 메모가 아닙니다.

`zet`는 다음을 포함합니다.

```text
text body
+ metadata envelope
+ source references
+ provenance
+ relationships
+ lifecycle state
+ authority and review record
```

사용자는 문서처럼 읽고 써야 합니다.

시스템은 archive object처럼 검사하고 검증해야 합니다.

이것이 이 프로젝트의 메모 철학입니다.

```text
사람이 생각하기에 충분히 읽기 쉽고,
기계가 관리하기에 충분히 구조화되어 있으며,
기억이 되기에 충분히 durable해야 한다.
```

## 6. Private Archive First

기본 시스템은 외부 SNS나 공유 서비스가 없다고 가정합니다.

`zet`를 민팅한다는 것은 다음 뜻입니다.

```text
draft zet -> human review -> private canonical archive record
```

민팅은 게시가 아닙니다.

민팅은 공유가 아닙니다.

민팅은 feed에 올리는 것이 아닙니다.

이 원칙은 사용자의 생각 과정을 보호합니다. private archive가 실수로 performative social media가 되어서는 안 됩니다.

## 7. ZET 공유와 Web3

미래의 `ZET` 통신 계층은 hype가 아니라 인프라 의미에서 Web3-like합니다.

처음부터 token, coin, public blockchain이 필요하다는 뜻이 아닙니다.

여기서 중요한 Web3 원칙은 다음입니다.

- subject-owned identity,
- user-owned data,
- portable records,
- verifiable actions,
- relationship-scoped sharing,
- optional peer-to-peer or relay transport,
- central platform을 유일한 source of truth로 만들지 않기.

이 모델에서:

```text
1:1 ZET 관계       -> 메신저
1:다수 ZET 관계    -> SNS / feed
다수:다수 ZET 관계 -> 협업 워크스페이스
```

하지만 모두 같은 뿌리에서 시작합니다.

```text
private minted zet
-> share envelope
-> scoped capability or copy/access policy
-> recipient archive or client
```

미래 공유의 선호 lifecycle 언어는 다음입니다.

```text
mint -> delegate -> attest -> anchor
```

이 언어에서 `attest`는 좋아요나 동의가 아닙니다. 어떤 foreign `zet`가 특정 issuer, hash, protocol profile, delegated condition으로 존재했다는 것을 recipient archive가 분산 증인으로 기록하는 행위입니다.

`delegate`는 재사용 가능한 public link를 뜻해서는 안 됩니다. 선호 모델은 attestation-bound capability입니다. 이미 알고 있는 counterparty에게 발급하거나, 1회 claim된 뒤 claim한 identity에 귀속되는 방식이어야 합니다. 그래야 탈중앙화된 contact ledger가 보존됩니다. issuer는 자신이 누구에게 delegation했는지 알고, recipient는 누구에게서 받았는지 증명할 수 있습니다.

서버가 존재한다면 transport, discovery, relay, sync를 도울 수 있습니다.

하지만 서버가 사용자의 archive를 canonical하게 소유해서는 안 됩니다.

## 8. 포맷과 SaaS 표면

`zet`는 항상 텍스트입니다. 하지만 텍스트라는 말이 영원히 Markdown-only라는 뜻은 아닙니다.

zettel-kasten의 기본 경험은 CLI/MCP/AI runtime 중심입니다. AI와 함께 쓰고 검사하기에는 강력하지만, 모든 사용자가 원하는 시각적 UI/UX를 처음부터 제공하는 완성형 앱은 아닙니다.

따라서 WOM은 개발자와 사용자가 자기 zettel-kasten 및 `ZET` 기반 SaaS를 직접 만들 수 있도록 열려 있어야 합니다. 예를 들어 gallery, media viewer, feed, workspace, dashboard, research tool, collaboration app을 각자 만들 수 있어야 합니다.

그래서 포맷 문제가 중요합니다. Markdown은 v0.2 authoring/import compatibility에는 좋지만, 장기 canonical/interchange/rendering target은 보안 의식이 반영된 [WOM Safe HTML Profile](wom-safe-html-profile.ko.md)이 되어야 합니다. 이것은 arbitrary HTML을 archive memory에 허용한다는 뜻이 아니라, AI가 읽을 수 있고 deterministic하며 provenance를 보존하고 안전하게 렌더링 가능한 profile을 정의하겠다는 뜻입니다.

## 9. 버전이 있는 공개 체인

공개 repository는 다음의 reference chain입니다.

- code,
- specs,
- schemas,
- release notes,
- upgrade rules,
- public examples.

사용자는 최신 release를 따라갈 수도 있고, 오래된 release에 남을 수도 있습니다.

같은 major protocol version은 호환을 기대할 수 있어야 합니다. 다른 major version은 migration이나 compatibility bridge가 필요할 수 있습니다.

그래서 공개 repository는 신중하게 versioning되어야 합니다.

## 10. 이 프로젝트가 아닌 것

이 프로젝트는 다음이 아닙니다.

- 일반 note app,
- 일반 cloud drive,
- chatbot wrapper,
- public SNS clone,
- blockchain token project,
- 첫날부터 모든 collaboration tool을 대체하려는 프로젝트.

이 프로젝트는 다음을 위한 foundation입니다.

- AI-native private archives,
- provenance-aware zettels,
- local-first memory,
- controlled sharing,
- zets에서 출발해 `ZET`로 확장되는 future messenger/SNS/collaboration layer.

## 11. 구현 순서에 주는 의미

올바른 구현 순서는 다음입니다.

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

가장 어려운 social-network layer부터 시작하면 안 됩니다.

먼저 private memory를 신뢰할 수 있게 만들어야 합니다.
