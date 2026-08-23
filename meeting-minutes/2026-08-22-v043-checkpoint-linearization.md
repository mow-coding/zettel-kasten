# v0.4.3 ExactOperation checkpoint 선형화 기록

날짜: 2026-08-22
범위: `FileExactOperationCheckpointStore.append` 성능·내구성 P1 수정

## 문제

기존 `append`는 checkpoint row 하나를 추가할 때마다 전체 JSONL을 쓰기 전과
쓴 뒤에 다시 읽고, 매번 checkpoint 디렉터리까지 `fsync`했다. 전체 row 수를
`n`이라 하면 누적 파일 읽기가 O(n²)이어서 Letter 138의 8,566 effects 실제
적용을 막았다. Windows에서는 row마다 파일을 다시 여닫는 비용도 컸다.

## 결정과 구현

- 기존 `wom-kit/exact-operation-checkpoint/v1` JSONL bytes와 경로를 변경하지
  않았다. sidecar나 새 schema도 만들지 않았다.
- 새 process 또는 resume는 기존 전체 JSONL을 한 번 읽어 canonical JSON과
  손상을 검증한다.
- 같은 writer-lock 수명 안에서는 검증한 파일 identity·size·mtime cursor와
  하나의 `O_APPEND` read/write descriptor를 재사용한다.
- 각 row는 계속 canonical JSON 한 줄로 append하고 매 row마다 file `fsync`한
  뒤, 방금 추가한 byte range를 다시 읽어 exact match를 확인한다.
- 다음 append 전에 descriptor/path identity, 예상 size, mtime과 플랫폼에서
  관측 가능한 path change-time token을 다시 확인한다. truncation, replacement,
  tail tamper, stale concurrent store는 fail-close한다.
- descriptor는 finalize의 전체 재검증 전에 닫으며, 실패 경로에서도
  archive-wide writer lock을 놓기 전에 닫는다.
- 지원되는 writer끼리는 archive-wide OS lock으로 process 간 배제하고, 같은
  process에서 하나의 lock을 공유한 store끼리는 공유 mutex로 배제한다.
- 디렉터리 `fsync`는 checkpoint 파일 이름을 최초 생성할 때 한 번만 한다.
  기존 파일의 성장과 row bytes의 내구성 경계는 file `fsync`가 담당하므로
  row마다 directory `fsync`할 필요가 없다.
- final receipt를 만들기 전에는 JSONL 전체를 다시 읽고 sequence, manifest,
  execution, approval, previous hash, checkpoint hash, stage, field receipt의 전체
  chain을 재검증한다. 승인·manifest 결속 규칙은 변경하지 않았다.

따라서 한 실행의 checkpoint 전체 파일 scan은 신규 실행 기준 2회(초기 부재
확인 1회, final chain 검증 1회)이고, 각 append는 최대 64 KiB인 현재 row만
처리해 O(1)이다. 총비용은 O(n)이다.

## 실제 규모 benchmark

명령:

```powershell
python tools/benchmark_exact_operation_checkpoint_store.py `
  --effect-count 8566 --max-elapsed-seconds 180 --format json
```

Windows / Python 3.12 / 실제 임시 파일과 실제 `fsync`를 사용한 synthetic
Letter 138 규모 결과:

| 항목 | 결과 |
|---|---:|
| effects | 8,566 |
| durable checkpoint rows | 25,698 |
| checkpoint bytes | 27,979,179 |
| 전체 시간 | 53.391초 |
| 처리량 | 481.317 rows/초 |
| 전체 checkpoint scan | 2회 |
| checkpoint directory fsync | 생성 시 1회 |
| 첫 상태 | 0.000초 |
| 최대 progress gap | 1.375초 |
| 승인 binding | 유지 |
| 결과 | `ok=true` |

같은 8,566-effects benchmark의 앞선 반복 실행은 44.375초와 55.344초였고,
공유 writer-lock mutex까지 포함한 최종 코드를 다시 실행한 위 53.391초 결과를
인수 기준 기록으로 사용했다. 세 실행 모두 full scan 2회, directory fsync
1회, 첫 상태 0.000초, 10초 미만 상태 간격을 만족했다.

1,000-effects 예비 비교에서 파일을 row마다 여닫던 선형화 1차 구현은
37.641초, descriptor를 writer-lock 수명에 안전하게 결속한 최종 구현은
4.156초였다.

## 회귀 경계

- 기존 canonical JSONL prefix를 byte-for-byte 보존한 채 append
- truncation, 파일 replacement, same-size corruption, tail 증가·변조 차단
- newline 없는 crash tail의 resume 차단
- stale concurrent store와 writer-lock identity drift 차단
- 실제 `os._exit` 뒤 fsync된 row 재개
- writer-lock 종료 시 cached descriptor 정리
- finalize 직전 앞쪽 chain 변조 시 final receipt 미발행
- 기존 exact manifest 승인 binding·apply·resume·revert 테스트 유지

## 남은 위험

- `os.fsync` 자체가 운영체제나 고장 난 저장장치에서 10초 넘게 block되면 그
  syscall 내부에서는 Python heartbeat를 낼 수 없다. 실제 25,698-row 계측의
  최종 계측의 최대 상태 간격은 1.375초였다.
- 지원 writer 간 배제 경계인 exclusive writer lock을 무시한 외부 writer가
  파일 bytes를 같은 길이로 바꾸고
  mtime까지 정확히 복원하는 경우, 바로 다음 append의 O(1) metadata guard만으로
  앞쪽 byte 변조를 찾을 수는 없다. 그러나 final receipt 전과 모든 resume에서
  전체 hash chain을 다시 읽으므로 변조된 실행을 완료·재개할 수 없다.
- Windows에서는 기존 정책대로 directory handle `fsync`가 no-op이다. 각 row의
  file `fsync`와 최초 파일 생성 시 호출 경계는 유지되지만, 디렉터리 내구성은
  NTFS/Windows의 파일 생성 semantics에 의존한다.

## 독립 검토 후 P1 수정

독립 검토는 checkpoint JSONL full scan 자체 외에 실제 apply 진행률 계산에
남아 있던 O(n²) 순회를 발견했다. 각 item 상태를 발행할 때마다 모든
`completed_fields`를 다시 합산했기 때문이다. `_CheckpointState`가 완료 field
수를 한 번 계산하고 field checkpoint 성공 때 O(1)로 증가시키도록 수정했으며,
100-item 회귀 테스트가 apply loop 안에서 completed-field mapping을 한 번도
재순회하지 않고 최종 진행률 100을 발행함을 검증한다.

같은 8,566-effect / 25,698-row 실제 파일 benchmark는 수정 뒤 40.797초,
629.899 rows/초로 통과했다. full checkpoint scan 2회, checkpoint directory
sync 1회, 첫 engine 상태 0.000초, 최대 상태 간격 1.407초를 유지했다.

독립 검토는 POSIX directory `open/fsync` 실패를 기존 helper가 삼키는 문제도
발견했다. directory sync helper는 이제 성공 여부를 반환하며, private
directory·writer lock·최초 checkpoint 이름·최종 result receipt 생성 경계는
실패를 성공으로 처리하지 않는다. 최초 checkpoint 이름 sync 실패 주입
테스트는 content writer 전에 `exact_operation_checkpoint_write_failed`로
차단되고 cached descriptor를 닫음을 검증한다.

Windows에서 archive lock을 무시하는 외부 writer가 checkpoint의 앞쪽 byte를
같은 길이로 바꾸고 timestamp까지 복원하는 공격은 다음 O(1) append guard를
통과할 수 있다. 그러나 final full-chain scan은 result receipt를 차단한다.
이 경계는 non-cooperative external tamper가 필요한 P2 residual로 기록하며,
승인된 exact writer끼리는 archive-wide lock을 계속 강제한다. 또한 benchmark의
0.000초 값은 apply engine 진입 이후 첫 상태만 증명한다. CLI 시작부터 2초 내
첫 출력은 각 공개 writer의 end-to-end release gate에서 별도로 검증한다.
