# 공유 업데이트 경로 미리보기

날짜: 2026-06-04
상태: 읽기 전용 dry-run 미리보기

## 요약

`shared-update-route-preview`는 로컬 공유 업데이트 기록 하나를 보고,
수신자 쪽에서 다음에 어떤 경로를 검토할 수 있는지 설명하는 얇은
읽기 전용 라우터입니다.

이 명령이 답하는 질문은 하나입니다.

```text
기존 공유 업데이트 기록 검토 게이트를 통과한 뒤,
수신자 쪽에서 다음에 검토할 수 있는 후보 경로는
delegate, attest, anchor, none 중 무엇인가?
```

이 명령은 그 경로를 실행하지 않습니다. 기존 명령을 가리킬 뿐이고,
파일을 만들거나 바꾸지 않습니다.

## CLI

```powershell
python wom-kit\cli\archive.py shared-update-route-preview <archive-root> --record <archive-relative-json> --dry-run --format json
```

`--record` 경로는 archive root 안에 있는 archive-relative 경로여야
합니다. 절대 경로, URL처럼 보이는 경로, 상위 폴더로 벗어나는 경로,
UNC 경로, NUL byte는 기존 공유 업데이트 기록 검토 정책에서 거부됩니다.

## 경로 적격성 포인터

출력에는 포인터만 들어갑니다.

- `route_eligibility.delegate` / `delegate_route_preview`는 `delegate-zet`을 가리킵니다.
- `route_eligibility.attest` / `attest_route_preview`는 `attest-zet`을 가리킵니다.
  관련 공유 업데이트 검토 명령으로 `shared-update-attestation-review`도
  따로 표시하고, 필수 플래그 `--approve`와 `--reviewed-by`도 함께
  반환합니다.
- `route_eligibility.anchor` / `anchor_route_preview`는 `anchor-zet`을 가리킵니다.
- `route_eligibility.none` / `none_route_preview`는 기록이 막혔거나 알려진
  경로로 매핑되지 않을 때 적용됩니다.

이 필드들은 경로 적격성 포인터입니다. `delegate-zet`, `attest-zet`,
`anchor-zet`의 전체 미리보기 로직을 다시 구현하지 않습니다.

경로 명령을 이름으로 보여준다고 해서 실행 권한을 준다는 뜻은
아닙니다. 쓰기 가능한 표면은 여전히 별도의 사람 승인 게이트를
통과해야 합니다. 예를 들어 `shared-update-attestation-review`는 여전히
`--approve`와 `--reviewed-by`가 필요합니다.

## 출력 경계

경로 미리보기는 다음을 반환합니다.

- `lifecycle_action: zet_shared_update_route_preview`
- `route_status: route_preview_not_recorded`
- `candidate_route: delegate | attest | anchor | none`
- `source_shared_update_record.record_path`
- `source_shared_update_record.sha256`
- attestation/review 경로 포인터의
  `related_shared_update_review_required_flags: ["--approve", "--reviewed-by"]`
- `trust_state: untrusted_foreign`
- `attestation_status: not_created`
- `signature_status: not_created`
- `anchor_status: not_created`
- `renewal_status: not_performed`
- `would_change: []`
- 쓰기, 전송, 신뢰, 가져오기, 수락, attest, 서명, anchor, apply,
  provider, projection, queue, worker, blockchain, token, model-training,
  backpropagation, full-auto 동작이 모두 닫혀 있다는 명시적 플래그

이 미리보기는 본문 원문, 로컬 절대 경로, provider URL, token, secret,
비공개 source 위치를 출력하지 않습니다.

## 경로 선택

라우터는 `shared-update-record-review`가 노출한 안전한
`receiver_review_preview.proposed_action` 메타데이터만 사용합니다.

보수적인 매핑은 다음과 같습니다.

- delegate 경로를 말하는 메타데이터는 `delegate`로 매핑됩니다.
- anchor 경로를 말하는 메타데이터는 `anchor`로 매핑됩니다.
- `review_before_renewal` 또는 attest/review 메타데이터는 `attest`로 매핑됩니다.
- 알 수 없거나 막힌 메타데이터는 `none`으로 매핑됩니다.

`anchor`는 나중에 anchor 경로를 검토할 수 있다는 뜻일 뿐입니다. 이
명령은 공유 업데이트를 anchor하지 않고, apply하지 않고, 신뢰하지
않고, 가져오지 않고, 수락하지 않습니다.

## MCP

v0.3.1 후보 작업은 이 경로 미리보기에 대한 MCP write/apply 도구를
추가하지 않습니다. 공유 업데이트 write/apply/import/trust/anchor 동작은
MCP에서 계속 닫혀 있습니다.

## 하지 않는 일

이 미리보기는 real ZET transport, key creation, key-sharing registry,
radio-frequency access, mirroring delivery, neighbor feed update, automatic
renewal, trust graph mutation, import, acceptance, real attestation, signature,
anchor, apply, public proof, provider sync, WordPress publishing, projection
write, receipt write, queues, workers, DID/wallet/key custody, payments,
staking, consensus, blockchain, token, system token, governance, model
training, backpropagation, full-auto behavior를 구현하지 않습니다.
## Route Token Note

Free-form action text is not echoed; only recognized route tokens are carried
into this preview.
