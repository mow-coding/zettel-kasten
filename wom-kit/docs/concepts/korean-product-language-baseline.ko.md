# 한국어 제품 언어 기준선

상태: v0.2.50 공개 제품 언어 기준
날짜: 2026-05-27

이 문서는 WOM을 한국어로 설명할 때 쓰는 핵심 제품 언어를 정리합니다.

목표는 모든 코드 이름을 한국어로 바꾸는 것이 아닙니다. CLI 명령, JSON field, schema field, 파일명, Python identifier, 구현 내부 이름은 영어를 유지합니다. 한국어 용어는 README, concept 문서, 사용자 설명, 미래 UI 문구처럼 사람이 제품을 이해하는 표면에서 씁니다.

## 이름 기본값

| 원어 | 한국어 설명 | 기준 |
| --- | --- | --- |
| `WOM` | 옴 | 고유명사입니다. `웜`이라고 읽지 않습니다. |
| `zettel-kasten` | 기록 계층 | repository root와 archive-system 뿌리입니다. |
| `zet` | 쪽글 / 토막글 | 제품 term은 계속 `zet`입니다. |
| `ZET` | 공유 계층 | 제품 term은 계속 `ZET`입니다. |
| `objet` | 오브제 | source/original file을 가리키는 WOM 제품 언어입니다. |
| `object` | object | provider API나 manifest id 같은 기술 용어에만 씁니다. |

`zet`는 문서 자체입니다. 사람이 쓰거나 AI가 초안을 만들고 사람이 감독한 최소 텍스트 단위입니다.

`ZET`는 그 `zet`를 다른 사람이나 팀과 나누는 미래 공유 계층입니다. `ZET`는 block 자체가 아닙니다.

## 발행에서 갱신까지

| 원어 | 한국어 제품어 | 의미 |
| --- | --- | --- |
| `mint` | 발행 | 한 세계 안에서 기존 것을 정리하며 새 생각을 만드는 행위입니다. 창조이면서 동시에 파괴적인 속성을 지닙니다. |
| `delegate` | 공유 | 발신자가 자기 세계의 `zet`를 외부에게 여는 행위입니다. 이미 고정된 상대에게만 보내는 느낌보다, 바깥을 향해 열리는 느낌을 포함합니다. |
| `attest` | 수용 | 수신자가 상대의 것을 받아들이기 전에 확인하고 받는 행위입니다. 비폭력 대화의 수용 감각에서 출발합니다. |
| `anchor` | 반영 | 상대의 것을 내 세계 안에 비추어 넣는 행위입니다. |
| `attest + anchor` | 갱신 | 수신자 쪽에서 수용하고 반영하여 자기 세계를 새롭게 조정하는 행위입니다. |

`mint -> delegate`는 발신자 쪽의 발행과 공유입니다.

`attest -> anchor`는 수신자 쪽의 수용과 반영입니다.

ZET가 진짜 공유 계층으로 작동하려면 단지 발신자가 발행하고 공유하는 것만으로는 부족합니다. 수신자가 `갱신`을 수행할 때, 즉 수용과 반영을 통해 자신의 세계 안에서 의미가 움직일 때 ZET의 관계적 실체가 생깁니다.

## 소포와 검문소

| 원어 | 한국어 제품어 | 의미 |
| --- | --- | --- |
| `foreign block` | 소포 | 다른 사람의 세계에서 온 block입니다. |
| `quarantine` | 검문소 | 소포를 곧바로 내 세계에 들이지 않고 안전하게 검토하는 곳입니다. |
| `trust` | 인증 | 신뢰 가능하다고 표시하거나 확인하는 상태입니다. |
| `import` | 반입 | 외부 자료를 내 작업 공간 안으로 들이는 행위입니다. |
| `acceptance` | 채택 | 그것이 내 세계에 들어와도 된다고 결정하는 더 강한 행위입니다. |

v0.2.x의 foreign block 흐름은 검문소와 영수증 같은 일부 안전 단계를 preview하거나 기록할 수 있습니다. 그러나 real trust, real import, acceptance, real anchor, real ZET transport는 아직 열지 않습니다.

즉, v0.2.x의 검문소 기록은 "이 소포를 안전하게 받아들였다"가 아닙니다. "이 소포를 아직 믿지 않는 상태로 검토 기록에 올렸다"에 가깝습니다.

## 상자, 초록, 본문

| 원어 | 한국어 제품어 | 의미 |
| --- | --- | --- |
| `block` | 상자 | `zet + header`입니다. |
| `header` | 초록 | refs, hashes, provenance, policy, receipts, source refs, objet refs 같은 주변 정보를 담습니다. |
| `body` | 본문 | block 안에서 읽히는 `zet`의 main text 역할입니다. |

짧게 쓰면:

```text
block = zet + header
상자 = zet + 초록
```

`zet`는 문서 자체이고, `body`는 그 `zet`가 상자 안에서 readable main text로 놓일 때의 역할 이름입니다.

`header`/초록에는 다음 같은 정보가 들어갈 수 있습니다.

- 참조된 `zet`,
- 참조된 `objet`,
- 가리키기/참조 정보,
- 필요할 때 참조된 오브제의 공유 접근권한 metadata,
- 요약,
- provenance/족보,
- receipt/영수증,
- policy와 visibility.

내 세계에서 만들어진 상자가 다른 사람의 세계로 들어가면 `foreign block`, 즉 소포가 됩니다.

## ZET 공유 형식과 방식

ZET의 네트워크 형식은 관계 수에 따라 나눕니다.

| 관계 | 한국어 제품어 |
| --- | --- |
| 1:1 | 메신저형 ZET |
| 1:다수 | SNS형 ZET |
| 다수:다수 | 워크스페이스형 ZET |

기술적인 공유 방식은 따로 나눕니다.

| 원어 | 한국어 제품어 |
| --- | --- |
| `radio-frequency` | 라디오 주파수 방식 |
| `key-sharing` | 키 방식 |
| `mirroring` | 미러링 방식 |

현재 개념상 사용 가능성은 다음처럼 잡습니다.

| ZET 형식 | 가능한 방식 |
| --- | --- |
| 메신저형 ZET | 키 방식 |
| SNS형 ZET | 키 방식 + 라디오 주파수 방식, 선택/혼용 가능 |
| 워크스페이스형 ZET | 키 방식 + 라디오 주파수 방식 + 미러링 방식, 선택/혼용 가능 |

이 표는 제품 언어와 미래 설계 기준선입니다. v0.2.50은 real RF access, key-sharing registry, mirroring delivery, real ZET transport, provider sync, 앱 구현을 추가하지 않습니다.

## 표면과 수제성

| 원어 | 한국어 제품어 | 의미 |
| --- | --- | --- |
| `projection` | 구현 | 내 archive의 가능성이 어떤 표면에서 나타나는 일입니다. |
| `surface` | 수제 앱 | 사용자가 고른 표현/게시/작업 표면입니다. |
| `prompt-as-algorithm` | 수제 알고리즘 | 중앙 플랫폼의 검은상자가 아니라, 사용자가 이해하고 조정할 수 있는 자기 알고리즘입니다. |
| `neighbor` | 이웃 | follow/relationship 계층의 사람 또는 node입니다. |
| `feed` | 담벼락 | 공유된 흐름이 보이는 표면입니다. |
| `broadcast` | 송출 | 더 넓은 대상에게 내보내는 행위입니다. |
| `receipt` | 영수증 | v0.2 구현에서 proof-like action record를 부르는 말입니다. |
| `provenance` | 족보 | 어디서 왔고 어떻게 만들어졌는지를 남기는 기록입니다. |
| `canonical` | 정본 | archive 안에서 공식으로 인정된 기록입니다. |
| `node` | 노드 | WOM 안의 주체 또는 참여자입니다. |

수제 앱은 새로 직접 만든 앱일 수도 있고, WordPress처럼 외부 앱을 표면 역할로 빌려오는 것일 수도 있습니다. WordPress는 빌려온 수제 앱 예시이지 WOM/ZET system 자체가 아니며, real ZET transport도 아닙니다.

## SNS형 ZET의 사용자 행동

SNS형 ZET에서 현재 제품 언어 후보로 잡는 핵심 행동은 두 가지입니다.

| 표현 | 의미 |
| --- | --- |
| 젯 갱신하기 | 이웃/팔로우 관계 쪽에서 새로 열린 내용을 내 세계에 맞게 갱신하는 행동입니다. |
| 쿠키 굽기 | 내 수제 알고리즘으로 추천 탐색을 새로 여는 행동입니다. |

`쿠키 굽기`는 Web2 cookie 수집의 반전입니다.

```text
Web2: 쿠키 수집 허용 -> platform collects my trace
Web3/ZET: 쿠키 굽기 -> I use my own cookie/trace for myself
```

즉, 플랫폼에게 내 흔적을 빼앗기는 것이 아니라, 내가 내 흔적과 취향을 써서 나를 위한 탐색 재료를 굽는다는 뜻입니다.

## 메신저형 ZET의 스레드

`스레드`는 메신저형 ZET에서 상자/block들이 답장 관계로 이어진 대화 사슬입니다.

예를 들면 한 노드가 상자를 보내고, 다른 노드가 그 상자에 답장 상자를 만들고, 다시 그 답장에 답장이 이어지면 그 연결이 스레드가 됩니다.

이 말은 blockchain 기술 구현을 뜻하지 않습니다. v0.2.50은 cryptocurrency, token, mining, staking, consensus network, public ledger, trustless public chain을 구현하지 않습니다.

## 현재 v0.2.50 경계

v0.2.50은 제품 언어 기준선입니다.

이번 배치는 다음을 하지 않습니다.

- CLI/MCP 명령 추가 또는 이름 변경,
- real ZET transport,
- real trust/import/acceptance/anchor,
- attestation/signature write,
- RF access,
- key-sharing registry,
- mirroring delivery,
- WordPress publishing,
- projection write/receipt,
- recommendation fetching/ranking/feed update,
- provider call/sync,
- payments/staking/consensus/blockchain,
- model training/backpropagation,
- full-auto behavior.

이 문서는 앞으로 한국어 README, concept 문서, 미래 UI 문구가 흔들리지 않게 만드는 얇은 기준선입니다.

관련 미래 공유/갱신 문서: [ZET Shared Update Record Baseline](../zet-shared-update-record-baseline.md).
