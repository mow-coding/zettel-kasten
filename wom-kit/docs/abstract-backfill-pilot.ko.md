# 정본 zet 3건 초록 데이터 보완 표본 절차

명시적 `abstract`가 없는 옛 정본 zet가 많은 보관함에서 사용하는 공식 표본
절차입니다. 목적은 사람 검토 흐름을 확인하는 것이며, 보관함 전체를 자동으로
채우는 권한이 아닙니다.

## 반드시 멈추는 지점

정확히 3건만 다룹니다. 아래 검증 명령까지 실행한 뒤 멈추고, 네 번째 zet를
고르기 전에 무엇이 어렵고 느리거나 불안했는지 보고합니다.

## 1. 후보 3건 선택

```text
archive first-read-readiness <archive-root> --dry-run --max-items 3 --progress --format json
```

반환된 순서 그대로 최대 3건을 선택합니다. 각 항목은 안전한 zet 아이디가
있고, 초록 데이터가 없거나 호환용 요약만 있으며, 초록 데이터를 읽을 수 있어야
합니다. 안전한 항목이 3건보다 적으면 그 수만 진행하고 멈춥니다. 더 편한 내용을
찾아 임의로 건너뛰지 말고, 가림 처리됐거나 읽을 수 없는 zet는 다루지 않습니다.

종료코드 0은 진단 명령이 정상 완료됐다는 뜻입니다. 보관함 준비 완료를 뜻하지
않으므로 `readiness_met`과 `state`를 확인합니다.

## 2. 비공개 제안 준비

선택한 zet만 `read-zettel`로 읽습니다. AI가 본문을 바탕으로 짧은 초록 데이터를
비공개로 제안할 수 있지만, 자기 제안을 스스로 검토하거나 승인할 수 없습니다.
다음 위치의 비공개 JSONL에 최대 3행만 둡니다.

```text
.wom-scratch/abstract-backfill/<private-name>.jsonl
```

[초록 데이터 보완 계획](zet-abstract-backfill-plan.md)의 행 계약을 따릅니다.
zet 아이디, 경로, 본문 해시, 제안 문장은 비공개 임시저장소에만 두고 공개
피드백 편지에 붙이지 않습니다.

## 3. 검증하고 사람이 읽기

```text
archive zet-abstract-backfill-plan <archive-root> --proposal .wom-scratch/abstract-backfill/<private-name>.jsonl --max-items 3 --dry-run --progress --format json
```

차단 항목 없이 3건 모두 `ready_for_human_review`여야 합니다. 그다음 사람이
세 zet의 전체 본문과 세 제안 문장을 짝으로 직접 읽습니다. 계획이 정상이라는
사실 자체는 사람 검토가 아닙니다.

계획에서 받은 정확한 제안 SHA-256으로 승인 후 쓰기 명령을 먼저 미리봅니다.

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<private-name>.jsonl --expected-proposal-sha256 <sha256> --dry-run --progress --format json
```

사람 검토가 끝난 뒤에만 다음 승인을 실행할 수 있습니다.

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<private-name>.jsonl --expected-proposal-sha256 <sha256> --approve --reviewed-by person:<reviewer> --affirm-abstracts-reviewed --progress --format json
```

## 4. 검증하고 멈추기

```text
archive first-read-readiness <archive-root> --dry-run --max-items 3 --progress --format json
archive abstract-freshness <archive-root> --dry-run --max-items 3 --progress --format json
archive zet-abstract-backfill-receipt-audit <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-problems 20 --progress --format json
```

누락 초록 데이터가 정확히 3건 줄었는지, 세 초록 데이터/본문 짝이 `fresh`인지,
보완 영수증 이력이 정상인지 확인합니다. 여기서 멈추고 비공개 결과 해시,
실행 시간, 사람 검토 노력, 이해하기 어려운 표현, 차단 항목을 보고합니다.
이 표본을 곧바로 대량 작업으로 확대하지 않습니다.

## 안전 경계

- 어떤 명령도 누락 초록 데이터를 전부 자동 선택하고 자동으로 쓰면 안 됩니다.
- AI는 비공개 제안을 도울 수 있지만, 사람 검토와 승인은 분리되어야 합니다.
- 승인 후 쓰기는 `frontmatter.abstract`만 바꾸고, 내용 없는 해시 근거를 남기며,
  별도의 검토된 되돌리기와 영수증 검진 흐름을 제공합니다.
- 기술적으로 `fresh`여도 그 초록 데이터가 사실이고 유용하며 완전하거나 모델이
  이해했다는 증거는 아닙니다.
