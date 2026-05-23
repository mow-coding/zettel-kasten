# 기초 제품 백서: WOM, Zettel-Kasten, And Zet

상태: 공개 제품 기획 기준선
날짜: 2026-05-23
버전 맥락: v0.2.7 planning document

이 문서는 WOM, `zettel-kasten`, `zet`의 상세한 공개 제품 철학 문서입니다.

`WOM`은 `Widesider of Modernity`의 약자입니다. modernity의 최전선에서 인간이 인식할 수 있는 지평을 넓히겠다는 의도를 담습니다.

`zettel-kasten`은 역사적 뿌리와 archive method입니다. `zet`는 active product primitive입니다.

구현 세부사항보다 먼저, 이 시스템이 무엇인지, 왜 필요한지, 인간과 AI에 대해 어떤 전제를 갖는지, 그리고 같은 구조가 어떻게 private archive, HITL workflow, AI-agent harness, 메신저, SNS, 협업툴로 확장될 수 있는지를 설명합니다.

## 1. 핵심 주장

AI에게 필요한 것은 더 좋은 prompt만이 아닙니다.

AI에게는 오래 남고, 검증 가능하며, 출처를 확인할 수 있고, 수정 이력을 남길 수 있으며, 행동의 근거로 삼을 수 있는 memory가 필요합니다.

인간에게도 그런 memory가 필요합니다.

지금의 기억은 로컬 폴더, 구글 드라이브, 노션, 슬랙, 깃허브, 이메일, 스크린샷, 휴대폰 사진첩, AI 채팅 기록 사이에 흩어져 있습니다.

`zettel-kasten`은 이 기억을 위한 local-first, subject-owned archive system입니다.

`zet`는 원본 자료, AI와의 대화, 사용자의 판단을 durable archive memory로 바꾸는 텍스트 중심 단위입니다.

미래의 `zet` 공유 레이어는 선택된 zets를 사람, 조직, 기기, agent, archive 사이에서 이동시키되 중앙 플랫폼이 사용자의 기억을 canonical하게 소유하지 않도록 설계합니다.

기본 모델은 다음과 같습니다.

```text
원본/source 데이터
+ 메타데이터
+ 민팅된 zets
+ receipts
+ 공유 가능한 envelopes
```

이것은 단순한 메모 앱 아이디어가 아닙니다.

이것은 memory infrastructure 아이디어입니다.

## 2. 문제의식

대부분의 도구는 기억을 서로 호환되지 않는 조각으로 나눕니다.

파일은 로컬 폴더, Google Drive, Notion, Slack, GitHub, 이메일, 스크린샷, 휴대폰 사진첩, 채팅 기록에 흩어집니다.

AI 대화는 유용한 통찰을 만들 수 있지만, 그 통찰은 transient chat history 안에 머무르는 경우가 많습니다. 출처, 승인 여부, revision history, 검토 상태를 가진 durable record로 바뀌지 못합니다.

많은 클라우드 앱은 앱을 중심에 둡니다.

```text
app first
user memory second
AI as a feature inside the app
```

이 프로젝트는 순서를 뒤집습니다.

```text
user archive first
AI as an operator over that archive
apps as optional surfaces
sharing as deliberate projection
```

문제는 사람들이 파일을 저장할 장소가 없다는 것이 아닙니다.

문제는 원본 데이터, 해석, 결정, 미래 행동을 연결할 수 있는 durable하고 inspectable한 AI-native memory layer가 부족하다는 것입니다.

## 3. Subject-Owned Archive

모든 subject는 archive를 가질 수 있습니다.

여기서 subject는 다음이 될 수 있습니다.

- 개인,
- 가족,
- 팀,
- 회사,
- 프로젝트,
- 기관,
- 위임된 agent identity,
- 또는 기억과 권한을 가질 수 있는 다른 경계 있는 주체.

따라서 최초 실행 시 만드는 archive는 개인 archive일 수도 있고 조직 archive일 수도 있습니다.

이 설계는 다음 환경을 모두 고려합니다.

- 개인 노트북,
- 회사 워크스테이션,
- 공용 태블릿,
- 가족 archive 서버,
- 팀 워크스페이스 머신,
- AI가 운영하는 환경.

archive는 단순한 폴더가 아닙니다.

archive는 구조화된 memory boundary입니다.

```text
이 기억은 누가 소유하는가?
어떤 원본 자료를 참조하는가?
어떤 zets가 canonical한가?
누가 승인했는가?
무엇이 언제 바뀌었는가?
무엇을 공유할 수 있는가?
무엇은 private으로 남아야 하는가?
```

## 4. 인간 데이터 원형

이 프로젝트는 인간이 다루는 데이터를 세 가지 원형으로 봅니다.

```text
텍스트 / 언어
소리
이미지
```

이것은 파일 확장자 분류가 아닙니다.

개념적 원형입니다.

말소리는 transcription을 통해 텍스트가 될 수 있지만, 원본 소리는 여전히 소리입니다.

음악이나 소음은 분석되거나 라벨링되거나 악보로 변환될 수 있지만, 원본 acoustic signal은 여전히 소리입니다.

이미지는 caption, OCR, embedding, AI 설명으로 표현될 수 있지만, 원본 이미지는 여전히 이미지입니다.

스프레드시트 스크린샷은 표 형태의 텍스트로 복원될 수 있지만, 스크린샷 자체는 이미지 source object입니다. 추출된 표는 derived record입니다.

이 구분이 중요한 이유는 `zet`가 항상 텍스트이기 때문입니다.

`zet`는 해석된 지도이지 raw territory가 아닙니다.

`zet`는 원본 자료를 인용하고, 설명하고, 요약하고, 연결하고, 판단할 수 있지만, 원본 자료 그 자체인 척해서는 안 됩니다.

## 5. 원본 데이터와 파생 텍스트

archive는 모든 text-like artifact를 같은 층위로 평평하게 취급해서는 안 됩니다.

권장 authority ladder는 다음과 같습니다.

```text
L0 original source object
L1 born-digital editable text
L2 parser-extracted text
L3 OCR / speech-to-text / AI transcription
L4 human-reviewed derived text
L5 minted zet
```

예시:

- `.txt`, `.md`, `.hwp`, `.hwpx`, `.docx`, `.xlsx` 같은 파일은 born-digital editable text를 담고 있을 수 있습니다.
- PDF parser가 추출한 텍스트는 source object에서 파생된 기록입니다.
- 스크린샷이나 스캔 PDF의 OCR은 model-dependent derived text입니다.
- 음성 녹음의 speech-to-text도 derived text입니다.
- 사람이 검토하고 수정한 OCR은 raw OCR보다 강하지만 여전히 source object에서 파생된 기록입니다.
- minted `zet`는 raw evidence가 아닙니다. evidence를 참조하는 승인된 archive memory입니다.

이 구분은 AI 도구가 발전할수록 더 중요해집니다.

나중에 OCR 성능이 좋아졌다면 OCR layer를 다시 생성할 수 있어야 합니다. 이때 원본 object를 덮어쓰거나 derived text를 original text와 혼동해서는 안 됩니다.

## 6. Zet란 무엇인가

`zet`는 항상 텍스트입니다.

더 정확히 말하면 `zet`는 다음으로 구성됩니다.

```text
Markdown-like document body
+ metadata envelope
+ source references
+ relationships
+ provenance
+ lifecycle state
+ authority record
+ integrity information
```

body는 사람이 읽을 수 있어야 합니다.

envelope는 소프트웨어가 검사할 수 있어야 합니다.

`zet`는 다음을 할 수 있습니다.

- source를 요약하기,
- 아이디어를 설명하기,
- 문서를 해석하기,
- 여러 source를 연결하기,
- AI와 함께 만든 결론을 보존하기,
- 결정을 기록하기,
- 로컬 파일을 참조하기,
- object store item을 참조하기,
- Notion page를 참조하기,
- Google Drive 문서를 참조하기,
- 외부 URL을 참조하기,
- 공유 가능한 텍스트 객체가 되기.

`zet`는 다음이 아닙니다.

- 임의의 파일 첨부,
- raw screenshot,
- 기계만 읽는 database row,
- 기본값으로 social media post,
- 기본값으로 central server object.

`zet`는 해석된 archive memory의 가장 작은 durable unit입니다.

## 7. 민팅

민팅은 private archive issuance입니다.

민팅은 공개 게시가 아닙니다.

민팅은 블록체인 공개 발행이 아닙니다.

민팅은 공유가 아닙니다.

민팅은 draft `zet`를 canonical private archive record로 바꾸는 행위입니다.

기본 흐름:

```text
source material
-> AI/user conversation
-> draft zet
-> review gate
-> minted private zet
-> receipt
-> optional later share action
```

민팅 전 draft는 자유롭게 수정될 수 있습니다.

민팅 후 `zet`는 durable memory가 됩니다. 수정이나 대체는 가능하지만 이력이 남아야 합니다.

이 구조는 archive에 중요한 성질을 줍니다.

```text
thinking can stay fluid before minting
memory becomes accountable after minting
```

## 8. HITL과 AI-Agent Harness

기본 모드는 HITL, 즉 human-in-the-loop입니다.

기본 모델은 다음과 같습니다.

```text
AI may inspect allowed context.
AI may draft.
AI may propose links, tags, source refs, and summaries.
Human reviews.
Human mints.
Human approves sharing.
```

하지만 같은 architecture는 더 강한 위임도 지원할 수 있습니다.

핵심 추상화는 authority slot입니다.

이 authority slot에는 다음이 들어갈 수 있습니다.

- 인간 사용자,
- 조직 내 역할,
- supervised AI agent,
- policy-bound autonomous AI agent,
- scoped permission profile 아래에서 움직이는 agent chain.

그래서 실질적인 authority mode는 세 가지가 됩니다.

```text
basic
  AI는 draft만 만든다. 인간이 mint와 share를 결정한다.

auto_review
  AI가 candidate를 만들고 check를 실행할 수 있다.
  그래도 canonical minting과 external sharing은 인간 review gate를 지난다.

full_authority
  AI가 명시적으로 제한된 scope 안에서 mint, revise, route, share를 수행할 수 있다.
  모든 action은 receipt를 만들고 audit/revoke 가능해야 한다.
```

이 때문에 `zettel-kasten`은 동시에 다음이 될 수 있습니다.

```text
human-centered AI archive
AI-agent operating harness
```

인간 사용자의 기억을 보호하는 receipt system은 autonomous agent behavior를 감사 가능하게 만드는 장치이기도 합니다.

인간이 개입하면 이 시스템은 숙고를 지원합니다.

인간이 권한을 위임하면 이 시스템은 agent를 위한 operating substrate가 됩니다.

둘은 서로 다른 제품이 아닙니다.

같은 archive와 zet lifecycle에 붙은 authority mode가 다를 뿐입니다.

## 9. Local AI Conversation Provenance

AI conversation provenance는 사용자의 `zettel-kasten` runtime environment 안에서 발생한 AI 대화를 의미해야 합니다.

이것이 중요한 이유는 local 혹은 controlled runtime이 archive, local folder, provider export, object manifest, source map에 접근 권한을 가질 수 있기 때문입니다.

외부 AI chat URL은 같은 수준의 provenance가 아닙니다.

외부 chat URL은 외부 reference, imported snapshot, source object가 될 수는 있습니다. 하지만 controlled local archive session과 같은 권한과 맥락을 가진 creation provenance인 척해서는 안 됩니다.

권장 규칙:

```text
local archive AI session
  -> creation provenance

external AI chat link
  -> external reference unless imported, snapshotted, reviewed, and bound
```

## 10. 저장 모델

객체 스토리지는 미디어만 넣는 곳이 아닙니다.

원본 source 파일은 evidence로 사용될 때 source/object layer에 속합니다.

여기에는 다음이 포함됩니다.

- `.hwp`,
- `.hwpx`,
- `.docx`,
- `.xlsx`,
- `.pdf`,
- `.txt`,
- `.md`,
- `.csv`,
- 스크린샷,
- 오디오,
- 비디오,
- Notion export,
- Google Drive export,
- provider snapshot,
- 다른 original 또는 captured files.

권장 분리:

```text
Git repository
  zets
  metadata
  schemas
  receipts
  manifests
  public-safe specs

Object store / local object store
  source files
  media
  binary documents
  large exports
  immutable snapshots

Search/index layer
  extracted text
  OCR text
  embeddings if used
  graph index

Provider bindings
  Notion
  Google Drive
  GitHub
  object storage
  local filesystem
```

`.md` 파일은 역할에 따라 source object일 수도 있고 minted `zet`일 수도 있습니다.

확장자보다 역할이 중요합니다.

## 11. Provider-Aware Archive

사용자는 자연스럽게 말할 수 있어야 합니다.

```text
이 로컬 폴더를 내 zettel-kasten에 적재해줘.
이 문서로 zet를 만들어줘.
이 Google Drive 파일을 source material로 써줘.
이 Notion page를 내 archive에 매핑해줘.
방금 만든 요약을 mint해줘.
이 zet를 이 사람에게 공유해줘.
```

시스템은 이런 요청을 명시적 operation으로 바꿔야 합니다.

```text
scan source
bind provider
copy or snapshot source
extract derived text
draft zet
show review
mint zet
write receipt
update index
offer optional share
```

provider integration은 provenance를 보존해야 합니다.

예를 들어 Google Drive나 Notion item은 다음 중 하나가 될 수 있습니다.

- URL reference,
- export import,
- object storage snapshot,
- source map entry,
- minted `zet`의 citation.

이 선택들은 서로 다르며 반드시 기록되어야 합니다.

## 12. Private Archive First

기본 시스템은 외부 `zet` 공유 서비스가 없다고 가정합니다.

이것은 의도된 설계입니다.

첫 제품은 SNS가 아닙니다.

첫 제품은 trustworthy private archive입니다.

기본값:

```text
minted zet = private
```

외부 공유는 반드시 별도 action이어야 합니다.

```text
mint != share
mint != publish
mint != post
```

이것은 생각이 곧바로 performance가 되는 것을 막습니다.

archive가 먼저 memory가 되고, 그 다음에 communication이 되도록 합니다.

## 13. Zet 공유

미래의 `zet` 서비스는 archive model 위에 올라가는 sharing and communication layer입니다.

같은 `zet` abstraction은 관계 topology에 따라 다른 social form을 만듭니다.

```text
1:1 zet sharing
  -> messenger

1:many zet sharing
  -> SNS feed, channel, newsletter-like stream

many:many zet sharing
  -> collaboration workspace
```

핵심은 이것들이 data model 수준에서는 완전히 다른 제품군이 아니라는 것입니다.

같은 unit 위에 다른 relationship graph가 얹히는 것입니다.

```text
text zet
+ metadata envelope
+ source access policy
+ share envelope
+ recipient scope
+ receipts
```

공유에는 다음이 붙을 수 있습니다.

- text only,
- copied source artifacts,
- access links,
- scoped capabilities,
- redacted derivatives,
- expiration policy,
- recipient permissions,
- workspace rules.

private archive의 original이 가볍게 새어나가서는 안 됩니다.

공유는 대개 private canonical `zet`와 구분되는 share envelope 또는 workpack을 만들어야 합니다.

## 14. Token Hype 없는 Web3-like 구조

이 프로젝트는 인프라 의미에서 Web3-like합니다.

중요한 아이디어를 표현하기 위해 coin이나 public blockchain이 먼저 필요하지는 않습니다.

중요한 원칙은 다음입니다.

- subject-owned identity,
- user-owned data,
- portable records,
- verifiable actions,
- relationship-scoped sharing,
- local-first operation,
- optional peer-to-peer transport,
- optional relays,
- 중앙 플랫폼을 유일한 source of truth로 만들지 않기.

relationship-scoped sharing은 `delegate`가 기본적으로 public link가 아니라는 뜻이기도 합니다. 미래의 delegate capability는 counterparty-bound 또는 one-time claimable이어야 하고, attestation을 통해 recipient에게 귀속되어야 합니다. issuer는 자신이 누구와 접촉했는지 기억하기 위해 중앙 서버에 의존하지 않아야 하고, recipient는 foreign `zet`의 출처를 증명하기 위해 중앙 서버에 의존하지 않아야 합니다.

이 모델은 나중에 optional settlement, licensing, token-gated access, smart contract와 연결될 수 있습니다. 다만 그런 layer는 선택 사항이어야 합니다. payment는 access 또는 license right를 부여할 수 있지만, authorship, provenance, archive ownership을 조용히 바꾸어서는 안 됩니다.

공개 repository는 protocol/reference chain입니다.

```text
source code
+ specs
+ schemas
+ release tags
+ upgrade notes
```

사용자는 최신 chain을 따라갈 수도 있고, 오래된 release에 남을 수도 있습니다.

같은 major version은 expected compatibility를 의미해야 합니다.

다른 major version은 migration이나 bridge가 필요할 수 있습니다.

이것이 버전이 맞는 `zet` 시스템끼리 같은 주파수를 맞춘다는 말의 실질적 의미입니다.

## 15. 조합 가능한 Archives

zettel-kasten은 zets를 만들 수 있습니다.

선택된 zets는 공유될 수 있습니다.

공유된 zets는 새로운 archive로 조합될 수 있습니다.

그 새 archive는 다음이 될 수 있습니다.

- 공동 소유,
- 위임,
- spin-out,
- 상속,
- transfer,
- fork,
- merge.

예시:

- 개인 archive가 가족 archive를 위한 selected zets를 만든다.
- 두 사람이 shared archive를 만든다.
- 팀이 project archive를 만든다.
- 회사가 business unit archive를 spin out한다.
- 조직이 workpack을 다른 subject에게 transfer한다.
- agent가 full authority 범위 안에서 task archive를 만들고 receipts를 돌려준다.

이것은 시스템의 가장 강한 아이디어 중 하나입니다.

```text
archives create zets
zets can create archives
archives can be composed, shared, transferred, and governed
```

## 16. AX에서 왜 중요한가

여기서 AX는 AI Transformation입니다.

많은 AI 도입은 기존 workflow에 chatbot을 붙이는 방식으로 진행됩니다.

이 프로젝트는 더 낮은 layer에서 시작합니다.

질문은 다음입니다.

```text
AI가 책임 있게 일하려면 어떤 memory substrate가 필요한가?
```

답은 vector search만이 아닙니다.

AI에게 필요한 것은 다음입니다.

- original sources,
- derived text,
- provenance,
- human 또는 delegated authority,
- receipts,
- versioning,
- revision history,
- local permissions,
- share boundaries,
- durable zets.

이것이 없으면 AI output은 신뢰하기 어렵습니다.

이것이 있으면 AI는 archive operator, research assistant, memory curator, collaboration agent, workflow executor가 될 수 있습니다.

## 17. 사용자 경험 원칙

시스템은 강력해야 하지만 사용자가 infrastructure engineer처럼 생각해야 해서는 안 됩니다.

목표 경험:

```text
install with one command
connect providers step by step
talk to an AI that can access allowed local context
ask naturally
review what matters
mint durable zets
share deliberately
delegate carefully
audit later
```

제품은 다음처럼 느껴져야 합니다.

```text
my device
my archive
my AI operator
my zets
my rules
```

다음처럼 느껴지면 안 됩니다.

```text
another central app owns my memory
```

## 18. 오픈소스 철학

blueprint, schemas, reference implementation, research notes, implementation plans, public-safe work logs는 공개되어야 합니다.

실제 사용자 archive는 private이어야 합니다.

공개:

- product philosophy,
- protocol design,
- schemas,
- fake examples,
- reference implementation,
- research references,
- implementation plans,
- public-safe release notes.

비공개:

- real zets,
- real source maps,
- real files,
- provider tokens,
- private AI conversations,
- personal paths,
- sensitive receipts.

이 구분 덕분에 프로젝트는 공개적이고 협력적일 수 있으면서도 개인 기억을 public data로 만들지 않을 수 있습니다.

## 19. Non-Goals

이 프로젝트가 당장 되려는 것은 다음이 아닙니다.

- generic note app,
- cloud drive clone,
- chatbot wrapper,
- token project,
- public SNS clone,
- 모든 collaboration tool을 즉시 대체하는 제품,
- `zet`를 쓰기 위해 모두에게 zettel-kasten 사용을 강제하는 시스템.

`zet`는 나중에 full archive system을 원하지 않는 사람도 쓸 수 있는 standalone messenger/collaboration/SNS layer가 되어야 합니다.

하지만 그 깊은 architecture는 zettel-kasten에서 옵니다.

## 20. 구현 순서

구현은 다음 순서로 진행하는 것이 좋습니다.

```text
1. local archive structure
2. source/object model
3. provider bindings
4. draft zet format
5. mint transaction
6. mint receipt
7. text provenance hierarchy
8. search and graph index
9. authority modes
10. share envelope / workpack
11. capability-based sharing
12. local-first collaboration
13. optional P2P or relay transport
14. standalone zet client
15. agent harness mode
```

social layer가 먼저 오면 안 됩니다.

trustworthy private memory가 먼저 와야 합니다.

## 21. 성공 기준

이 프로젝트가 제대로 작동한다는 것은 사용자가 다음을 할 수 있다는 뜻입니다.

- 최소한의 setup friction으로 설치하기,
- local folders와 selected providers 연결하기,
- AI에게 허용된 source를 inspect하게 하기,
- 대화를 통해 `zet` draft 만들기,
- source references와 provenance 확인하기,
- `zet`를 private archive에 mint하기,
- 이력을 남기며 revision하기,
- 나중에 search하기,
- 의도적으로 share하기,
- agent에게 bounded authority 위임하기,
- 나중에 audit하기.

장기 목표는 단순합니다.

```text
important context should not evaporate
private memory should become durable
AI should operate over accountable memory
sharing should be chosen, scoped, and verifiable
```
