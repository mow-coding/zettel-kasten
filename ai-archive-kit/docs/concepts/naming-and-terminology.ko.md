# WOM 명칭과 용어 기준

상태: 공개 naming baseline
날짜: 2026-05-23

이 문서는 WOM의 현재 제품 언어 방향을 정의합니다.

이 문서는 public-facing language를 위한 naming freeze입니다. 모든 내부 file path, schema field, compatibility command가 이미 rename되었다는 뜻은 아닙니다.

## 전체 이름

```text
WOM
Widesider of Modernity
```

WOM이 전체 umbrella name입니다.

이 이름은 modernity가 하나의 spectrum이라면, 그 최전선에서 인간이 인식할 수 있는 지평을 넓히겠다는 뜻을 담습니다.

WOM은 단순 note app, SaaS archive, blockchain token project가 아닙니다. local-first, AI-native, Web3 지향 archive/communication system을 둘러싼 worldview입니다.

## 뿌리, 기본 단위, 노드

공식 public language:

```text
WOM              -> 전체 umbrella / worldview
zettel-kasten    -> 역사적 뿌리와 local archive method
zet              -> active text primitive
node             -> subject/archive participant
tie              -> node 사이의 relationship/capability 후보 용어
```

`zettel-kasten`은 중요합니다. 이 프로젝트가 Niklas Luhmann의 note-box 전통에서 출발했기 때문입니다.

하지만 active product unit은 `zettel`이 아니라 `zet`입니다.

사용:

```text
zet
minted zet
draft zet
foreign zet
```

현재 제품 언어로 피할 것:

```text
active unit으로서의 zettel
public copy에서 canonical zettel
선호 command name으로서의 mint-zettel
```

구현 호환성 note: 현재 v0.2 file path와 code에는 아직 `zettel`, `zettels/`, `mint-zettel`, 관련 schema name이 남아 있습니다. `v0.2.13`부터 `mint-zet`이 선호 CLI alias로 존재하지만, 옛 이름은 compatibility surface로 유지합니다.

## Lifecycle

WOM의 공식 lifecycle:

```text
mint -> delegate -> attest -> anchor
```

의미:

- `mint`: `zet`를 node의 private archive memory로 발행한다.
- `delegate`: minted `zet`에 대한 scoped capability를 위임한다.
- `attest`: foreign `zet`의 issuer, integrity, delegated condition을 검증/입증한다.
- `anchor`: attested foreign `zet`를 node의 local meaning network 안에 정박시킨다.

Legacy 또는 compatibility language:

- `promote` -> 예전 minting behavior를 위한 legacy compatibility.
- `share` -> legacy/general explanation. 제품 언어는 `delegate`.
- `download` / `receive` -> core language로 피함. 제품 언어는 `attest`.
- `save` -> core language로 피함. local meaning placement를 말할 때는 `anchor`.

## Parcel And Admit

현재 구현 언어:

```text
pack
workpack
import
```

선호 product direction:

```text
workpack -> parcel
pack     -> parcel / create parcel
import   -> admit, parcel 또는 foreign zet를 검증 후 node 안으로 들일 때
```

raw source/provider material에는 다음을 씁니다:

```text
ingest source
register source
scan source
```

이 구분이 중요합니다:

- `admit`은 boundary를 넘는 governed material에 속합니다.
- `ingest/register/scan`은 local source onboarding과 metadata mapping에 속합니다.
- `parcel`은 generic file bundle보다, 범위가 정해진 portable unit에 가깝습니다.

## Proof, Credential, Attestation

현재 구현 언어는 `receipt`입니다.

`receipt`는 v0.2 implementation term으로는 허용할 수 있습니다. blockchain에도 transaction receipt라는 말이 있고, 현재 code가 이미 schema-backed receipt file을 갖고 있기 때문입니다.

하지만 product language는 더 강한 distributed-trust 단어로 이동해야 합니다.

```text
mint receipt          -> mint proof
delegate receipt      -> delegation credential 또는 delegation proof
attestation receipt   -> attestation
anchor metadata       -> anchor proof / anchor mark
```

근시일 원칙:

- v0.2 compatibility를 위해 file path와 schema에서는 `receipt`를 유지합니다.
- public docs에는 `proof`와 `credential`을 도입합니다.
- field/path migration은 alias가 생긴 뒤 결정합니다.

## Credit

`credit`은 core evidence object의 대체어로는 추천하지 않습니다.

좋은 연상:

- attribution,
- recognition,
- trust,
- accounting,
- future settlement,
- value or contribution.

하지만 위험한 연상도 있습니다:

- money,
- score,
- debt,
- platform reputation.

추천:

```text
credit -> 미래 attribution / contribution / settlement layer
proof or credential -> core evidence layer
```

## 현재 호환성 상태

`v0.2.13` 기준:

- `delegate-zet`은 이미 제품 언어와 맞습니다.
- `attest-zet`, `anchor-zet`도 제품 언어와 맞습니다.
- `mint-zet`은 민팅의 선호 CLI surface입니다. `mint-zettel`은 compatibility alias로 남습니다.
- `promote`, `share`는 legacy compatibility command로만 남겨야 합니다.
- `parcel`은 범위가 정해진 portable unit을 만드는 선호 CLI surface입니다. `pack`은 compatibility alias로 남습니다.
- `admit --dry-run`은 parcel/workpack을 검증 후 들여오는 과정을 preview하는 선호 CLI surface입니다. `import --dry-run`은 compatibility alias로 남습니다.
- `workpack`은 안전한 migration이 생기기 전까지 v0.2 storage path/folder compatibility term으로 남습니다.
- `receipt`는 implementation compatibility를 유지하되, product copy에서는 `proof`, `credential`을 도입합니다.

짧게 쓰면:

```text
WOM
node
zet
mint -> delegate -> attest -> anchor
parcel -> admit
proof / credential / attestation
```
