# 공유 업데이트 경로 미리보기 - 사용 예제

날짜: 2026-06-04
상태: 사용/스모크 예제 (읽기 전용, dry-run)

v0.3.1에서 추가된 `shared-update-route-preview` 명령어의 사용 예제입니다. 읽기
전용 미리보기를 어떻게 실행하고 출력을 어떻게 읽는지 보여줍니다. 새로운 동작은
추가하지 않습니다.

레퍼런스 문서: [shared-update-route-preview.ko.md](shared-update-route-preview.ko.md).

## 이 명령이 하는 일

`shared-update-route-preview`는 이미 검토된 공유 업데이트 기록 하나를 보고,
수신자 쪽에서 다음에 고려할 수 있는 후보 경로 — `delegate`, `attest`, `anchor`,
`none` — 와 그 경로를 실제로 처리하는 기존 명령을 알려줍니다. 아무것도 실행하지
않고, 아무것도 쓰지 않습니다.

## 1. 준비: 작은 공개 안전 기록

아카이브에 이미 검토된 공유 업데이트 기록이 archive-relative 경로에 있다고
가정합니다 (비공개 본문 없음, 절대 경로 없음, 비밀값 없음):

```text
shared-updates/incoming/example-update.json
```

## 2. dry-run 미리보기 실행

```powershell
python wom-kit\cli\archive.py shared-update-route-preview <archive-root> --record shared-updates/incoming/example-update.json --dry-run --format json
```

## 3. 대표 출력 예시

```json
{
  "lifecycle_action": "zet_shared_update_route_preview",
  "route_status": "route_preview_not_recorded",
  "candidate_route": "attest",
  "source_shared_update_record": {
    "record_path": "shared-updates/incoming/example-update.json",
    "sha256": "<hash>"
  },
  "trust_state": "untrusted_foreign",
  "attestation_status": "not_created",
  "anchor_status": "not_created",
  "renewal_status": "not_performed",
  "would_change": [],
  "route_eligibility": {
    "attest": {
      "applies": true,
      "defer_to": "attest-zet",
      "related_shared_update_review_command": "shared-update-attestation-review",
      "related_shared_update_review_required_flags": ["--approve", "--reviewed-by"]
    }
  }
}
```

## 4. 읽는 법

- `candidate_route` — 사람이 다음에 고려할 수 있는 경로 (여기서는 `attest`).
- `route_eligibility.<route>.defer_to` — 그 경로를 실제로 처리하는 기존 명령.
  이 미리보기는 그 명령을 가리키기만 합니다.
- `related_shared_update_review_required_flags` — 다음 표면 자체가 사람 승인
  게이트라는 표시 (`--approve`와 `--reviewed-by`가 필요함).
- `would_change: []` — 바뀐 것이 없습니다. 미리보기는 읽기 전용입니다.

## 5. 네 가지 결과

- `delegate` — 나중에 delegate 경로를 고려할 수 있음 (`delegate-zet`).
- `attest` — 나중에 attestation/검토 경로를 고려할 수 있음 (`attest-zet`;
  검토 쓰기는 `shared-update-attestation-review`).
- `anchor` — 나중에 anchor 경로를 고려할 수 있음 (`anchor-zet`).
- `none` — 기록이 막혔거나 알려진 경로로 매핑되지 않음. 이것은 중립적 사실이며,
  거절이나 승인이 아닙니다.

## 하지 않는 일

쉬운 말로:

- 경로를 **승인하지 않습니다.**
- 어떤 파일도 **쓰지 않습니다.**
- 아무것도 가져오기/수락/위임/attest/anchor **하지 않습니다.**
- 신뢰 생성, 전송, provider sync, 공개 증명을 **하지 않습니다.**

나중에 있을 수 있는, 사람 승인을 거치는 경로가 무엇인지 설명만 합니다. 경로
명령을 이름으로 보여주는 것은 실행 권한이 아닙니다.
