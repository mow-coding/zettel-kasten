# ZET 공유 Lifecycle 용어

상태: 공개 용어 후보
날짜: 2026-05-23

이 문서는 미래의 `ZET` 통신 계층에서 사용할 제품 언어 방향을 기록합니다.

이 문서에서 `zet`는 zettel-kasten 안에서 민팅되는 단위 문서이고, `ZET`는 그 zets를 바탕으로 만들어지는 통신 방식/서비스/프로토콜 계층입니다.

아직 공유 기능, P2P transport, SNS/feed, collaboration을 구현하는 문서가 아닙니다. 앞으로의 spec, schema, receipt, UI가 맞춰야 할 철학적 동사를 먼저 정의합니다.

`zet`, `node`, `parcel`, `admit`, `proof`, `credential`까지 포함한 더 넓은 WOM naming baseline은 [WOM 명칭과 용어 기준](naming-and-terminology.ko.md)을 보세요.

## 1. 왜 새로운 동사가 필요한가

이 프로젝트는 기존 SaaS 앱의 용어를 그대로 물려받지 않으려 합니다.

보통 SaaS 흐름은 다음처럼 말합니다.

```text
create -> share -> download -> save
```

이 언어는 데이터를 플랫폼 안에서 이동하는 파일처럼 봅니다.

하지만 `ZET` 모델은 각 주체를 자기 archive를 가진 행위자로 봅니다. 각 주체는 기록을 발행하고, 권한을 위임하고, 타인의 기록을 입증하고, 자기 의미망 안에 정박시킬 수 있습니다.

`ZET`의 선호 lifecycle 흐름은 다음입니다.

```text
mint -> delegate -> attest -> anchor
```

이것은 아직 완성된 protocol이 아니라 용어 후보입니다. 의도적으로 일반 앱 용어보다 블록체인, 분산 신뢰, 도시사회학적 감각에 더 가깝게 잡습니다.

## 2. Lifecycle 동사

### Mint

`mint`는 `zet`를 자기 private archive 안에 canonical memory로 발행하는 행위입니다.

현재 구현에서는 다음 흐름입니다.

```text
draft zet -> mint-zet -> canonical private zet -> mint proof/receipt -> draft snapshot
```

minting은 posting, sharing, broadcasting, publishing이 아닙니다.

minting은 private archive issuance입니다.

### Delegate

`delegate`는 mint된 `zet`를 특정 주체, 그룹, archive, agent, workspace에게 열어주는 행위의 후보 용어입니다.

delegate는 ownership transfer가 아닙니다.

delegate는 다른 행위자에게 제한된 capability를 위임하는 행위입니다. 예를 들면:

- `zet`를 inspect할 capability,
- receipt와 hash를 verify할 capability,
- 참조된 source material에 접근할 capability,
- copy를 받을 capability,
- attestation을 만들 capability.

미래 구현에서는 이것이 delegation credential, capability token, parcel, 또는 다른 portable proof로 표현될 수 있습니다. 현재 v0.2 구현은 schema-backed compatibility path에서 아직 `delegate receipt`를 사용합니다.

#### Delegate는 공개 링크가 아니다

기본 delegation 모델은 누구나 계속 쓸 수 있는 public link 또는 하나의 공유 키가 아니어야 합니다.

delegation은 attestation-bound capability로 표현되어야 합니다.

- `counterparty_bound`: 이미 알고 있는 archive, subject, agent, group member, workspace identity를 대상으로 발급합니다.
- `claimable_once`: 처음에는 수신자가 특정되지 않은 1회용 capability로 발급하되, 한 번 claim되면 claim한 identity에 귀속됩니다.
- `spent`: 1회용 capability가 claim되고 attest되면 다른 행위자가 다시 쓸 수 없는 상태가 됩니다.
- `public_link`: 의도적으로 공개하려는 자료에 한해서만 선택 가능한 비기본 미래 모드입니다.

이것이 중요한 이유는 탈중앙화 시스템에서는 중앙 플랫폼이 접촉 장부를 대신 관리해주지 않기 때문입니다. issuer는 어떤 counterparty가 접근 권한을 받았거나 claim했는지 알아야 하고, recipient는 어떤 issuer에게서 delegation을 받았는지 증명할 수 있어야 합니다.

실제 미래 delegation은 nonce, scope, target policy, expiry 또는 revocation rule, issuer identity, content/receipt hash를 포함해야 합니다. 이후 attestation은 그 delegation을 recipient archive identity 또는 public key fingerprint에 묶어야 합니다.

transport가 순수 P2P라면 issuer는 recipient가 attestation 또는 acknowledgement receipt를 돌려줄 때 capability가 사용되었음을 알 수 있습니다. shared ledger나 public blockchain은 나중에 그 관찰 가능성을 더 넓게 만들 수 있지만, core protocol에 필수는 아닙니다.

### Attest

`attest`는 위임받은 foreign `zet`를 검증하고, 그 `zet`가 특정 상태로 존재했음을 증거로 기록하는 행위입니다.

attestation은 다음이 아닙니다.

- 좋아요,
- 동의,
- endorsement,
- repost,
- 그 생각을 내 생각으로 채택하는 행위.

attest하는 archive는 사실상 이렇게 말합니다.

```text
나는 이 foreign zet가 존재했고,
이 identity 또는 archive에 의해 mint되었고,
이 schema/protocol profile에 맞았고,
이 content hash를 가졌고,
이 delegated condition 아래에서 내 archive 경계 안에 들어왔음을 검증했다.
```

그래서 `attest`는 미래의 Web3-like 모델에서 핵심입니다.

여러 독립 주체가 같은 minted `zet`를 attest하면, 원 발행자는 새 revision을 만들 수는 있어도 옛 상태가 없었다고 우기기 어려워집니다. 기록된 hash, receipt, attestation이 분산 증인이 되기 때문입니다.

attestation은 나중에 `attestation receipt` 또는 그에 준하는 log entry를 만들어야 합니다.

### Anchor

`anchor`는 attested foreign `zet`를 수신자의 zettel-kasten 의미망 안에 놓는 행위의 후보 용어입니다.

anchoring은 단순히 파일을 저장하는 것이 아닙니다.

anchoring은 foreign `zet`에 다음을 부여합니다.

- local context,
- local relationships,
- local retrieval paths,
- local interpretive position,
- recipient archive의 knowledge map 안의 자리.

foreign `zet`는 provenance상 여전히 foreign입니다. anchoring은 authorship, issuer identity, delegated scope, attestation evidence를 지우지 않습니다.

도시사회학적 직관으로 보면, 어떤 기록은 살아 있는 지도 안에서 위치, 관계, 맥락을 얻을 때 의미를 갖습니다.

## 3. Compatibility 언어

미래 공유 레이어는 두 사용자가 단순히 같은 앱 버전을 써야 한다고 설명하지 않는 편이 좋습니다.

더 나은 compatibility 모델은 다음입니다.

```text
protocol compatibility
schema compatibility
trust profile compatibility
capability compatibility
```

클라이언트가 더 최신 release에 있어도 오래된 sharing protocol을 이해할 수 있습니다. 반대로 기술적으로 읽을 수 있는 `zet`라도 trust profile이나 delegated capability가 충분하지 않으면 수락하지 않을 수 있습니다.

## 4. Future Proofs And Compatibility Receipts

이 용어는 앞으로 다음 evidence object를 설계하게 만듭니다.

```text
delegation credential / delegation proof
attestation
anchor proof / anchor mark
```

현재 v0.2 구현은 compatibility를 위해 file path와 schema에서 아직 `receipt`를 사용합니다.

`v0.2.14` 기준으로 lifecycle은 아직 초기 단계이지만, mint와 delegate에는 실제 local write path가 생겼고 `WOM`/`zet`/`ZET` naming boundary도 문서화되었습니다.

- `mint-zet --dry-run`은 private archive minting을 preview합니다. `mint-zettel`은 compatibility alias로 남습니다.
- `mint-zet --approve --reviewed-by <actor>`는 canonical private archive memory, mint receipt, draft snapshot을 기록합니다.
- `delegate-zet --dry-run`은 delegate receipt preview를 반환합니다.
- `delegate-zet --approve --reviewed-by <actor>`는 local delegate receipt를 기록합니다.
- `attest-zet --dry-run`은 attestation receipt preview를 반환합니다.
- `anchor-zet --dry-run`은 anchor metadata preview를 반환합니다.
- `ZET`는 미래 통신 계층이고, `zet`는 민팅된 단위 문서입니다.
- WOM Safe HTML Profile은 미래 `ZET` surface가 안전하게 렌더링할 수 있는 장기 canonical/interchange/rendering 방향입니다.

`delegate-zet --target-policy claimable_once --dry-run`은 아직 recipient archive를 정하지 않은 1회용 claimable capability를 preview할 수 있습니다. 이후 `attest-zet --dry-run` preview가 `claim_binding`을 통해 그 capability를 attesting archive에 묶습니다.

delegate receipt write는 실제 local evidence이지만 transport나 import는 아닙니다. attestation과 anchor는 아직 preview-only입니다.

나중에 설계할 때는 다음을 만족해야 합니다.

- delegation은 audit 가능해야 합니다.
- delegation capability는 counterparty-bound 또는 one-time claimable이어야 합니다.
- attestation은 독립적으로 verify 가능해야 합니다.
- anchoring은 foreign provenance를 보존해야 합니다.
- private archive minting은 social sharing과 분리되어야 합니다.

## 5. 선택적 정산 레이어

core `zet` sharing model은 non-financial하고 protocol-neutral해야 합니다.

하지만 capability model은 미래의 선택적 settlement를 위한 여지를 남깁니다.

- delegate capability는 아무 payment 없이 발급될 수 있습니다.
- delegate capability는 나중에 payment receipt, license term, token-gated condition, smart-contract settlement를 참조할 수 있습니다.
- payment는 명시된 조건 아래에서 access, capability, license를 부여해야 합니다.
- payment가 원본 `zet`의 authorship, provenance, ownership을 조용히 이전하는 것으로 해석되어서는 안 됩니다.

이렇게 하면 `zet`는 무료 personal communication으로도 쓸 수 있고, 나중에 blockchain, licensing, patronage, paid knowledge exchange, institutional access model로도 확장될 수 있습니다.

## 6. 현재 상태

현재 상태:

- `mint`는 private archive issuance의 선호 제품 언어입니다.
- `attest`는 foreign `zet` 검증의 선호 제품 언어입니다.
- `delegate`는 scoped sharing authority의 선호 후보입니다.
- `anchor`는 attested foreign `zet`를 local meaning에 놓는 선호 후보입니다.
- `v0.2.10`은 delegate, attest, anchor의 첫 dry-run CLI/MCP check를 제공합니다.
- `v0.2.11`은 `counterparty_bound`와 `claimable_once` delegate capability preview를 추가합니다.
- `v0.2.12`는 CLI-only real delegate receipt write를 추가합니다.
- `v0.2.13`은 WOM naming baseline과 compatibility-safe CLI alias인 `mint-zet`, `parcel`, `admit`을 추가합니다.
- `v0.2.14`는 `WOM`/`zet`/`ZET` 구분과 WOM Safe HTML Profile design baseline을 추가합니다.

짧게 쓰면:

```text
mint -> delegate -> attest -> anchor
```
