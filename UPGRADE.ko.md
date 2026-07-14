# 업그레이드 가이드

[English Upgrade Guide](UPGRADE.md)

## v0.3.232 명시적 초록 데이터 발행 게이트

보관함 마이그레이션은 필요하지 않습니다. 기존 정본 zet와 과거 영수증은
그대로 유효합니다. 초안은 초록 데이터 없이도 임시저장소에 둘 수 있지만,
정본으로 발행하기 전에는 사람이 검토한 명시적 `frontmatter.abstract`가
반드시 있어야 합니다.

360자 이하의 한 줄 초록 데이터를 넣은 뒤 평소 mint 미리보기를 실행합니다.

```text
archive mint-zet <archive-root> --path inbox/<draft>.md --dry-run --format json
```

`first_read_check.status`가 `ready`이고 `ready_for_publication`이 `true`일
때만 승인 단계로 진행합니다. `summary` 같은 호환용 필드는 이 발행 조건을
대신하지 못합니다. 실제 mint와 이전 `promote` 경로는 초안 전체 SHA-256과
초록 데이터 SHA-256을 함께 묶고, 미리보기 뒤 한 번 읽은 바이트를 다시
검증합니다. 초안의 어느 바이트라도 바뀌었거나 초록 데이터가 없거나
안전하지 않으면 정본, 영수증, 초안 스냅샷을 쓰기 전에 멈춥니다.

검사 기록에는 상태, 글자 수, 제한, SHA-256만 남고 초록 문장은 복사하지
않습니다. 통과는 구조적 준비가 됐다는 뜻일 뿐, 내용의 진실성·완전성·
최신성이나 AI가 실제로 읽었다는 사실까지 증명하지 않습니다.

## v0.3.231 초록 데이터 준비도 검진

보관함 마이그레이션은 필요하지 않습니다. 업데이트 뒤 AI 운영자 프로세스를
다시 시작하고 다음 읽기 전용 명령을 실행합니다.

```text
archive first-read-readiness <archive-root> --dry-run --progress --format json
```

비공개 처리되지 않은 모든 정본 zet에 명시적 `frontmatter.abstract`가 있고,
모든 선택 항목의 안전한 아이디가 하나로 해석될 때만 `state: ready`가 됩니다.
기존 `gist`, `summary`, `description`, `overview`는 호환용 첫 읽기로 남지만,
사람이 명시적 초록 데이터를 검토하고 승인하기 전에는
`state: compatibility_only`입니다. 준비되지 않은 결과의 종료 코드가 0이
아니어도 검진 실패가 아니라 보완할 목록을 정직하게 발견한 것입니다.

이 명령은 초록 데이터만 읽고 아무것도 쓰지 않습니다. 초록 문장의 품질,
AI의 실제 읽기 완료, 오브제 바이트, 외부 서비스, 백필 승인을 증명하지
않습니다. 결과를 검토한 뒤에만 비공개 전체 `zet-catalog-pass`로 진행합니다.

## Frontmatter v0.3 migration

The current v0.3 frontmatter contract requires nested `provenance` and
`visibility` fields. If an archive was created from older
`wom-kit/zettel-kasten-rules/v0.2-draft` guidance, preview the migration before
strict v0.3 validation:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run --format json
```

Approve only after reviewing the planned field changes on a backup or sandbox
copy:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --approve --format json
```

The migration is dry-run-first, rewrites only archive-contained Markdown zettel
frontmatter under `inbox/` and `zettels/`, preserves clean legacy source objects
in `source_refs`, and blocks ambiguous or unsafe source values for manual
review.

이 문서는 `zettel-kasten` / `zet`의 공개 버전 사이를 어떻게 이동해야 하는지 설명합니다.

이 프로젝트는 단순한 코드 묶음이 아니라, archive 규칙, zettel metadata, object manifest, provenance record, 미래의 `ZET` sharing envelope까지 함께 관리하는 버전형 프로토콜입니다.

## 기본 규칙

```text
PATCH upgrade -> 문서, 검증, 호환 가능한 수정
MINOR upgrade -> 호환 가능한 기능 추가 또는 optional field 추가
MAJOR upgrade -> protocol/schema breaking change
```

실제 archive를 업그레이드하기 전에는:

1. 대상 버전의 release note를 읽습니다.
2. private archive repository와 object manifest를 백업합니다.
3. `archive doctor --strict`를 실행합니다.
4. migration command가 있다면 먼저 dry-run으로 실행합니다.
5. 생성된 receipt를 확인한 뒤에만 private archive 변경사항을 커밋합니다.

아카이브는 사용자의 기억입니다. 조용히 몰래 다시 쓰면 안 됩니다.

## 현재 안전 절차와 upgrade-check

현재 WOM-kit은 실제 archive 업그레이드에서 release note, backup,
`archive doctor --strict`, human review를 기준으로 삼습니다.

아래 read-only 점검 명령을 사용할 수 있습니다.

```text
archive upgrade-check <archive-root> --dry-run --format json
```

이 명령은 doctor, recovery-plan, restore-drill, upgrade readiness 신호를
보고합니다. 파일을 쓰지 않고 `would_change: []`를 반환하며, migration
command를 실행하지 않고, provider를 호출하지 않으며, migration engine도
아닙니다.
top-level `ok`는 점검이 실행됐다는 뜻입니다. 실제 upgrade가 막혔는지,
검토가 더 필요한지, manual review 단계로 넘어갈 수 있는지는
`upgrade_readiness.status`(`ready`, `warnings`, `blocked`)를 확인합니다.

실제 archive를 바로 바꾸지 말고 sandbox copy 또는 backup으로 먼저
확인합니다.

1. private archive control plane을 복사하거나 백업합니다.
2. object manifest와 local objet store가 보존되어 있는지 확인합니다.
3. 대상 release note를 읽습니다.
4. `archive upgrade-check <archive-root> --dry-run --format json`을 실행합니다.
5. `archive doctor --strict`를 실행합니다.
6. `archive index`로 generated search를 다시 만듭니다.
7. 작은 `archive search` smoke test를 실행합니다.
8. migration dry-run이 있다면 실제 migration 전에 먼저 실행합니다.
9. 출력과 receipt를 검토한 뒤에만 private archive 변경을 commit합니다.

project folder 작업에서는 temporary intake staging이 archive of record가
아니라는 점을 기억합니다. cleanup 전에 원본을 objet, source map, manifest,
zet, receipt로 보존해야 합니다.

## v0.3.230 검토한 내용과 승인을 묶는 SHA-256

v0.3.230은 아카이브 migration을 요구하지 않고 reconcile을 자동 실행하지도
않습니다. 달라지는 것은 미리보기 결과가 `drift_class: content_change`일 때의
승인 절차입니다. 공식 업데이트 뒤 AI 운영 프로세스를 새로 시작합니다. 이
패치만 확인하려고 전체 검진을 다시 돌릴 필요는 없고, 문제가 있던 zet만 아래
미리보기를 다시 실행하면 됩니다.

BOM이 있는 canonical과 별도의 retired-draft 불일치는 서로 독립적으로
검토합니다.

```text
archive remint-reconcile <archive-root> --zettel-id <bom-zet-id> --dry-run --strip-bom --diagnostic-only --format json
archive retire-draft-reconcile <archive-root> --zettel-id <retired-draft-zet-id> --dry-run --format json
```

둘 중 하나가 `content_change`이면 결과의 `human_review_plan`과
`review_plan_sha256`을 읽습니다. 이 계획은 문서 내용을 JSON에 복사하지 않고,
사람이 로컬에서 확인할 파일의 아카이브 상대경로와 순서, SHA-256, 달라진 초록
데이터 필드 또는 영수증 참조 이름만 보여줍니다. 사람은 해당 파일을 직접
비교한 뒤 셋 중 하나를 고릅니다.

1. `intentional_change`: 달라진 필드나 참조를 모두 설명할 수 있을 때만
   `human_review_plan.commands.approve_if_intentional`에 나온 명령을 그대로
   실행합니다. `<actor>`에는 실제로 검토한 사람을 적습니다. 내용 변경 승인
   명령의 형태는 다음과 같습니다.

   ```text
   archive remint-reconcile <archive-root> --zettel-id <bom-zet-id> --approve --reviewed-by <actor> --content-changed-ack --reviewed-plan-sha256 <review-plan-sha256> --strip-bom --format json
   archive retire-draft-reconcile <archive-root> --zettel-id <retired-draft-zet-id> --approve --reviewed-by <actor> --content-changed-ack --reviewed-plan-sha256 <review-plan-sha256> --format json
   ```

2. `unintentional_change`: 잘못 바뀐 내용을 복구하거나 고친 뒤, 그 대상의
   미리보기를 다시 실행합니다. 예전 SHA-256으로 승인하면 안 됩니다.
3. `uncertain`: 아무것도 쓰지 않고 멈춘 뒤 사람 소유자에게 묻습니다. 한쪽
   대상의 성공, 분류 결과, 깨끗한 검진 결과는 다른 쪽의 승인이 아닙니다.

승인 명령은 파일을 쓰기 전에 현재 근거로 검토 계획을 다시 계산합니다.
`--reviewed-plan-sha256`이 없거나 형식이 틀리거나 검토 뒤 근거가 바뀌었으면
멈춥니다. 내용 변경 승인이 성공하면 이 SHA-256을 provenance와 별도의 불변
감사 영수증에 기록하고, `content_change_ack_required: false`와
`human_review_plan.status: completed`를 반환합니다. 기존 `format_drift` 승인은
새 옵션 없이도 이전처럼 작동합니다.

## v0.3.229 실행 가능한 BOM reconcile 안내

v0.3.229는 아카이브 migration이나 아카이브 쓰기 경로를 바꾸지 않습니다.
`zettel_has_bom` 검진 항목은 이제 canonical 초록 데이터에서 확인한 안전한 zet
아이디를 실제 미리보기 명령에 채웁니다.

```text
archive remint-reconcile <archive-root> --zettel-id <actual-id> --dry-run --strip-bom --diagnostic-only --format json
```

파일명만 보고 아이디를 추측하지 않습니다. canonical 초록 데이터에 안전한
아이디가 없으면 경고와 힌트는 유지하지만 권장 명령은 생략합니다. 이 경우는
placeholder를 수동으로 채우라는 뜻이 아니라 신원 metadata를 먼저 검토하라는
실패 폐쇄 신호입니다.

BOM 경고와 별도의 retired-draft 영수증 SHA 불일치는 서로 독립된 아래 두
미리보기로 확인합니다. 두 명령 모두 쓰지 않습니다.

```text
archive remint-reconcile <archive-root> --zettel-id <bom-zet-id> --dry-run --strip-bom --diagnostic-only --format json
archive retire-draft-reconcile <archive-root> --zettel-id <retired-draft-zet-id> --dry-run --format json
```

BOM 쪽은 `ok: false`, blocker 존재, `content_change`, `body_changed: true`,
`approval_requires_content_changed_ack: true` 중 하나라도 나오면 멈춥니다.
내용을 가린 결과가 `format_drift`, `bom_stripped: true`, 내용 변경 확인 불필요로
나온 경우에만 `--diagnostic-only`를 뺀 같은 미리보기를 다시 실행해 현재 본문과
초록 데이터를 사람이 확인합니다. 그 확인 뒤에만 다음 승인을 검토합니다.

```text
archive remint-reconcile <archive-root> --zettel-id <bom-zet-id> --approve --reviewed-by <actor> --strip-bom --format json
```

retired-draft 쪽에서 `blocked`나 `unclassified`가 나오면 멈춥니다.
`format_drift_ready_for_review`는 모든 `ref_reports` 행을 검토한 뒤 승인할 수
있습니다. `needs_content_change_review`는 자동 승인 신호가 아닙니다. 현재
canonical과 영수증 근거를 사람이 확인하고 변경이 의도된 경우에만
`--content-changed-ack`를 사용할 수 있습니다. 한쪽 reconcile 성공은 다른
쪽에 대한 승인으로 간주되지 않습니다.

## v0.3.228 실행 가능한 전체 검진 결과와 현재 단계 진행 표시

v0.3.228은 아카이브 migration과 아카이브 쓰기 경로를 바꾸지 않습니다.
공식 프로젝트 업데이트 뒤 새 프로세스를 시작하고, 아카이브 건강 근거가
필요할 때만 전체 검진을 실행합니다.

```text
archive runtime-context <archive-root> --full-doctor --progress --format json
```

결과의 `doctor_findings`는 진단 코드별 전체 ERROR/WARN 개수, 최대 100개의
실행 가능한 항목, 최대 20개의 고유 권장 명령을 남깁니다. 각 항목에는 심각도,
코드, 아카이브 상대경로, 설명, 힌트, 권장 명령, 호환 대상이 포함될 수
있습니다. INFO는 개수만 유지합니다. `truncated`와
`suggested_commands_truncated`는 제한 때문에 모든 항목이나 명령을 싣지
못했는지 명시합니다.

이 계약은 앞으로 생성되는 결과에 적용됩니다. 심각도별 개수만 저장한
v0.3.227 `runtime-context` JSON에서는 이미 버려진 코드, 경로, 설명을 정직하게
복원할 수 없습니다. 따라서 그 과거 개수를 식별하려면 새 검진 한 번은
필요합니다. v0.3.228은 새로 완료된 결과가 같은 근거를 다시 잃지 않게 합니다.

`local-profile-secret-safety`가 실행 중일 때 compact heartbeat는 현재 단계의
안전한 개수만 보여줍니다.

```text
checked_files=<방문한 파일 수>
content_scanned=<내용을 검사한 텍스트형 파일 수>
local_profiles=<검사한 로컬 프로필 수>
skipped_dirs=<건너뛴 무시 대상 디렉터리 수>
```

이전 엣지 source-load 집계는 마지막 `done` 줄을 위해 보존되지만, 더는 현재
안전 검사 단계를 가리지 않습니다. 일반 파일은 순회가 이미 확인한 디렉터리
경계를 재사용하고, 심볼릭 링크는 기존처럼 해석된 경계와 무시 대상 검사를
거칩니다. 비밀값처럼 보이는 파일명, 내용, 로컬 프로필 판정 규칙은 바뀌지
않습니다.

합성 벤치마크는 임시 fixture만 만들고 실제 아카이브를 읽지 않습니다.

```text
python tools/benchmark_local_profile_secret_safety.py --file-count 5000 --format json
```

릴리스 작업 환경의 같은 fixture 즉시 전후 측정은 20.838초에서 11.644초로
개선됐고, 공개 변경 후 도구의 별도 실행은 13.693초였습니다. 파일 크기,
저장장치, 백신 환경이 다른 실제 아카이브의 완료 시간을 보장하는 수치는
아닙니다.

## v0.3.227 전체 검진 엣지 진행 표시 집계

v0.3.227은 아카이브 migration을 하지 않고 검진의 판정이나 읽기 범위를
바꾸지 않습니다. v0.3.225에서 도입한 대상별 엣지 영수증 작업을 기본 compact
진행 표시에 어떻게 보여주는지만 바꿉니다.

전체 검진 명령은 같습니다.

```text
archive runtime-context <archive-root> --full-doctor --progress --format json
```

빠른 `edge-receipt-index`는 시작과 완료만 출력합니다. 실제로 10초 이상
걸릴 때만 heartbeat에 안전한 개수가 추가될 수 있습니다. source load는 전체
검진 동안 다음 누계를 하나만 유지합니다.

```text
sources=<지금까지 읽은 source 수>
candidates=<지금까지 연 후보 영수증 수>
cache_hits=<source 결과 cache hit 수>
```

마지막 `done` 줄이 최종 합계를 보여줍니다. 앞으로 읽게 될 source 수를 미리
예측하려고 별도의 전체 스캔을 추가하지 않습니다.

source별 상세 묶음이 필요하면 직접 검진의 verbose 또는 비공개 progress log를
사용합니다. 이 이벤트의 stage는 `edge-receipt-source-load-detail`입니다.

```text
archive doctor <archive-root> --strict --progress --progress-detail verbose
archive doctor <archive-root> --strict --progress --progress-log logs/doctor-progress.jsonl
```

JSONL은 상세한 로컬 진단 시간을 담을 수 있으므로 비공개로 보관해야 합니다.
8,583개 source와 21,539개 index 이벤트를 사용한 합성 벤치마크에서 shared
compact는 4줄(358바이트), verbose는 51,457줄(약 6.3MB)이었습니다. 메모리
출력 시간은 실제 대화형 터미널 렌더링 비용보다 보수적인 하한선입니다.

## v0.3.226 아카이브 신원 일치 점검과 검토 후 수정

v0.3.226은 자동 migration을 하지 않습니다. 빠른 인수인계 문서,
AI 스타팅 메뉴얼, 검진이 `archive.yml`의 주체 선언과
`archive-identity.yml`의 신원/소유권 정보를 비교합니다. 두 문서가 다르면
먼저 읽은 값을 조용히 채택하지 않고 불일치 상태를 알려줍니다.

`identity_consistency.status`가 `aligned`가 아니면 먼저 미리보기만 실행합니다.

```text
archive identity-reconcile <archive-root> --dry-run --format json
```

v0.3.226의 `init` 또는 온보딩으로 새로 만든 아카이브는 템플릿 신원 아이디와
표시정보를 사용자가 정한 아카이브/주체 정보로 바꾸므로 처음부터 일치합니다.
기존 아카이브는 버전만 올렸다고 자동으로 바뀌지 않습니다.

미리보기는 두 설정 문서만 읽고 아무것도 쓰지 않습니다. 사람 이름이나 신원값은
출력하지 않고, 바뀔 필드명과 현재/수정 후 SHA-256만 보여줍니다. 서로 다른 주체,
아카이브 아이디, 범위, 잘못된 문서는 자동 수정을 막습니다. 같은 주체의 표시정보와
비어 있거나 템플릿 상태인 신원 아이디만 수정 후보가 될 수 있습니다.

결과가 `repair_ready`이면 두 원본 문서를 사람이 확인한 뒤, 그 미리보기가 반환한
`approval_command` 전체를 사용합니다. 승인에는 검토자, 주체정보 검토 확인, 그리고
아카이브/현재 신원/수정 후 신원의 세 해시가 모두 필요합니다. 하나라도 달라지면
쓰지 않고 다시 미리보기를 요구합니다.

승인은 `archive-identity.yml`만 수정하고, 결과 해시를 검증한 뒤
`receipts/identity-reconciles/`에 실제 신원값이 없는 영수증을 씁니다. YAML을 다시
직렬화하므로 주석이나 서식은 정리될 수 있지만 의미상 변경은 표시된 필드로
제한됩니다. 처리 중 영수증 쓰기가 실패하면 원래 신원 문서 바이트를 복원합니다.

```text
archive runtime-context <archive-root> --strict --format json
archive doctor <archive-root> --strict
```

## v0.3.225 전체 검진의 엣지 영수증 대상별 읽기

v0.3.225는 아카이브 migration이나 상태 쓰기가 없습니다. 명시적으로 실행한
전체 검진에서 과거 mint 대상의 SHA가 처음 다르게 보이더라도 모든 엣지 영수증
JSON을 다시 열지 않습니다. 검진은 한 번만 파일명 지도를 만들고, SHA가 다른
원본 zet의 이름에 해당하는 영수증과 현재 엣지가 직접 가리키는 예전 형식의
영수증만 읽습니다.

진행 표시는 비공개 내용을 담지 않는 두 단계로 나뉩니다.

```text
edge-receipt-index: <현재>/<전체>
edge-receipt-source-load: <현재>/<전체>
```

첫 번째 숫자는 전체 영수증 파일명 조사이고, 두 번째 숫자는 해당 zet를 검사하기
위해 실제로 여는 작은 후보 묶음입니다. 어느 단계도 영수증 경로, zet 아이디,
엣지 값, 제목, 본문, 초록, 외부 서비스 값, 비밀값을 출력하지 않습니다.

관리자는 실아카이브를 읽지 않고 8,583건 합성 회귀를 재현할 수 있습니다.

```text
python tools/benchmark_doctor_edge_receipt_index.py --receipt-count 8583 --format json
```

벤치마크는 임시 자료만 쓰고 외부 서비스를 부르거나 파일을 남기지 않습니다.
검진 객체에서 지도 구축 1회, 대상 영수증 읽기 1회, 두 번째 조회의 캐시 적중을
확인합니다. 이는 이전에 멈춘 검진 내부 단계를 검증하는 도구이며, 실아카이브의
전체 작업량은 명시적 전체 검진으로 마지막 확인을 해야 합니다.

## v0.3.224 빠른 인수인계 문서와 반복 없는 연결

v0.3.224는 아카이브 migration이나 상태 쓰기가 없습니다. CLI와 MCP의
인수인계 문서(`runtime-context`)는 이제 기본적으로 빠른 안내만 반환합니다.
정체성, 정책, canonical entrypoint, 로컬 주권, 버전, 작업기록만 읽고 전체 zet와
영수증을 훑는 검진은 만들지 않습니다.

```text
archive runtime-context <archive-root> --format json
```

전체 검진이 실제로 필요한 작업에서만 다음처럼 명시합니다.

```text
archive runtime-context <archive-root> --full-doctor --progress --format json
```

MCP도 같습니다. 빠른 인수인계에는 `full_doctor`를 생략하고, 전체 검진에는
`full_doctor: true`를 씁니다. 두 표면 모두 `inspection.mode`, 전체 검진 실행
여부, 검진 상태, 실제로 넓게 읽은 범위를 보고합니다. 이전처럼 인수인계 문서가
자동으로 전체 검진까지 실행한다고 가정한 스크립트는 명시적 옵션을 추가해야
합니다.

AI 스타팅 메뉴얼(`ai-start-here`) 결과에는 인수인계 문서가 이미 들어 있습니다.
호환용 `first_commands` 목록의 해당 행은 `already_included`와
`run_required: false`로 표시됩니다. 실제 다음 실행은 `next_commands`와
`remaining_ai_runtime_order`를 따릅니다. 원본 작업기록을 고쳐 쓰지는 않지만,
이미 끝난 기본 `Run runtime-context first.` 문장은 AI 스타팅 메뉴얼의 다음 안전
단계로 다시 복사하지 않습니다.

## v0.3.223 전체 검진 영수증 내부 단계

v0.3.223은 아카이브 migration을 요구하지 않으며 v0.3.222의 빠른 기본
`ai-start-here` 동작을 바꾸지 않습니다. 선택적 전체 검진에서는 다음 명령을
사용합니다.

```text
archive ai-start-here <archive-root> --dry-run --full-doctor --progress --format json
```

mint 영수증 하나에서 바깥 개수가 오래 유지되면 heartbeat가 비공개 내용 없는
고정 `phase`를 함께 보여줍니다. 예시는 `target_file_ref`, `file_hash`,
`target_edge_evolution`, `edge_receipt_index`입니다. 영수증 경로, zet 경로·아이디,
오브제 참조, 엣지 값, 제목, 본문, 초록, 외부 서비스 값, 비밀값은 노출하지
않습니다.

공유 명령 reporter는 같은 단계/개수의 일반 진행을 한 번만 formatter에
전달합니다. 이후 같은 개수의 하위 단계는 heartbeat phase만 갱신하고 formatter
잠금을 다시 잡지 않습니다. 검증, 해시, 영수증, 아카이브 파일을 건너뛰는
최적화가 아닙니다.

직접 실행하는 `doctor --progress-detail verbose`와 명시적 비공개 Doctor 진행
로그의 상세 이벤트는 그대로 유지됩니다. 전체 검진은 대형 아카이브에서 계속
수분 걸릴 수 있으며, phase는 생존 신호이지 완료 보증이 아닙니다.

## v0.3.222 빠른 AI 스타팅 메뉴얼

v0.3.222는 아카이브 migration을 요구하지 않고 아카이브 상태를 쓰지
않습니다. 평소 처음 들어올 때는 빠른 안내 명령을 사용합니다.

```text
archive ai-start-here <archive-root> --dry-run --progress --format json
```

이 경로는 정체성, 정책, 작업기록, 주요 경로의 존재 여부만 제한적으로
읽습니다. 전체 검진을 실행하거나 모든 zet와 영수증을 순회하거나 오브제
바이트를 읽지 않습니다. `inspection.mode: quick`과
`inspection.doctor_summary.checked: false`는 이 결과가 출발 안내이지 전체
아카이브 건강 증명이 아니라는 뜻입니다.

전체 아카이브 검진이 실제로 필요할 때만 다음처럼 명시합니다.

```text
archive ai-start-here <archive-root> --dry-run --full-doctor --progress --format json
```

전체 검진 모드는 이전의 정밀 검사를 유지합니다. 검진은 zet 본문, 로컬
오브제 바이트, 비밀 패턴 검사용 아카이브 텍스트를 읽을 수 있고, 결과는 이번
실행에서 각 읽기가 실제로 일어났는지 기록합니다. 그래도 자격증명 저장소나
외부 서비스에는 접근하지 않고, 별도로 비공개 임시 `--output`을 요청하지
않는 한 아무것도 쓰지 않습니다.

진행 표시에는 실제 단위(`mint-receipts` 단계는 `mint_receipts`), 단계 경과
시간, 처리율, ETA가 포함되고 heartbeat도 최신 개수를 보여줍니다. compact
출력은 같은 단계/개수를 30초 동안 다시 출력하지 않으므로 `1/N` 하위 단계가
터미널을 도배하지 않습니다.

## v0.3.221 아카이브 전체 초록 수정 영수증 검진

v0.3.221은 아카이브 migration을 요구하지 않고 아무것도 쓰지 않습니다.
초록 배치를 적용하거나 되돌린 뒤, 다음 명령으로 전체 생명주기를 한 번에
검진합니다.

```text
archive zet-abstract-backfill-receipt-audit <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-problems 100 --progress --format json
```

각 적용 영수증은 다음 두 닫힌 상태 중 하나여야 합니다.

```text
적용 영수증 + 현재 적용 상태 해시
적용 영수증 + 정상 되돌리기 영수증 + 현재 되돌림 상태 해시
```

손상되거나 고아가 된 영수증, 현재 정본 해시 불일치는 차단됩니다. 정상
생명주기는 개수와 하나의 `audit_digest`로만 보여주고, 문제 항목만 제한된
개수로 출력합니다. 문제 출력도 비공개 경로·아이디·본문·초록·검수자 대신
해시와 정렬 인덱스를 사용합니다.

`.wom-scratch/abstract-backfill/` 아래의 알려진 잠금은 내용 자체를 읽지 않고
검진합니다.

- 대응하는 완료 영수증이 있으면 `attention_required` 경고입니다. 실행 중인
  프로세스가 없고 완료 상태가 맞는지 확인한 뒤에만 수동으로 지웁니다.
- 대응하는 완료 영수증이 없으면 해결되지 않은 transaction 차단입니다.
  잠금을 지우기 전에 영수증과 현재 정본 해시부터 확인합니다.

이 검진은 잠금을 지우거나, 영수증을 편집하거나, 정본 zet를 고치거나,
외부 서비스·모델·비밀 저장소를 호출하지 않습니다. green은 로컬 일관성
증거이지 초록 내용의 품질이나 강제 종료 안전성을 증명하지 않습니다.

## v0.3.220 영수증 검증형 초록 보충 되돌리기

v0.3.220은 아카이브 migration을 요구하지 않습니다. 성공한 v0.3.219 초록
배치를 영수증으로 검진하고, 사람 승인 뒤 삽입 전 상태로 되돌리는 기능을
추가합니다. 원래 비공개 proposal 파일은 없어도 됩니다. 적용 명령이 돌려준
영수증 경로와 `receipt.sha256`은 보관해야 합니다.

먼저 아무것도 쓰지 않고 정확히 되돌릴 수 있는지 확인합니다.

```text
archive zet-abstract-backfill-revert <archive-root> --receipt receipts/revisions/abstract-backfill/<digest>.zet-abstract-backfill.json --expected-receipt-sha256 <receipt.sha256> --max-items 500 --dry-run --progress --format json
```

`ready_to_revert`는 현재 모든 정본 파일이 적용 직후 해시와 같고, writer가
넣은 첫 `abstract:` 줄 하나만 제거하면 기록된 적용 전 해시가 정확히 나온다는
뜻입니다. 제거 승인을 뜻하지는 않습니다.

사람이 기록된 모든 초록의 제거를 검토한 뒤 같은 영수증을 명시적으로
승인합니다.

```text
archive zet-abstract-backfill-revert <archive-root> --receipt receipts/revisions/abstract-backfill/<digest>.zet-abstract-backfill.json --expected-receipt-sha256 <receipt.sha256> --max-items 500 --approve --reviewed-by person:<검수자> --affirm-abstract-removal-reviewed --progress --format json
```

되돌리기는 초록 보충 전 파일 바이트를 정확히 복원하고 원래 적용 영수증을
보존하며, `receipts/revisions/abstract-backfill-reverts/` 아래에 텍스트 없는
불변 영수증 하나를 씁니다. 적용 뒤 정본 수정, 초록 변경, 본문 변경, 영수증
불일치, writer와 다른 줄 모양이 하나라도 있으면 배치 전체를 차단합니다.
항목 또는 되돌리기 영수증 쓰기에서 실행 중 오류가 나면 적용된 상태로 다시
복원합니다.

같은 작업을 다시 실행하면 쓰지 않고 `already_reverted`를 반환합니다. 나중에
같은 초록을 다시 넣으려면 새로운 proposal SHA-256과 영수증 아이디가 생기도록
새 proposal 바이트를 준비하고 다시 검토해야 합니다. 기존 적용 영수증은
되돌리기 영수증과 함께 닫힌 기록으로 남습니다.

단기 잠금은 `.wom-scratch/abstract-backfill/` 아래에 있고 외부 편집기를 잠그지
않습니다. 강제 종료 뒤 자동 복구 journal도 아직 없습니다. 남은 잠금을 바로
지우지 말고 두 영수증과 현재 파일 해시를 먼저 확인하십시오.

## v0.3.219 승인 후 초록 보충 쓰기

v0.3.219는 아카이브 migration을 요구하지 않습니다. 대신
`zet-abstract-backfill-plan`을 통과하고 사람이 검토한 비공개 제안서만
정본 zet에 반영하는 별도 쓰기 명령을 추가합니다. 계획이 green이어도
저절로 쓰지는 않습니다.

먼저 같은 제안서 SHA-256으로 실제 반영 내용을 미리 봅니다.

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<비공개-이름>.jsonl --expected-proposal-sha256 <proposal.sha256> --max-items 500 --dry-run --progress --format json
```

결과가 `ready_to_apply`인지 확인한 다음, 사람이 비공개 제안서의 모든 초록을
직접 검토해야 합니다. 검토를 마친 뒤에만 같은 바이트를 명시적으로
승인합니다.

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<비공개-이름>.jsonl --expected-proposal-sha256 <proposal.sha256> --max-items 500 --approve --reviewed-by person:<검수자> --affirm-abstracts-reviewed --progress --format json
```

이 명령은 쓰기 직전에 계획과 모든 정본 파일 해시를 다시 확인합니다.
`frontmatter.abstract` 하나만 추가하고 BOM, 줄바꿈 방식, 본문 바이트,
나머지 초록 데이터의 의미를 그대로 보존한 뒤
`receipts/revisions/abstract-backfill/` 아래에 영수증 하나를 씁니다. 영수증은
대상 아이디·경로와 수정 전·후·본문·초록 해시를 보관하지만 본문이나 초록
문장 자체는 보관하지 않습니다. 공개 명령 출력에는 이 비공개 값과 검수자
값이 나오지 않습니다.

항목 하나 또는 영수증 쓰기에서 오류가 나면, 시도한 모든 정본 파일을
메모리에 보관한 원래 바이트로 되돌리고 불완전한 영수증을 지웁니다. 롤백
메모리를 제한하기 위해 파일 하나는 16 MiB, 배치 전체는 256 MiB로 제한합니다.
성공한 같은 제안서를 다시 실행하면 쓰지 않고 `already_applied`를 반환합니다.

같은 대상 zet를 동시에 편집하지 마십시오. 실행 중 오류는 롤백하지만,
프로세스 강제 종료·정전·컴퓨터 장애는 실행 중 정리 절차를 건너뛸 수 있습니다.
v0.3.219에는 강제 종료 뒤 자동 복구를 위한 journal이 없습니다.

## v0.3.218 검토형 초록 보충 계획

v0.3.218은 아카이브 migration을 추가하지 않고 zet도 쓰지 않습니다. 검증된
카탈로그 페이지에 `abstract_status: missing`이 나오면 선택한 정본 zet 하나만
읽습니다.

```text
archive read-zettel <archive-root> --zettel-id <검증된-zet-id> --section body --format json
```

본문에서 초록 후보를 만들 때 `integrity.file_sha256`을 함께 보관합니다.
`.wom-scratch/abstract-backfill/` 아래 비공개 JSONL에 제공된
`zet-abstract-backfill-proposal.schema.json` 형식으로 한 줄씩 적은 뒤 실행합니다.

```text
archive zet-abstract-backfill-plan <archive-root> --proposal .wom-scratch/abstract-backfill/<비공개-이름>.jsonl --max-items 500 --dry-run --progress --format json
```

planner는 현재 파일 바이트, 정본 아이디/상태, 초록 누락, 제한된 안전 텍스트,
`abstract` 하나만 더하는 바이트 보존 삽입을 검사합니다. 출력에는 행 번호,
개수, 해시만 있고 아이디·경로·본문·초록·proposal 파일명은 없습니다.

green은 `ready_for_human_review`라는 뜻이지 승인 또는 적용 완료가 아닙니다.
v0.3.218에는 쓰기 명령이 없습니다. 정본 파일을 대량 수동 편집하지 말고,
transactional revision writer와 영수증은 다음 별도 capability로 둡니다.

## v0.3.217 해시로 묶인 카탈로그 임시 파일 수명주기

v0.3.217은 아카이브 migration을 추가하지 않고 zet를 다시 쓰지 않습니다.
성공한 `zet-catalog-pass`의 작은 결과에는 이제 `output.sha256`이 들어갑니다.
현재 AI 작업 동안 비공개 임시 파일 이름과 이 값을 함께 유지합니다.

비공개 항목을 출력하지 않고 완성 파일 전체를 먼저 검증합니다.

```text
archive zet-catalog-pass-read <archive-root> --input .wom-scratch/diagnostics/catalog-pass.jsonl --expected-sha256 <pass-결과의-sha256> --dry-run --progress
```

그 다음 같은 해시로 한 번에 한 페이지만 요청합니다.

```text
archive zet-catalog-pass-read <archive-root> --input .wom-scratch/diagnostics/catalog-pass.jsonl --page-index 0 --expected-sha256 <pass-결과의-sha256> --dry-run --progress
```

reader는 선택한 페이지를 돌려주기 전에 JSONL 전체를 순서대로 검증합니다.
완주 정보 누락, 페이지 순서 단절, snapshot 변경, 허용되지 않은 필드,
본문을 읽었다는 표시, 페이지 해시 누락, SHA 불일치가 있으면 페이지를 전혀
출력하지 않습니다.

마지막 `selection.next_page_index`가 `null`이면 삭제를 먼저 미리 봅니다.

```text
archive zet-catalog-pass-cleanup <archive-root> --input .wom-scratch/diagnostics/catalog-pass.jsonl --expected-sha256 <pass-결과의-sha256> --dry-run
```

사람이 확인한 뒤 그 파일 하나만 삭제합니다.

```text
archive zet-catalog-pass-cleanup <archive-root> --input .wom-scratch/diagnostics/catalog-pass.jsonl --expected-sha256 <pass-결과의-sha256> --approve --reviewed-by human:local-operator
```

cleanup은 영수증을 쓰지 않고 숨은 partial 파일도 지우지 않습니다. 이 파일은
WOM 지식이나 백업이 아니라 사용 후 버리는 비공개 임시 파일입니다.

## v0.3.216 한 프로세스 카탈로그 완주

v0.3.216은 아카이브 migration을 추가하지 않고 zet를 다시 쓰지 않습니다.
터미널 AI가 큰 아카이브를 전부 훑어야 할 때, 페이지마다 새 CLI를 실행하는
대신 다음 한 명령을 우선 사용합니다.

```text
archive zet-catalog-pass <archive-root> --status canonical --projection reading --page-size 200 --max-estimated-tokens 8000 --response-envelope-reserve-tokens 2500 --max-output-mib 256 --output .wom-scratch/diagnostics/catalog-pass.jsonl --dry-run --progress --format json
```

첫 페이지에서 로컬 초록 데이터(frontmatter)를 실제로 읽습니다. 중간 페이지는 그
프로세스의 메모리만 재사용합니다. 여러 페이지를 완주하기 직전에는 선택된
로컬 파일 상태를 다시 확인합니다. 도중에 바뀌었다면 차단하고 완성 결과
경로를 만들지 않습니다.

JSONL에는 시작 정보 한 줄, strict 페이지별 한 줄, 완주 정보 한 줄이
들어갑니다. zet 아이디, 제목, 초록, 분류값(facet), 타이, 엣지처럼 비공개 정보가
포함될 수 있지만 zet 본문은 들어가지 않습니다. 이것은 아카이브 기록이나
영수증이 아닙니다. Git에 올리지 말고 한 줄씩 읽은 뒤 사용이 끝나면
삭제합니다.

결과 경로는 `.wom-scratch/diagnostics/` 아래의 새 `.jsonl`이어야 하며 기존
파일을 덮어쓰지 않습니다. 정상적으로 처리된 실패는 새 숨은 임시 partial 파일을
지웁니다. 프로세스를 강제로 끊으면 비공개 partial이 남을 수 있습니다.
다음 실행은 그 개수만 알리고 읽거나 자동 삭제하지 않습니다. 수동 정리
전에는 실행 중인 pass가 없는지 먼저 확인합니다.

기존 페이지형 `zet-catalog`와 MCP 동작은 그대로입니다. 새 명령은 영구
캐시, 생성 지도, 인덱스, host goal/loop 상태를 만들지 않고 외부 서비스도
호출하지 않습니다.

## v0.3.215 프로젝트 버전 갱신

v0.3.215는 프로젝트의 WOM-kit 소스 미러와 버전 핀을 함께 갱신하는 첫
승인형 명령을 추가합니다. 아카이브의 zet을 migration하거나 다시 쓰지
않습니다.

먼저 인터넷 연결이나 파일 쓰기 없이 미리 확인합니다.

```text
archive project-version-update <project-or-archive-root> --target vX.Y.Z --dry-run --progress --format json
```

미리보기의 차단 항목이 없음을 확인한 뒤 한 번의 승인 명령을 실행합니다.

```text
archive project-version-update <project-or-archive-root> --target vX.Y.Z --approve --reviewed-by <actor> --progress --format json
```

승인하면 설정된 `origin/main`과 정확한 대상 태그만 한 번에 받습니다. 그
태그가 main 이력에 포함된 annotated tag인지, 세 버전 파일이 모두 대상과
일치하는지 확인한 다음 detached checkout, 알려진 핀 갱신, 프로젝트 영수증
쓰기를 수행합니다. 작업 폴더가 더럽거나 상태가 모호하면 멈춥니다. checkout
이후 실패하면 이전 checkout과 핀의 원래 바이트를 복구합니다. 받아 둔 Git
ref는 정본이 아닌 발견 상태이므로 남을 수 있습니다.

이 명령을 실행한 현재 Python 프로세스는 자동으로 새 버전이 되지 않습니다.
성공 뒤 새 프로세스를 시작하고 `archive version <root> --format json`으로
실행 위치·소스·핀·태그 일치를 확인해야 합니다. 설정된 원격의 이력은
검증하지만 암호학적 tag signature를 검증했다고 주장하지 않습니다.

부트스트랩 한계: v0.3.215보다 오래된 설치에는 이 명령 자체가 없습니다.
이번 한 번은 기존 안전 절차로 v0.3.215까지 올라온 뒤, 다음 릴리스부터 이
명령을 사용합니다.

## v0.3.214 장시간 명령 진행 표시와 제한된 결과 저장

v0.3.214는 migration을 추가하지 않고 기존 zet도 다시 쓰지 않습니다.
오래 걸리는 `ai-start-here`, `upgrade-check`, CLI `zet-catalog`에 선택형
진행 표시를 사용할 수 있습니다.

```text
archive ai-start-here <archive-root> --dry-run --progress --format json
archive upgrade-check <archive-root> --dry-run --progress --format json
archive zet-catalog <archive-root> --coverage-mode strict --cursor 0 --dry-run --progress --format json
```

진행 표시는 stderr로만 나가고 최종 결과는 stdout에 남습니다. 선택형
`--output .wom-scratch/diagnostics/<name>.json`은 전체 JSON 결과를 저장하고
stdout에는 작은 요약만 보여줍니다. 이 파일은 아카이브 기록이나 영수증이
아닌 비공개 임시 파일입니다. 기존 파일을 덮어쓰지 않으며 Git에 올리지
않아야 합니다.

catalog 진행 표시는 실제 재검사를 보이게 할 뿐, 새 CLI 프로세스가 수행하는
전체 scan을 없애거나 영구 cache를 만들지 않습니다. 두 option을 생략한 기존
호출은 이전과 같습니다.

## v0.3.213 Local sovereignty authority

v0.3.213은 migration이나 기존 zet 재작성을 하지 않습니다. read-only
`local-sovereignty` 계약을 추가하고 runtime, start-here, recovery,
upgrade-check 출력에 동일한 `storage_authority` 모델을 제공합니다.

검토된 local WOM 상태가 정본이며 GitHub, object storage, 외부 DB는
backup/replica 계층입니다. 기존 provider binding은 바뀌지 않고 명령은 live
backup audit를 실행하지 않습니다. `ai-start-here` schema는 v0.2로 올라가므로
해당 결과 schema를 검증하는 caller는 새 field와 version을 받아야 합니다.

## v0.3.212 Compact strict continuation

v0.3.212는 strict catalog pass의 첫 페이지 뒤에서 선택형
`--response-profile continuation`을 제공합니다. cursor 0은 반드시 `full`로
두고 그 페이지의 archive 전체 초록, ID, 순서, scan, workload 진단을
보관해야 합니다. 이후 compact 페이지는 항목, 준비 상태, snapshot, token,
chain, session, 경고, privacy 필드를 유지하고 반복 진단만 생략합니다.

catalog schema는 v0.8로 올라가고 continuation schema는 v0.3을 유지합니다.
응답 profile은 항목 선택, 순서, cursor, chain identity를 바꾸지 않기
때문입니다. 기존 호출은 계속 full 응답을 받고, 진행 중인 v0.3.211 strict
pass도 다음 0이 아닌 cursor부터 compact 응답을 선택할 수 있습니다.
archive migration과 기존 zet 재작성은 없습니다.

## v0.3.211 응답 envelope 토큰 예산

v0.3.211은 전체 compact service-result 크기 측정과 선택형
`--response-envelope-reserve-tokens`를 추가합니다. 기존 호출의
`max_estimated_tokens`는 계속 항목만 대상으로 합니다. reserve를 지정하면
그 값을 먼저 빼고 남은 몫을 항목 예산으로 사용합니다.

catalog schema는 v0.7로 올라가고 continuation schema는 v0.3을 유지합니다.
따라서 strict pass 중간에 page size, 항목 예산, reserve를 바꿔도 cursor를
건너뛰지 않습니다. 추정치는 측정 블록 자체, CLI 들여쓰기, MCP/JSON-RPC
바깥 포장을 제외하며 실제 외부 서비스 토큰 수가 아닙니다. archive
migration은 없습니다.

## v0.3.210 연결 읽기 경로 근거

v0.3.210은 seed 기반 연결 순서에 `projection=routed_reading`을 추가합니다.
일반 `projection=reading`은 작은 기본값으로 유지됩니다. `routed_reading`은
검증된 시작 zet ID와 `order=seeded_connection_walk`을 함께 쓸 때만
동작합니다.

catalog schema는 v0.6, strict continuation schema는 v0.3으로 올라갑니다.
chain hash가 zet ID만이 아니라 snapshot 안의 파일 항목을 서로 다르게
구분하기 때문입니다. 진행 중인 v0.3.209 strict pass는 cursor 0에서 다시
시작합니다. token은 signature나 영수증이 아닌 일시적인 checksum 실수 방지
장치입니다. archive migration이나 기존 zet 재작성은 없습니다.

## v0.3.209 첫 읽기 준비 상태

v0.3.209는 migration이 없고 기존 zet를 다시 쓰지 않습니다. catalog 출력
schema는 v0.5로 올라가지만 strict continuation token schema는 v0.2를
유지합니다.

strict pass 뒤에는 세 신호를 따로 해석합니다.

- `archive_wide_coverage_claim_ready`: 선택한 모든 파일 노드를 방문함
- `archive_wide_abstract_reading_claim_ready`: 비공개 처리된 노드를 제외한
  모든 노드에 읽을 수 있는 첫 읽기 텍스트가 있음
- `archive_wide_followup_resolution_ready`: 모든 노드가 후속 읽기에 사용할
  수 있는 안전하고 고유한 zet ID를 가짐

초록 또는 후속 읽기 신호가 거짓이면 사람의 검토가 필요한 공백입니다.
초록이나 ID를 자동으로 만들거나 다시 쓰지 않습니다.

## v0.3.208 seed 기반 전체 읽기 순서

v0.3.208은 선택형 `--order seeded_connection_walk`와 반복 가능한
`--start-zettel-id`를 추가합니다(MCP는 `order`, `start_zettel_ids`). 기존
path order가 기본값이며 archive migration은 없습니다.

host goal이나 사람이 이미 검증된 zet id를 제공한 경우에만 seed를
사용합니다. 없는 seed는 추측하지 않고 차단합니다. seed와 연결된 node를
먼저 읽은 뒤 끊어진 모든 component도 이어서 읽으므로 범위가 아니라
순서만 바뀝니다.

continuation token schema는 seed 목록 지문을 묶는 v0.2로 올라갑니다.
upgrade 시 진행 중이던 v0.3.207 strict pass는 cursor 0부터 다시
시작합니다. token은 일시적이며 archive 기록이 아닙니다.

## v0.3.207 compact 읽기와 strict 완주

v0.3.207은 CLI와 MCP catalog에 선택형 `projection=reading`과
`coverage_mode=strict`를 추가합니다. 기존 호출은 `projection=full`,
`coverage_mode=page`를 그대로 사용하며 archive migration은 없습니다.

AI가 archive 전체를 읽을 때는 strict mode를 cursor 0에서 시작하고, 이후
매 호출에 직전 페이지의 `coverage.continuation_token`을 전달합니다.
`archive_wide_coverage_claim_ready: true`일 때만 이 연속 chain이 끝까지
도달한 것입니다. 기존 `complete`는 현재 페이지가 scope 끝에 닿았다는
뜻일 뿐, 중간 cursor를 건너뛰지 않았다는 증거가 아닙니다.

token은 checksum을 검사하는 stateless 실수 방지 장치입니다. signature,
attestation, 보안 credential, 영수증이 아닙니다.

## v0.3.206 카탈로그 규모와 토큰 예산

v0.3.206은 CLI와 MCP 카탈로그 페이지에 작업량 추정치와 선택형
`max_estimated_tokens`를 추가합니다. 기존 archive와 호출자는 migration이
필요 없으며, 이 option을 생략하면 기존 item-count pagination이 유지됩니다.

토큰 추정치는 catalog item JSON만 대상으로 하고 4자당 1토큰이라는 공개된
휴리스틱을 사용합니다. 외부 서비스가 보고한 실제 사용량이 아닙니다. MCP는
중간 페이지를 process-local materialized snapshot에서 읽고, 완료 페이지를
내기 전에 로컬 파일 metadata를 전체 재검증합니다. 그때
`catalog_snapshot_changed`가 나오면 cursor 0부터 다시 시작합니다.

## v0.3.205 호스트 AI 초록 읽기

v0.3.205는 v0.3.204의 live catalog를 MCP에도 노출하고 MCP
`read_zettel`에 `section` 인자를 추가합니다. 기존 client가 `section`을
생략하면 이전과 같은 `body` 기본값을 사용합니다. archive migration은
필요 없습니다.

호스트 AI는 `zet_catalog`의 `next_cursor`를 같은 `snapshot.id`로
`complete: true`까지 따라가야 합니다. 본문을 넓게 읽기 전에는
`read_zettel(section: "overview")`를 먼저 사용합니다. 중간에 snapshot이
바뀌면 서로 다른 archive 상태를 섞지 말고 cursor 0부터 다시 시작합니다.

## v0.3.204 선택형 초록

v0.3.204는 선택형 `frontmatter.abstract`와 read-only live `zet-catalog`를
추가합니다. 기존 archive는 migration이 필요 없고 어떤 zet도 자동으로
다시 쓰지 않습니다.

새 초안이나 검토한 수정본에는 아래처럼 360자 이내 초록을 넣을 수 있습니다.

```text
archive create-draft <archive-root> --title <제목> --abstract <초록> --body <본문>
```

기존 zet에 필드가 없으면 `abstract_status: missing`으로 정직하게 표시됩니다.
카탈로그를 완성된 것처럼 보이게 하려고 초록을 대량 자동생성해 조용히 쓰지
말고, 사람이 검토하는 수정 흐름에서 점진적으로 채웁니다.

## 공개 버전

| Version | Status | Upgrade note |
| --- | --- | --- |
| `v0.3.208` | current public pre-release | `wom-kit/docs/releases/v0.3.208.md` |
| `v0.3.207` | superseded public pre-release | `wom-kit/docs/releases/v0.3.207.md` |
| `v0.3.206` | superseded public pre-release | `wom-kit/docs/releases/v0.3.206.md` |
| `v0.3.205` | superseded public pre-release | `wom-kit/docs/releases/v0.3.205.md` |
| `v0.3.204` | superseded public pre-release | `wom-kit/docs/releases/v0.3.204.md` |
| `v0.3.203` | superseded public pre-release | `wom-kit/docs/releases/v0.3.203.md` |
| `v0.3.202` | superseded public pre-release | `wom-kit/docs/releases/v0.3.202.md` |
| `v0.3.201` | superseded public pre-release | `wom-kit/docs/releases/v0.3.201.md` |
| `v0.3.200` | superseded public pre-release | `wom-kit/docs/releases/v0.3.200.md` |
| `v0.3.199` | superseded public pre-release | `wom-kit/docs/releases/v0.3.199.md` |
| `v0.3.198` | superseded public pre-release | `wom-kit/docs/releases/v0.3.198.md` |
| `v0.3.197` | superseded public pre-release | `wom-kit/docs/releases/v0.3.197.md` |
| `v0.3.196` | superseded public pre-release | `wom-kit/docs/releases/v0.3.196.md` |
| `v0.3.195` | superseded public pre-release | `wom-kit/docs/releases/v0.3.195.md` |
| `v0.3.194` | superseded public pre-release | `wom-kit/docs/releases/v0.3.194.md` |
| `v0.3.193` | superseded public pre-release | `wom-kit/docs/releases/v0.3.193.md` |
| `v0.3.192` | superseded public pre-release | `wom-kit/docs/releases/v0.3.192.md` |
| `v0.3.191` | superseded public pre-release | `wom-kit/docs/releases/v0.3.191.md` |
| `v0.3.190` | superseded public pre-release | `wom-kit/docs/releases/v0.3.190.md` |
| `v0.3.189` | superseded public pre-release | `wom-kit/docs/releases/v0.3.189.md` |
| `v0.3.188` | superseded public pre-release | `wom-kit/docs/releases/v0.3.188.md` |
| `v0.3.187` | superseded public pre-release | `wom-kit/docs/releases/v0.3.187.md` |
| `v0.3.186` | superseded public pre-release | `wom-kit/docs/releases/v0.3.186.md` |
| `v0.3.4` | superseded public pre-release | `wom-kit/docs/releases/v0.3.4.md` |
| `v0.3.3` | superseded public pre-release | `wom-kit/docs/releases/v0.3.3.md` |
| `v0.3.2` | superseded public pre-release | `wom-kit/docs/releases/v0.3.2.md` |
| `v0.3.1` | superseded public pre-release | `wom-kit/docs/releases/v0.3.1.md` |
| `v0.3.0` | superseded public pre-release | `wom-kit/docs/releases/v0.3.0.md` |
| `v0.2.60` | superseded public pre-release | `wom-kit/docs/releases/v0.2.60.md` |
| `v0.2.59` | superseded public pre-release | `wom-kit/docs/releases/v0.2.59.md` |
| `v0.2.58` | superseded public pre-release | `wom-kit/docs/releases/v0.2.58.md` |
| `v0.2.57` | superseded public pre-release | `wom-kit/docs/releases/v0.2.57.md` |
| `v0.2.56` | superseded public pre-release | `wom-kit/docs/releases/v0.2.56.md` |
| `v0.2.55` | superseded public pre-release | `wom-kit/docs/releases/v0.2.55.md` |
| `v0.2.54` | superseded public pre-release | `wom-kit/docs/releases/v0.2.54.md` |
| `v0.2.53` | superseded public pre-release | `wom-kit/docs/releases/v0.2.53.md` |
| `v0.2.52` | superseded public pre-release | `wom-kit/docs/releases/v0.2.52.md` |
| `v0.2.51` | superseded public pre-release | `wom-kit/docs/releases/v0.2.51.md` |
| `v0.2.50` | superseded public pre-release | `wom-kit/docs/releases/v0.2.50.md` |
| `v0.2.49` | superseded public pre-release | `wom-kit/docs/releases/v0.2.49.md` |
| `v0.2.48` | superseded public pre-release | `wom-kit/docs/releases/v0.2.48.md` |
| `v0.2.47` | superseded public pre-release | `wom-kit/docs/releases/v0.2.47.md` |
| `v0.2.46` | superseded public pre-release | `wom-kit/docs/releases/v0.2.46.md` |
| `v0.2.45` | superseded public pre-release | `wom-kit/docs/releases/v0.2.45.md` |
| `v0.2.44` | superseded public pre-release | `wom-kit/docs/releases/v0.2.44.md` |
| `v0.2.43` | superseded public pre-release | `wom-kit/docs/releases/v0.2.43.md` |
| `v0.2.42` | superseded public pre-release | `wom-kit/docs/releases/v0.2.42.md` |
| `v0.2.41` | superseded public pre-release | `wom-kit/docs/releases/v0.2.41.md` |
| `v0.2.40` | superseded public pre-release | `wom-kit/docs/releases/v0.2.40.md` |
| `v0.2.39` | superseded public pre-release | `wom-kit/docs/releases/v0.2.39.md` |
| `v0.2.38` | superseded public pre-release | `wom-kit/docs/releases/v0.2.38.md` |
| `v0.2.37` | superseded public pre-release | `wom-kit/docs/releases/v0.2.37.md` |
| `v0.2.36` | superseded public pre-release | `wom-kit/docs/releases/v0.2.36.md` |
| `v0.2.35` | superseded public pre-release | `wom-kit/docs/releases/v0.2.35.md` |
| `v0.2.34` | superseded public pre-release | `wom-kit/docs/releases/v0.2.34.md` |
| `v0.2.33` | superseded public pre-release | `wom-kit/docs/releases/v0.2.33.md` |
| `v0.2.32` | superseded public pre-release | `wom-kit/docs/releases/v0.2.32.md` |
| `v0.2.31` | superseded public pre-release | `wom-kit/docs/releases/v0.2.31.md` |
| `v0.2.30` | superseded public pre-release | `wom-kit/docs/releases/v0.2.30.md` |
| `v0.2.29` | superseded public pre-release | `wom-kit/docs/releases/v0.2.29.md` |
| `v0.2.28` | superseded public pre-release | `wom-kit/docs/releases/v0.2.28.md` |
| `v0.2.27` | superseded public pre-release | `wom-kit/docs/releases/v0.2.27.md` |
| `v0.2.26` | superseded public pre-release | `wom-kit/docs/releases/v0.2.26.md` |
| `v0.2.25` | superseded public pre-release | `wom-kit/docs/releases/v0.2.25.md` |
| `v0.2.24` | superseded public pre-release | `wom-kit/docs/releases/v0.2.24.md` |
| `v0.2.23` | superseded public pre-release | `wom-kit/docs/releases/v0.2.23.md` |
| `v0.2.22` | superseded public pre-release | `wom-kit/docs/releases/v0.2.22.md` |
| `v0.2.21` | superseded public pre-release | `wom-kit/docs/releases/v0.2.21.md` |
| `v0.2.20` | superseded public pre-release | `wom-kit/docs/releases/v0.2.20.md` |
| `v0.2.19` | superseded public pre-release | `wom-kit/docs/releases/v0.2.19.md` |
| `v0.2.18` | superseded public pre-release | `wom-kit/docs/releases/v0.2.18.md` |
| `v0.2.17` | superseded public pre-release | `wom-kit/docs/releases/v0.2.17.md` |
| `v0.2.16` | superseded public pre-release | `wom-kit/docs/releases/v0.2.16.md` |
| `v0.2.15` | superseded public pre-release | `wom-kit/docs/releases/v0.2.15.md` |
| `v0.2.14` | superseded public pre-release | `wom-kit/docs/releases/v0.2.14.md` |
| `v0.2.13` | superseded public pre-release | `wom-kit/docs/releases/v0.2.13.md` |
| `v0.2.12` | superseded public pre-release | `wom-kit/docs/releases/v0.2.12.md` |
| `v0.2.11` | superseded public pre-release | `wom-kit/docs/releases/v0.2.11.md` |
| `v0.2.10` | superseded public pre-release | `wom-kit/docs/releases/v0.2.10.md` |
| `v0.2.9` | superseded public pre-release | `wom-kit/docs/releases/v0.2.9.md` |
| `v0.2.8` | superseded public pre-release | `wom-kit/docs/releases/v0.2.8.md` |
| `v0.2.7` | superseded public pre-release | `wom-kit/docs/releases/v0.2.7.md` |
| `v0.2.6` | superseded public pre-release | `wom-kit/docs/releases/v0.2.6.md` |
| `v0.2.5` | superseded public pre-release | `wom-kit/docs/releases/v0.2.5.md` |
| `v0.2.4` | superseded public pre-release | `wom-kit/docs/releases/v0.2.4.md` |
| `v0.2.3` | superseded public pre-release | `wom-kit/docs/releases/v0.2.3.md` |
| `v0.2.2` | superseded public pre-release | `wom-kit/docs/releases/v0.2.2.md` |

## From `v0.3.202` To `v0.3.203`

사용자 검수를 반영한 operator 용어 정정 패치입니다. 마이그레이션은 필요 없습니다.

Operator-visible notes:

- `archive ai-response-concept-guide <archive-root> --topic operator_vocabulary
  --locale ko-KR --dry-run --format json`은 검수된 operator 용어를
  `confirmed_operator_language`로 보고합니다.
- 검수된 한국어 operator 용어에는 `object_id`=`오브제 아이디`,
  `doctor`=`검진`, `provider`=`외부 서비스`, `containment`=`포함 관계`,
  `safe_preview`=`미리보기`, `approved_write`=`승인 후 쓰기`,
  `external_report`=`공개용 문서`, `private_working_note`=`비공개 문서`가
  포함됩니다.
- `needs_user_translation`은 이후 새 용어 검수용 빈 묶음으로 남습니다.
- `wom-kit/docs/releases/v0.3.203.md`를 보세요.

## From `v0.3.201` To `v0.3.202`

AI 운영자가 사람에게 WOM을 설명할 때 먼저 쉬운 한국어로 말할 수 있게 하는 read-only 어휘 패치입니다. 마이그레이션은 필요 없습니다.

운영자가 보는 변경:

- `archive ai-response-concept-guide <archive-root> --topic operator_vocabulary
  --locale ko-KR --dry-run --format json`이 archive entrypoint, zet/draft,
  objet/evidence, lifecycle action, 검사, 연결, provider, secret 관련 용어를
  묶어서 돌려줍니다.
- `all` topic에도 새 `operator_vocabulary` 섹션이 포함됩니다.
- 기계용 term은 바뀌지 않고, 새 표현은 사람에게 답할 때 쓰는 안내 문장용입니다.
- `wom-kit/docs/releases/v0.3.202.md`를 보세요.

## From `v0.3.200` To `v0.3.201`

AI 운영자가 archive에 처음 들어왔을 때 볼 수 있는 read-only 안내 표지판을 추가하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 보는 변경:

- 새 `archive ai-start-here <archive-root> --dry-run --format markdown|json`
  명령이 생겼습니다. 별칭은 `start-here`, `operator-start-here`입니다.
- 기존 runtime-context, canonical entrypoint, operational-context 메타데이터를
  한 장짜리 first-read map으로 보여줍니다.
- 파일을 쓰지 않고, provider를 호출하지 않고, secret, zettel 본문, objet
  bytes를 읽지 않으며, local absolute path는 기본적으로 redaction합니다.
- `wom-kit/docs/releases/v0.3.201.md`를 보세요.

## From `v0.3.199` To `v0.3.200`

object-storage manifest reconcile audit receipt에 schema와 doctor 검증을 추가하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 보는 변경:

- `object-storage-wom-location-reconcile --approve`가 쓰는 local-only audit receipt에 공개 JSON schema가 생겼습니다: `wom-kit/schemas/object-storage-manifest-reconcile-receipt.schema.json`.
- `archive doctor`는 이제 object-storage manifest reconcile audit receipt의 schema, action, reviewer, path, updated execution receipt ref, 양수 update count, non-echo privacy guard를 검사합니다.
- 명령 동작, approval gate, provider/credential/object-byte를 건드리지 않는 경계는 그대로입니다.
- `wom-kit/docs/releases/v0.3.200.md`를 보세요.

## From `v0.3.198` To `v0.3.199`

object-storage receipt와 manifest의 `wom_uploaded` 연결을 안전하게 맞추는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 보는 변경:

- `archive doctor`는 이제 같은 object/provider/store/remote key를 이미 덮는 유효한 `wom_uploaded` location이 있으면, 반복 `skipped_remote_same` receipt를 `object_storage_upload_wom_location_missing`으로 오탐하지 않습니다.
- 새 CLI 명령: `archive object-storage-wom-location-reconcile <archive-root> --receipt <receipt> --dry-run|--approve`.
- 항상 `--dry-run`을 먼저 실행합니다. `--approve`에는 `--reviewed-by`가 필요합니다.
- 이 명령은 provider 호출, credential 읽기, object byte 읽기, upload/download/sync, remote availability 확인을 하지 않습니다.
- approve 모드는 `objects/manifests/files.jsonl`과 `receipts/providers/object-storage-manifest-reconciles/` 아래 audit receipt 하나만 씁니다.
- 후보 출력은 object id, remote key, bucket name, provider URL, 정확한 credential ref, local absolute path를 일부러 보여주지 않습니다.
- `wom-kit/docs/releases/v0.3.199.md`를 보세요.

## From `v0.3.197` To `v0.3.198`

reconcile approve 결과의 상태 표시를 정리하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 보는 변경:

- `remint-reconcile --approve --format json`과
  `retire-draft-reconcile --approve --format json`은 성공적으로 쓴 뒤
  `status: reconcile_applied`, `overall_status: reconcile_applied`를 반환합니다.
- approve 결과는 이제 `suggested_next_action: run_doctor_to_verify_reconcile`와
  doctor 재검증 `next_safe_actions`를 보여줍니다.
- 적용이 끝난 approve 출력에 이전 dry-run의 `needs_content_change_review` 상태가
  그대로 남지 않으며, 새 approve write가 아직 대기 중인 것처럼 말하지 않습니다.
- Windows에서 JSON 예시를 파일로 저장할 때는 PowerShell의 bare `>` redirection보다
  명시적인 UTF-8 capture를 권장합니다.
- retired-draft receipt가 있는 zet의 schema enum을 직접 고친 경우,
  `remint-reconcile`을 먼저 dry-run/approve하고 이어서 `retire-draft-reconcile`도
  dry-run/approve하는 짝 flow를 사용하세요.
- reconcile 분류와 승인 gate는 그대로입니다.
- `wom-kit/docs/releases/v0.3.198.md`를 보세요.

## From `v0.3.196` To `v0.3.197`

reconcile dry-run next-action guidance를 추가하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `remint-reconcile --dry-run --format json`과 `retire-draft-reconcile --dry-run --format json`에
  `status`, `overall_status`, `suggested_next_action`, `would_write`,
  `approval_would_write`, `approval_requires_content_changed_ack`가 추가됩니다.
- `content_change` dry-run은 이제 `--approve --content-changed-ack` 전에 사람의 내용 검토가 필요하다고 명시합니다.
- `retire-draft-reconcile --format text`도 가능한 경우 `Next safe actions`를 출력합니다.
- reconcile 분류와 승인 gate는 그대로입니다.
- `wom-kit/docs/releases/v0.3.197.md`를 보세요.

## From `v0.3.195` To `v0.3.196`

doctor progress-log path-policy를 더 명확히 하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `doctor --progress-log <path>` summary가 상대 progress-log path는 현재 작업 디렉토리 기준 cwd-relative path임을 명시합니다.
- progress log 파일을 archive receipt가 아닌 local progress artifact로 표시하고, 기본적으로 commit하지 말라고 안내합니다.
- absolute progress-log input은 summary에 그대로 출력하지 않습니다.
- 기본 `doctor` 동작, progress-log 작성 동작, exit code 의미는 그대로입니다.
- `wom-kit/docs/releases/v0.3.196.md`를 보세요.

## From `v0.3.194` To `v0.3.195`

doctor output path-policy를 더 명확히 하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `doctor --output <path>` summary가 해당 path가 archive root 기준 archive-relative path임을 명시합니다.
- full doctor result 파일을 archive receipt가 아닌 local diagnostic artifact로 표시하고, 기본적으로 commit하지 말라고 안내합니다.
- `mint_retired_draft_sha_mismatch`에 `retire-draft-reconcile --dry-run`이 왜 안전한 첫 단계인지 설명하는 hint가 붙습니다.
- 기본 `doctor` 동작과 exit code 의미는 그대로입니다.
- `wom-kit/docs/releases/v0.3.195.md`를 보세요.

## From `v0.3.193` To `v0.3.194`

doctor result capture와 diagnostic guidance를 보강하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `doctor --output <path>`는 전체 diagnostics JSON array를 파일에 쓰고 stdout에는 작은 summary만 출력합니다.
- `doctor --summary`, `--errors-only`, `--diagnostic-level ERROR,WARN`은 exit code 의미를 바꾸지 않고 stdout 출력량만 줄입니다.
- `provenance.creation_mode` enum 오류, object-storage receipt/manifest link gap, BOM zettel warning에 더 안전한 next-action hint가 붙습니다.
- 새 옵션을 쓰지 않으면 기본 `doctor` 출력은 그대로입니다.
- `wom-kit/docs/releases/v0.3.194.md`를 보세요.

## From `v0.3.192` To `v0.3.193`

doctor local-profile secret-safety progress를 보강하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `doctor --progress`가 `local-profile-secret-safety` 내부 progress를 출력합니다: gitignore
  check, archive walk, checked-file count, content-scan count, local-profile count, skipped-dir
  count, 최종 summary.
- 큰 archive walk에서는 `still checking local profile secret safety` heartbeat가 나올 수 있습니다.
- config/text secret-content check는 파일 전체를 한 번에 올리지 않고 chunk 단위로 읽으며, 긴 읽기에서는
  `still scanning secret content ...`를 출력할 수 있습니다.
- result JSON, diagnostics, receipts, manifests, archive 파일은 기존 stage가 원래 보고하던 진단 외에는 바뀌지 않습니다.
- `wom-kit/docs/releases/v0.3.193.md`를 보세요.

## From `v0.3.191` To `v0.3.192`

doctor progress 출력량을 제어하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `doctor --progress`는 이제 기본으로 compact stderr progress를 사용합니다. stage 시작/완료,
  receipt milestone, 긴 무출력 방지 heartbeat, 핵심 edge-index lifecycle event를 남깁니다.
- 전체 상세 receipt trace가 필요하면 `doctor --progress --progress-detail verbose`를 사용합니다.
- `doctor --progress-log <path>`는 모든 progress event를 JSONL로 씁니다. stderr는 계속 compact일 수
  있고, `--progress` 없이 log 파일만 남기는 것도 가능합니다.
- result JSON, diagnostics, receipts, manifests, archive 파일은 바뀌지 않습니다.
- `wom-kit/docs/releases/v0.3.192.md`를 보세요.

## From `v0.3.190` To `v0.3.191`

doctor edge-evolution progress를 보강하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- mint target sha mismatch 뒤 `doctor --strict --progress`가 target edge-receipt evolution 대상
  archive-relative path를 출력합니다.
- edge receipt index 작업이 loading, scan count, ready count, cache hit, target candidate count를
  출력합니다.
- target evolution replay가 target zettel read, cutoff 없음/no-edge-list skip, strict/inclusive
  history check, ok/no-match 결과를 출력합니다.
- 긴 edge receipt scan에서는 `still scanning edge receipts` liveness가 나올 수 있습니다.
- result JSON, diagnostics, receipts, manifests, archive 파일은 바뀌지 않습니다.
- `wom-kit/docs/releases/v0.3.191.md`를 보세요.

## From `v0.3.189` To `v0.3.190`

doctor file-ref drilldown을 보강하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `doctor --strict --progress`가 mint receipt file-reference check 내부를 더 쪼갭니다:
  path resolve, existence check, archive-relative resolved ref, sha field check, stat, cache hit,
  hash 시작/완료, mismatch, target edge-evolution check, ref-ok.
- 새 SHA-256 읽기가 필요하면 파일 크기와 무관하게 읽기 전에 `hashing <section> file bytes`를 출력합니다.
- `still hashing ... file bytes`는 긴 읽기의 chunk heartbeat로만 남기고, 작은 파일에서 필수로 찍히지는 않습니다.
- retired mint source는 `source file ref skipped; source retired`를 출력합니다.
- result JSON, diagnostics, receipts, manifests, archive 파일은 바뀌지 않습니다.
- `wom-kit/docs/releases/v0.3.190.md`를 보세요.

## From `v0.3.188` To `v0.3.189`

doctor liveness를 보강하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `doctor --strict --progress`가 모든 mint receipt에 대해 `started receipt checks`,
  source/target/snapshot file-ref check 이름, `completed receipt checks`를 출력합니다.
- 큰 mint-receipt file SHA 검사에서는 내용 없는 `hashing ... file bytes`,
  `still hashing ... file bytes`, `hashed ... file bytes` liveness를 출력할 수 있습니다.
- heartbeat mode 전환 메시지는 receipt마다 최소 file-ref liveness가 나온다는 점을 명시합니다.
- counted stage ETA는 stage의 처음 9개 샘플 또는 처음 30초 동안 `eta=warming_up`으로 유지됩니다.
- result JSON, diagnostics, receipts, manifests, archive 파일은 바뀌지 않습니다.
- `wom-kit/docs/releases/v0.3.189.md`를 보세요.

## From `v0.3.187` To `v0.3.188`

doctor progress를 보강하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `doctor --strict --progress`가 검사한 모든 mint receipt에 대해 receipt 단위 heartbeat를 출력합니다.
- 자세한 mint-receipt sub-step은 4번째 receipt까지 출력한 뒤, 이후에는 250개마다 그리고 마지막 receipt에서 출력합니다.
- 4번째 receipt 뒤에는 receipt heartbeat로 계속 진행하며 detailed substep은 샘플링한다는 메시지를 명시합니다.
- counted stage ETA는 stage별 시간을 쓰고, 처음 몇 개 샘플만 있는 동안에는 과장된 ETA 대신 `eta=warming_up`을 출력합니다.
- result JSON, diagnostics, receipts, manifests, archive 파일은 바뀌지 않습니다.
- `wom-kit/docs/releases/v0.3.188.md`를 보세요.

## From `v0.3.186` To `v0.3.187`

AI artifact lifecycle inventory를 추가하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `archive ai-artifact-inventory <archive-root> --dry-run --format json`은 정해진 AI artifact
  root만 점검합니다: `.wom-scratch/`, `workbench/ai-scratch/`, `staging/ai/inbox/`,
  `staging/ai/reviewed/`.
- 후보가 아직 `unreviewed_ai_artifact`인지, 아니면 matching AI artifact
  `source-intake-record`가 이미 있는지 보여줍니다.
- JSONL 대화 로그와 다른 AI 생성 파일은 canonical zet 본문으로 바로 넣는 대상이 아니라,
  필요하면 raw evidence로 objet 보존할 수 있는 후보입니다. 안전한 경로는 raw artifact ->
  objet/source evidence -> derived/distilled text -> draft zet -> human review -> canonical zet입니다.
- 이 명령은 파일 본문을 읽지 않고, content hash를 계산하지 않고, 파일을 쓰거나 지우지 않고,
  zet을 만들지 않고, provider를 호출하지 않으며, `--show-relative-paths`를 명시하지 않는 한
  archive-relative path도 출력하지 않습니다.
- `wom-kit/docs/releases/v0.3.187.md`를 보세요.

## From `v0.3.185` To `v0.3.186`

운영자 진단을 보강하는 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `object-storage-adopt-existing`에 `--stop-after-plan`이 추가되었습니다. `--approve` 명령 모양을 그대로 쓰면서 key-map/resume plan만 계산하고, credential 값 읽기, provider HEAD, manifest 갱신, execution receipt 쓰기 전에 멈춥니다.
- 최종 `--format json` 또는 text 결과는 stdout으로 나갑니다. 선택형 `--progress` heartbeat는 stderr로 나가므로, 구조화된 결과를 보는 script는 stdout을 보거나 stderr를 따로 redirect해야 합니다.
- `adopt_summary`에 `plan_only`, `plan_only_stop_stage`, `planned_remote_head_count`, `unresolved_remote_key_count`, `existing_matching_wom_uploaded_location_count`, 그리고 같은 store의 `wom_uploaded` raw count와 실제 gating count가 추가되었습니다. 그래서 단순 `store_ref` manifest count가 실제 resume skip 후보보다 큰 이유를 설명할 수 있습니다.
- `doctor --strict --progress`는 처음 세 개 mint receipt에 대해 더 자세한 sub-step을 출력하고, detailed receipt마다 `completed receipt checks`를 찍습니다. `target mint receipt link ok` 이후 멈춤이 다음 receipt 문제인지 더 잘 좁힐 수 있습니다.
- `wom-kit/docs/releases/v0.3.186.md`를 보세요.

## From `v0.3.184` To `v0.3.185`

진단을 보강한 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `object-storage-adopt-existing --progress`는 v0.3.183의 matching resume summary를 계속
  출력합니다. 이제 같은 provider/digest location이 있지만 현재 실행의 `store_ref` 또는
  resolved `remote_key`와 맞지 않으면 `resume nonmatching-provider summary`도 출력합니다.
- `adopt_summary`에 `same_provider_nonmatching_location_count`,
  `same_provider_nonmatching_declared_uploaded_count`, `same_provider_store_ref_mismatch_count`,
  `same_provider_remote_key_mismatch_count`가 추가됩니다.
- `provider_location_mismatch_gap` warning은 legacy/nonmatching `declared_uploaded` location이
  evidence이긴 하지만 현재 store/key run의 `--skip-existing-wom-uploaded` 후보는 아니라는 점을
  설명합니다.
- `doctor --strict --progress`는 `checking target mint receipt link`를 target mint block,
  receipt-path, relative-path, comparison, ok/error sub-step으로 더 잘게 보여줍니다.
- `archive version <root>` text output은 import module redaction line을 보여줍니다.
  source mirror와 editable/global install drift를 볼 때는 `--no-redact-local-paths`로 실제
  module path를 확인할 수 있습니다.
- `wom-kit/docs/releases/v0.3.185.md`를 보세요.

## From `v0.3.183` To `v0.3.184`

사람이 읽는 zet viewer 표면을 보강한 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `archive read-zettel --section document`는 한 zet을 WOM 문서 화면으로 읽습니다.
  frontmatter detail은 숨기고 text output은 본문만 출력합니다.
- JSON output에는 `viewer_mode`, `frontmatter_hidden`,
  `raw_frontmatter_delimiters_echoed: false`가 들어갑니다. 단순 viewer가 저장 metadata와
  문서 본문을 추측 없이 분리할 수 있게 하기 위한 신호입니다.
- canonical Markdown 파일 형식에는 여전히 id, provenance, edge, visibility, receipt를 위한
  YAML frontmatter가 있습니다. 이번 변경은 저장 형식이 아니라 읽기 표면에 대한 변경입니다.
- `wom-kit/docs/zet-frontmatter-viewer-contract.md`와
  `wom-kit/docs/releases/v0.3.184.md`를 보세요.

## From `v0.3.182` To `v0.3.183`

resume 진단과 progress를 보강한 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `object-storage-adopt-existing --progress`가 verified remote HEAD loop에 들어가기 전에
  `adopt-plan` resume summary를 출력합니다. matching provider/store/key location을
  `wom_uploaded`, `declared_uploaded`, other로 나누어 보여줍니다.
- `adopt_summary`에 `existing_matching_location_count`,
  `existing_declared_uploaded_count`, `existing_other_location_count`,
  `expected_resume_skip_count`가 추가됩니다.
- matching `declared_uploaded` location이 있으면 `declared_upload_resume_gap` warning을 냅니다.
  이 location들은 WOM이 검증한 `wom_uploaded`가 아니므로 `--skip-existing-wom-uploaded`로
  skip할 수 없고, verified adopt HEAD로 승격해야 합니다.
- `doctor --strict --progress`는 target frontmatter loading을 read/BOM/fence/YAML/load와
  mint-link sub-step으로 더 잘게 보여줍니다.
- `wom-kit/docs/releases/v0.3.183.md`를 보세요.

## From `v0.3.181` To `v0.3.182`

basoon 재검증 후속 additive patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `archive object-storage-adopt-existing ... --approve --skip-existing-wom-uploaded`는 중단된
  verified adopt를 다시 이어갈 때 쓰는 resume helper입니다. 같은 provider/store/key에 대해 이미
  matching `wom_uploaded` manifest location이 있는 object는 `already_wom_uploaded_manifest`로
  보고하고 remote HEAD를 다시 치지 않습니다.
- 기본값은 계속 보수적입니다. `--skip-existing-wom-uploaded`를 생략하면 verified adopt는 기존처럼
  resolved key마다 다시 HEAD합니다. 이 resume option은 `--content-hash-verify`와 함께 쓰면 거절됩니다.
- adopt planning은 matching existing `wom_uploaded` location 개수를 보고하고, 개수가 있는데 resume
  option이 꺼져 있으면 `resume_hint` warning을 냅니다.
- `archive doctor --strict --progress`는 `mint-receipts` 내부 sub-step과 file SHA-256,
  zettel frontmatter, BOM evidence cache summary를 출력합니다.
- `wom-kit/docs/releases/v0.3.182.md`를 보세요.

## From `v0.3.180` To `v0.3.181`

additive operator-progress patch입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- `archive staged-cleanup-check <root> --staged <folder> --dry-run --progress`가 manifest
  로딩, zettel reference 스캔, staged entry walk, file verify, 큰 staged/store file hash 중
  content-free 진행률을 stderr로 출력합니다.
- `--progress`를 생략하면 기존 기본 출력과 result JSON은 그대로입니다.
- progress line에는 stage name과 count/byte total만 들어갑니다. staged file name, object id,
  local absolute path, provider URL, token, secret value는 새로 넣지 않습니다.
- `wom-kit/docs/releases/v0.3.181.md`를 보세요.

## From `v0.3.179` To `v0.3.180`

성능을 단단하게 만든 additive 패치입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- **대형 `object-storage-adopt-existing --key-map` plan resolution이 object마다 manifest를
  다시 스캔하지 않습니다.** adopt plan은 실행마다 manifest index를 한 번 만들고 object-id를
  O(1)로 찾습니다. 기존 first-record-wins 의미는 유지합니다.
- **`archive doctor` receipt stage가 실행별 파일 증거 cache를 재사용합니다.** 같은 doctor
  실행 안에서 파일 SHA-256, zettel frontmatter, BOM 확인 결과를 재사용하여 `mint-receipts`
  같은 receipt 검사 단계의 반복 디스크 읽기를 줄입니다.
- 기존 명령 형태, progress 출력, result JSON, receipt 형식은 바뀌지 않습니다.
- `wom-kit/docs/releases/v0.3.180.md`를 보세요.

## From `v0.3.178` To `v0.3.179`

내용을 줄인 진단 출력만 추가된 릴리즈입니다. 마이그레이션은 필요 없습니다.

운영자가 볼 변화:

- **`archive remint-reconcile --diagnostic-only --format json`**은 dry-run 전용 출력입니다.
  `drift_class`, `body_changed`, `body_diff_diagnostic`, blocker/warning, frontmatter 필드
  이름/개수는 남기고 `current_canonical_text`와 frontmatter 값은 뺍니다.
- **승인 경로는 일부러 가리지 않습니다.** `--diagnostic-only`는 `--approve`와 함께 쓰면
  거부됩니다. approve는 사람이 현재 디스크 내용을 직접 보고 검토해야 하기 때문입니다.
- 기존 `remint-reconcile --format json` 출력은 호환성을 위해 그대로 유지됩니다.
- `wom-kit/docs/releases/v0.3.179.md`를 보세요.

## From `v0.3.177` To `v0.3.178`

운영자 진행률 출력에 대한 추가적(additive) 패치입니다. 마이그레이션은 필요 없습니다.

운영자에게 보이는 변경:

- **`archive doctor --progress`**는 오래 도는 doctor 실행 중 stage start/done 줄을 stderr로
  출력합니다. JSON/text 진단 출력은 바뀌지 않습니다.
- **`object-storage-adopt-existing --progress`**는 plan 해석과 adopt HEAD loop에 대해 안전한
  stage/count heartbeat를 출력합니다. object id, remote key, bucket name, provider URL, 정확한
  credential ref, token, secret value는 출력하지 않습니다.
- **마이그레이션 없음; 기본 출력 변경 없음.** `--progress`를 넘길 때만 새 출력이 생깁니다.
- `wom-kit/docs/releases/v0.3.178.md`를 보세요.

## From `v0.3.176` To `v0.3.177`

object-storage 업로드 어댑터의 `--force-reupload`에 대한 추가적(additive) 안전 패치입니다.
마이그레이션이 필요 없고, 기본 idempotency 동작은 바뀌지 않습니다.

운영자에게 보이는 변경:

- **`--force-reupload`가 이제 resume-ledger-only skip도 우회합니다.** post-crash 또는
  handoff 상태에서 terminal resume-ledger row는 남아 있지만 manifest에는 현재 `wom_uploaded`
  위치가 없을 수 있습니다. 이때 검토된 force 실행은 더 이상 `skipped_already_present`로
  끝나지 않고 provider PUT 경로까지 갑니다.
- **강제 실행에서 PUT이 0회면 차단됩니다.** force 실행 출력은 `forced_reupload: true`를
  포함하고, provider PUT이 시도되지 않으면 `ok:false`와 `force_reupload_not_performed`를
  반환합니다.
- **마이그레이션 없음; 기본 동작 변경 없음.** `--force-reupload`가 없으면 기존
  resume-ledger/idempotency skip은 그대로 동작합니다.
- `wom-kit/docs/releases/v0.3.177.md`를 보세요.

## From `v0.3.175` To `v0.3.176`

추가적(additive)이며 DX 전용인 reconcile 본문-diff 진단 하나입니다. **동작이나 분류 변경 없음,
마이그레이션 없음.** 드리프트 분류기는 바이트 단위로 동일합니다.

운영자에게 보이는 변경:

- **`v0.3.176`은 내용을 노출하지 않는 `body_diff_diagnostic`을 추가합니다** (`remint-reconcile`
  및 `retire-draft-reconcile` 플랜 출력). 앞쪽 BOM 하나 제거 + CRLF/CR→LF 접기 이후에도 두 본문이
  여전히 다를 때 드리프트가 `content_change`로 분류되는데, 이제 플랜은 그것이 어떤 종류의 sub-BOM
  잔차인지 보고합니다: 고정된 `category`
  (`final_newline_only` / `trailing_whitespace_only` / `unicode_normalization_only` /
  `content_difference`), `first_differing_byte_offset`(정수), `normalized_length_delta`(정수),
  그리고 unicode 경우에 한해 닫힌 열거형 NFC/NFD 형태 라벨. 오직 숫자와 고정 라벨만 방출하며,
  본문 텍스트는 절대 방출하지 않습니다.
- **엄격한 분류 no-op입니다.** drift_class 술어 이후에 계산되어 출력 dict만 장식합니다(v0.3.172
  strip-BOM 프리뷰와 완전히 동일). `drift_class`, `classification_basis`,
  `content_change_ack_required`, 그리고 `bytes_normalized_for_content_compare`는 이 기능이 있든
  없든 바이트 단위로 동일합니다. 공백/정규화 + 실제 편집이 섞인 diff는 정직한
  `content_difference`로 남으며 절대 세탁되지 않습니다.
- **오해를 부를 수 있는 경우에는 키가 없습니다**: 앵커/스냅샷이 없는 플랜(`body_changed` None)과
  `format_drift` 플랜(`body_changed` False). 두 CLI 텍스트 프린터는 내용 없는 요약 한 줄을
  추가로 얻고, JSON 소비자는 키가 있을 때만 봅니다.
- **마이그레이션 없음; 동작 변경 없음.** 기존 receipt와 매니페스트는 영향받지 않습니다.
- `wom-kit/docs/releases/v0.3.176.md`를 보세요.

## From `v0.3.174` To `v0.3.175`

object-storage 업로드 어댑터를 위한 추가적(additive) 라이브 검증 보조 기능 두 가지입니다.
마이그레이션이 필요 없고, 기본 동작과 기존 receipt/매니페스트는 바이트 단위로 동일합니다.

운영자에게 보이는 변경:

- **`v0.3.175`는 승인 게이트가 걸린 `--force-reupload`를 추가합니다** (`object-storage-upload`).
  이미 존재하며 크기/해시가 일치하는 객체를 다시 PUT해서 라이브 프로바이더 PUT(예: 강제된
  작은 멀티파트)를 실행할 수 있게 합니다. `--approve`와 `--reviewed-by`가 모두 필요하고,
  비-sha 키 전략에서는 거부되며, `--dry-run`에서는 무효이고, PUT 이전 로컬
  `sha256(local)==object_id` 재검증이 그대로 실행되어 손상된 로컬 파일은 어떤 PUT보다 먼저
  거부됩니다. 실행 receipt는 최상위 `forced_reupload` 불리언을 기록합니다.
- **실제 멀티파트(`part_count>1`)가 이제 업로드 tier2 증명으로 인정됩니다**(기존 5 GiB
  `bytes_uploaded` 경로와 함께). 따라서 5 GiB 이상 객체가 없는 store도 강제된 작은
  멀티파트로 업로드 tier2를 증명할 수 있습니다. adopt 티어 사다리는 영향을 받지 않습니다.
- **마이그레이션 없음; 기본 동작과 기존 receipt/매니페스트는 바이트 단위로 동일합니다.**
  플래그가 없으면 모든 경로가 동일하고, 기본 receipt는 항상 존재하는 `forced_reupload: false`
  불리언만 추가로 갖습니다.
- `wom-kit/docs/releases/v0.3.175.md`를 보세요.

## From `v0.3.173` To `v0.3.174`

검증된 adopt tiered gate에 대한 추가적(additive) 수정 하나입니다. 마이그레이션이 필요 없고,
기존 receipt와 매니페스트는 영향을 받지 않으며, object-storage-upload 티어 사다리는 바이트
단위로 동일합니다.

운영자에게 보이는 변경:

- **adopt tiered gating이 업로드 5 GiB 멀티파트 증명과 분리됩니다.** 검증된
  `object-storage-adopt-existing --approve`는 HEAD 전용(0바이트 이동)이므로, 더 이상
  object-storage-upload 티어 2(5 GiB / 멀티파트 PUT 증명)로 증명된 store를 필요로 하지
  않습니다. 이제 이진(binary) adopt 전용 게이트를 씁니다: 단일 tiny-first adopt는 항상
  허용되고, 검증된 tiny-first adopt가 정확히 1건 있으면 임의 크기의 배치 adopt가 열립니다.
  대용량 이관 운영 절차: `object-storage-adopt-existing --only <one-sha> --approve`를 한 번
  실행한 뒤 전체 `--key-map` 배치를 다시 실행하세요.
- **adopt blocker 토큰 개명.** adopt 게이트 blocker는 이제 `adopt_tiny_first_unmet`입니다
  (기존 `tiered_gate_unmet`). object-storage-upload 게이트는 `tiered_gate_unmet`을 그대로
  유지합니다. adopt blocker 문자열을 매칭하던 스크립트를 갱신하세요.
- **마이그레이션 없음; 그 외 변화 없음.** 기존 실행 receipt와 매니페스트 위치는 영향을 받지
  않습니다. 업로드 receipt는 여전히 adopt를 열지 못하고, declared/미검증 adopt는 여전히
  카운트되지 않으며 PUT을 게이팅하지 않고, 잘못된 `--key-map`은 여전히 0건으로 self-limit
  합니다.
- `wom-kit/docs/releases/v0.3.174.md`를 보세요.

## From `v0.3.172` To `v0.3.173`

추가적(additive)인 명령 하나입니다. 마이그레이션이 필요 없고, 모든 기본 경로는 v0.3.172와
바이트 단위로 동일합니다.

운영자에게 보이는 변경:

- **새 `archive migrate --target base-link-types --dry-run|--approve --reviewed-by
  <actor>`.** archive-local `zettel-kasten/types.yml`에 누락된 모든 base WOM-kit link
  type을 덧붙입니다(recommended-9 `link-types-v0.3` 집합의 상위집합이라 `continues`도 함께
  끌어옵니다). append-only, no-clobber입니다: 기존 항목은 제거·개명·재정렬·값 변경을 하지
  않으므로 divergent same-id 커스터마이징이 항상 이깁니다(`present_not_overwritten`에 보고).
  `--approve`에는 `--reviewed-by`가 필요합니다. `receipts/migrations/base-link-types.*
  .migration.json` 아래에 receipt(`receipt_kind: base_link_types_sync`)를 쓰고, 롤백을
  포함한 원자적 쓰기이며 멱등적입니다. 의도적으로 **`--revert`는 없습니다**
  (`--revert --target base-link-types`는 닫힘 실패). 실행하지 않으면 변화 없음.
- **로컬 `types.yml`이 없으면 안전 no-op.** archive에 로컬 `zettel-kasten/types.yml`이
  없으면 sync는 아무것도 쓰지 않고 파일도 만들지 않습니다 — 이미 모든 현재·미래 base link
  type을 상속합니다. 이 명령을 돌리려고 일부러 로컬 `types.yml`을 만들지 마세요. 로컬
  `types.yml`은 base를 영구적으로 가립니다(고정).
- **doctor 라우팅.** `archive doctor`는 이제 정의되지 않은 edge type을 만난 운영자를
  `archive migrate --target base-link-types --dry-run`으로 안내합니다.
- **정직성.** archive가 자기 `types.yml`을 가지면 base를 영구적으로 가리므로, 이후의 모든
  base link type도 수동 `migrate --target base-link-types`가 필요합니다(자동 전파 없음).
  sync는 이 릴리스 시점의 base 항목 형태를 복사합니다(스냅샷). 형제 `link-types-v0.3`
  마이그레이션처럼 `safe_dump`로 `types.yml` 전체를 정규화/재작성합니다 — 주석·앵커·flow
  스타일·키 순서가 정규화될 수 있습니다. 기존 항목은 값/id 기준으로 보존되고, 주변 서식은
  바이트 단위로 보존되지 않습니다. diff를 검토하세요.
- `wom-kit/docs/releases/v0.3.173.md`를 보세요.

## From `v0.3.171` To `v0.3.172`

두 가지 검증-정직성(verification-honesty) 수정입니다. 둘 다 추가적(additive)이며
마이그레이션이 필요 없고, 모든 기본 경로는 v0.3.171과 바이트 단위로 동일합니다.

운영자에게 보이는 변경:

- **`object-storage-upload`에 새 `--multipart-part-size <BYTES>`와 `--allow-tiny-parts`.**
  기본 part 크기(64 MiB)는 그대로입니다. 오버라이드는 `[4096, 64 MiB]` 범위이고, 기본값
  미만이면 `--allow-tiny-parts`가 필요합니다. 낮춘 `--multipart-threshold`와 함께 쓰면
  작은 객체에도 멀티파트를 강제해 라이브 R2 멀티파트를 증명할 수 있습니다. 파일을 읽어
  분할하는 방식만 바뀌며, 전체 객체 사전 해시·HEAD-after 전체 객체 검증·orphan 정리·leak
  게이트는 그대로입니다. 실제 R2는 마지막 조각을 제외하고 5 MiB 미만 멀티파트 part를
  거부하므로 작은 part 크기는 라이브 검증용 보조 수단입니다 — 라이브에서의 작은-part 거부는
  업로드 거부(failed 상태)이지 조용한 무결성 우회가 아닙니다. 플래그를 넘기지 않으면 변화
  없음.
- **추가 receipt 필드.** object-storage 업로드 실행 receipt에
  `effective_multipart_part_size_bytes`가 추가됩니다. 스키마는 비파괴적입니다
  (`additionalProperties:false` 없음, `required` 아님). 기존 receipt와 소비자에 영향
  없음.
- **strip-bom dry-run 패리티.** `remint-reconcile`과 `retire-draft-reconcile`의
  `--dry-run`에서 `--strip-bom`은 이제 `--approve` 실행이 기록하는 것과 동일한 strip
  의도 메타데이터(`bom_stripped`, `bom_strip_note`)를 미리 보여줍니다. 분류에는 전혀
  영향이 없는 no-op이라 `--strip-bom` 유무와 무관하게 `drift_class`와 내용-변경 ack
  요건이 동일하며, 실제 `content_change`가 `format_drift`로 세탁되지 않습니다.
- `wom-kit/docs/releases/v0.3.172.md`를 보세요.

## From `v0.3.170` To `v0.3.171`

이 release는 `object-storage-adopt-existing`에 선택형 플래그 `--key-map` 하나를
추가합니다. 추가적(additive)이며 adopt 전용입니다. 기본 경로(--key-map 없음)는
v0.3.170과 바이트 단위로 동일하고, `object-storage-upload`는 바뀌지 않습니다.
마이그레이션은 필요 없습니다.

운영자에게 보이는 변경:

- **`object-storage-adopt-existing`에 새 `--key-map <file>`.** 객체별로 이미
  존재하는 정확한 원격 키를 WOM에 직접 넘깁니다. JSONL, 한 줄에 한 객체:
  `{"sha256":"<64hex>","remote_key":"<key>"}`. 매핑된 객체는 그 값이 그대로 결정
  키가 되므로 해당 객체에 대해 `--key-strategy`/`--key-prefix`/
  `--key-append-extension`는 무시됩니다. 콘텐츠 주소 템플릿이 복원하지 못하는
  객체별 파일 확장자(매니페스트 logical_key에 확장자가 없는 prehashed-ledger
  경우)에 저장된 객체를 채택할 때 사용하세요. 매핑 항목이 없는 객체는 보고되며
  채택되지 않습니다.
- **안전성은 그대로이며 더 강해집니다.** 크기는 항상 매니페스트에서 가져오고 map에서
  가져오지 않습니다. 매핑된 키가 404거나 크기가 다르면 조용한 스킵 대신
  재업로드합니다. 각 키는 digest 바인딩(객체 sha256이 경로 세그먼트 또는 파일명
  stem)을 통과하고 leak 가드를 통과해야 합니다. 잘못되었거나 모호한 map은 전체 실행이
  치명적으로 실패하며 아무것도 채택하지 않습니다. 신뢰할 수 있는 객체별 업로드 기록에서
  기계적으로 생성하지 않은 map이라면 `--content-hash-verify`를 추가하세요 — 크기는
  같지만 바이트가 다른 객체에 대한 유일한 암호학적 증명입니다.
- **사용하지 않으면 변화 없음.** `--key-map` 없이는 adopt가 v0.3.170과 정확히 동일하게
  동작합니다. `wom-kit/docs/releases/v0.3.171.md`와 runbook
  `wom-kit/docs/object-storage-adopt-existing-key-map-runbook.md`를 보세요.

## From `v0.3.169` To `v0.3.170`

이 release는 runtime AI 운영자 규율 규범을 추가합니다. 문서 전용이며
추가적(additive)입니다. 명령·스키마·receipt·archive 변경이 없고, 새로 WOM이
강제하는 검사도 없습니다. 마이그레이션은 필요 없습니다.

운영자에게 보이는 변경:

- **runtime 표면에 새 `AI-Operator Discipline` 섹션.** 세 `AGENTS.md`
  템플릿(personal/company/family), runtime `SKILL.md`,
  `wom-ai-runtime-skill-plugin-layer.md`에 운영자 AI가 지키는 세 가지 행동 규범을
  담았습니다. 사용자가 실제로 접한 출처를 기록하고 "더 권위 있는"/원본으로 조용히
  바꾸지 말 것, 어떤 작업을 불가능하다고 선언하거나 낮춰 처리하기 전에 설치·사용
  가능한 도구를 먼저 열거할 것, 이미 설정·승인된 상태를 다시 묻지 말고 이어받을 것.
  옛 `AGENTS.md`를 실제 archive에 복사해 두었다면 새 섹션을 추가해도 되지만, 하지
  않아도 아무것도 깨지지 않습니다. 명령 동작은 바뀌지 않습니다.
- **`text-provenance-hierarchy.md`에 새 source-substitution 축.** `## 7.
  Encountered-Source Fidelity` 하위 절이 두 provenance 축(기존 derivation-tool
  축과 새 source-substitution 축)을 명시합니다. 문서 전용이며, provenance 모델에
  새 필수 필드는 없습니다.
- **강제가 아니라 지침.** WOM은 provenance fidelity, 도구 열거, 상태 이어받기를
  검증·강제하지 않으며, 이 release는 그런 검사를 추가하지 않습니다.
  `ai-response-concept-guide`의 topic enum은 그대로입니다.
  `wom-kit/docs/releases/v0.3.170.md`를 보세요.

## From `v0.3.168` To `v0.3.169`

이 release는 read-only 운영자 피드백 전달 ledger와 승인형 일괄 mark-delivered
명령을 추가합니다. 모두 추가적(additive)이며 마이그레이션은 필요 없습니다.

운영자에게 보이는 변경:

- **archive 마이그레이션 없음, 기존 record 불변, 해시 변경 없음.**
  `operator-feedback.schema.json` record에 선택적(optional) 문자열 속성
  `delivered_at`, `acknowledged_at`가 추가됩니다(`required`에는 넣지 않음). 기존
  `ops/feedback/*.yml` record는 그대로 검증·읽힙니다. 일괄 receipt용으로 새
  `operator-feedback-delivery-receipt.schema.json`이 함께 배포됩니다.
- **새 read-only `archive operator-feedback-ledger`**(별칭 `feedback-ledger`,
  `feedback-board`): `ops/feedback/*.yml`에서 전달 상태를 상태별 카운트 + 대기(draft)
  목록 + 최신 전달 경계로 집계합니다. 아무것도 쓰지 않고, 피드백 본문을 읽지 않으며,
  피드백 ref·제목·경로·토큰·비밀 값을 노출하지 않습니다. 손상된 record는 `unreadable`로
  세어 건너뜁니다. 옛 `--status delivered` 경로로 delivered된 record는 `delivered_at`가
  없어 경계가 `updated_at`로 대체됩니다.
- **새 승인형 `archive operator-feedback-mark-delivered`**(별칭
  `feedback-mark-delivered`): `--dry-run`은 draft→delivered 전이를 미리 보고 아무것도
  쓰지 않습니다. `--approve --reviewed-by <actor>`는 대기 중인 모든 `draft` record를
  delivered로 표시하고 `delivered_at`를 찍으며 receipt 하나를 씁니다. `--only <id>`는
  단일 record만 표시합니다. `draft` record만 건드리고, 멱등하며, 손상된 record는 다른
  record를 반쯤 쓰지 않고 건너뜁니다.
- **정직 경계(과장 없음).** 이는 메타데이터 수명주기일 뿐입니다.
  `external_submission_performed`는 `false`로 유지되며, `delivered`는 운영자가 직접
  표시했다는 뜻이지 외부로 제출되었거나 사람이 수신했다는 증명이 아닙니다.
  `wom-kit/docs/releases/v0.3.169.md` 참고.

## From `v0.3.167` To `v0.3.168`

이 release는 draft 시점 identity 위생, attributed mint affirmation 플래그, 소비된
draft를 retire하도록 안내하는 포인터, base `continues` edge type, draft 시점
`--kind` 검증을 추가합니다. 모두 추가적(additive)이며 마이그레이션은 필요 없습니다.

운영자에게 보이는 변경:

- **archive 마이그레이션 없음, 기존 id 불변, 해시 변경 없음.** 어떤 기존 canonical
  id도 이름이 바뀌거나 정규화되지 않습니다. mint receipt에 새 추가 필드 `affirmations`
  배열(`item_id`, `affirmed_by`, `affirmed_at`)이 생기고, mint 결과에 `next_safe_actions`
  문자열 목록이 생깁니다. `mint-receipt.schema.json`은 `additionalProperties: false`를
  쓰지 않으므로 기존 receipt·manifest·zet은 그대로 수용됩니다.
- **draft-id 위생(forward-only).** ASCII 영숫자가 없는 제목(제목 없음 또는 한글뿐인
  제목)의 NEW draft는 이제 옛 `zet_<ts>_draft` 대신 `zet_<ts>_note` id를 받습니다.
  새로 만드는 draft에만 영향을 주며 기존 id는 그대로이고 mint에는 id 재작성 경로가
  추가되지 않습니다.
- **`mint-zet`의 attributed `--affirm`.** `mint-zet --approve --reviewed-by <actor>
  --affirm <item_id>`(반복 가능; `one_clear_purpose`, `sensitive_content_reviewed`만
  허용)는 두 human-review 체크리스트 항목을 raw `mint.checklist` YAML 편집 대신
  검토자 귀속·감사 가능한 CLI 행위로 충족하며 receipt의 `affirmations` 블록에
  기록됩니다. `--reviewed-by` 없으면 무효(hard error), machine-enforced 항목은
  덮어쓸 수 없고, 명시적 YAML `false`도 뒤집지 않습니다. **정직한 잔여 위험:** 기존
  `--reviewed-by` 게이트와 마찬가지로 `--affirm`은 검토자 문자열이 실제 사람인지
  증명하지 못합니다. 새로운 self-affirm 구멍을 만들지 않으며, 보장하는 것은 귀속과
  감사 가능성이지 문자열 검사가 아닙니다.
- **retire 포인터, 자동 삭제 없음.** 성공한 mint 결과는 이제 `next_safe_actions`로
  `archive retire-draft --zettel-id <id> --dry-run`을 안내합니다(text 모드에서 출력).
  mint은 여전히 소비된 inbox draft를 삭제하지 않으며 retire는 자체 승인 게이트 단계로
  남습니다.
- **base `continues` edge type.** base `zettel-kasten/types.yml`(KIT과 fixture)이 이제
  같은 흐름의 연속을 위한 `continues` link type를 정의합니다. **제한:** base 전용이며
  `migrate link-types-v0.3`의 recommended 집합에 포함되지 않으므로, 자기 `types.yml`을
  vendoring한 archive는 항목을 수동으로 추가합니다(추가적).
- **draft 시점 `--kind` 검증 + `--list-kinds`.** `archive create-draft`는 이제 archive의
  `zettel-rules.yml`에 없는 `--kind`에 대해 경고(차단 아님)하고 유효한 kind 목록을
  보여줍니다. `archive create-draft --list-kinds`는 이를 read-only로 나열하며 아무것도
  쓰지 않습니다. `wom-kit/docs/releases/v0.3.168.md` 참고.

## From `v0.3.166` To `v0.3.167`

이 release는 정직한 reconcile 계열을 확장합니다: 스냅샷이 함께 드리프트한 경우에도
안전하게 분류하는 기능, retire receipt용 형제 명령 `retire-draft-reconcile`, opt-in
`--strip-bom`을 추가하고, object-storage 실행 결과의 `live_execution_allowed_now`
필드를 바로잡으며, 경계가 정해진 `--multipart-threshold` 테스트 보조 옵션을
추가합니다. 모두 추가적(additive)이며 마이그레이션은 필요 없습니다.

운영자에게 보이는 변경:

- archive 마이그레이션이나 해시 변경은 없습니다. mint reconcile audit receipt의 두
  새 필드(`classification_basis`, `bom_stripped`), retire receipt의 새 `reconcile`
  provenance 블록, 새 `retire-draft-reconcile-receipt.schema.json`, object-storage
  업로드 receipt의 두 새 필드(`effective_multipart_threshold_bytes`, `part_count`)는
  모두 추가적입니다. 어떤 스키마도 `additionalProperties: false`를 쓰지 않으므로 기존
  receipt·manifest·zet은 그대로 수용됩니다.
- `remint-reconcile`은 이제 draft 스냅샷 자체가 드리프트한 경우에도 `format_drift`를
  인식하지만, 두 개의 독립 증명과 전체 필드 frontmatter 검사(모든 content 필드를
  재구성 비교 + mint receipt의 `id`/`title` 대조) 뒤에만 허용합니다 — 따라서 어떤
  content 필드(`visibility`, `kind`, `facets` 등)를 수정하거나 내용이 변조된 스냅샷은
  절대 `format_drift`의 앵커가 될 수 없습니다. 불확실하면 여전히 `content_change`로
  분류하고 `--content-changed-ack`을 요구합니다.
- 새 CLI 전용 명령 `archive retire-draft-reconcile --dry-run|--approve`는
  retire-draft receipt의 네 ref를 reconcile하며, doctor는 이제
  `mint_retired_draft_sha_mismatch` 결과를 `suggested_command`로 이 명령에
  안내합니다. 두 reconcile 명령의 opt-in `--strip-bom`은 선행 UTF-8 BOM만 제거하고
  내용 변경 ack 게이트를 절대 우회하지 않습니다.
  `wom-kit/docs/releases/v0.3.167.md` 참고.

## From `v0.3.164` To `v0.3.165`

이 release는 운영자용 runtime 표면에 normative Plain-Language for Humans 규약을
추가하고, read-only `ai-response-concept-guide`에 git/infrastructure 용어 번역
레이어를 추가합니다.

운영자에게 보이는 변경:

- archive 마이그레이션이나 해시 변경은 없습니다. 추가된 것은 지침 산문
  (`AGENTS.md` 템플릿, runtime skill, plugin-layer 문서)과
  `ai-response-concept-guide`의 새 read-only `--topic git_infra_terms` 세트뿐이며,
  기존 receipt·manifest·zet은 영향을 받지 않습니다.
- 강제가 아니라 지침입니다. 이 규약은 운영자 AI에게 git/infrastructure/WOM 내부
  용어를 사람에게는 일상어로 옮기고 정확한 용어는 괄호나 로그에만 남기라고
  안내합니다. WOM은 plain-language 출력을 검증하거나 강제하지 않으며, 읽는 AI가
  적용합니다. machine·JSON·receipt 출력은 그대로 정확하게 유지됩니다.
- `archive ai-response-concept-guide <archive-root> --topic git_infra_terms
  --locale en-US --dry-run --format json`으로 일상어 표현을 조회하세요. 아무것도
  쓰지 않고, provider를 호출하지 않으며, local path나 secret 값을 출력하지
  않습니다. `wom-kit/docs/releases/v0.3.165.md` 참고.

## From `v0.3.163` To `v0.3.164`

이 release는 object-storage 업로드 어댑터(WOM #11)의 Stage 2, 즉 실제 AWS SigV4
R2/S3 호환 업로드 전송 계층을 추가합니다. 이제 WOM은 승인된 object-storage
업로드에 대해 네트워크 CAPABLE하지만, capable이 곧 자동 실행을 뜻하지는 않습니다.

운영자에게 보이는 변경:

- archive 마이그레이션이나 해시 변경은 없습니다. 업로드 명령을 직접 실행하기
  전까지 기존 receipt와 manifest는 영향을 받지 않습니다.
- 여전히 의존성 추가는 없습니다. 전송 계층은 기존 `urllib` seam 위에
  `hashlib`/`hmac`/`base64`로 손수 구현했으며 `wom-kit/pyproject.toml`은 계속
  PyYAML 전용입니다.
- 라이브 `--approve` 업로드는 다음을 모두 요구합니다: env 전용 자격 증명 ref
  (`--access-key-id-ref env:...`, `--secret-access-key-ref env:...`), 안전한
  `--reviewed-by`, 확인 가능한 비밀 아닌 `--endpoint-host`와 `--bucket`
  (cloudflare-r2는 region 기본값 `auto`), 그리고 충족된 tiered tiny-first 게이트.
  대량 first-live 실행은 작은 객체 하나를 먼저 증명하기 전까지 `tiered_gate_unmet`
  로 거부됩니다. 하드 누적 PUT 상한이 실행 전체의 비용을 제한합니다.
- 라이브를 tiny-first로 검증하세요. 작은 객체 하나를 끝까지 업로드하고 실행
  receipt·manifest `wom_uploaded` 전이·원격 after-HEAD를 손으로 확인한 뒤 tier를
  올리세요. 릴리스 노트에 정확한 runbook이 있습니다. 첫 라이브 객체가 확인되기
  전까지 receipt와 릴리스 노트는 `unproven_against_live_provider: true`를
  유지합니다. `wom-kit/docs/releases/v0.3.164.md` 참고.

## From `v0.3.162` To `v0.3.163`

이 release는 object-storage 업로드 어댑터(WOM #11)의 Stage 1을 세 개의 승인 게이트
명령으로 추가하고, 공유 object-storage manifest 기록기를 안전하게 강화합니다.

운영자에게 보이는 변경:

- 새 명령만 추가되며 자동으로 실행되는 것은 없습니다. `archive
  object-storage-upload-plan --dry-run`과 `archive object-storage-upload-verify
  --dry-run`은 읽기 전용이며 아무것도 쓰지 않습니다. `archive
  object-storage-upload`는 `--dry-run`/`--approve` 중 정확히 하나가 필요하고,
  `--approve`에는 안전한 `--reviewed-by`가 필요합니다.
- 어댑터는 아직 업로드할 수 없습니다. 이것은 단계적 롤아웃의 Stage 1입니다. 라이브
  전송 계층이 포함되어 있지 않으므로 `archive object-storage-upload --approve`는
  자격 증명이나 바이트를 읽기 전에 `live_transport_not_implemented`로 닫힌 상태로
  실패합니다. 프로바이더에 도달하는 환경 변수나 플래그는 없으며, 라이브 전송에는
  Stage 2 코드 변경이 필요합니다.
- archive 마이그레이션이나 해시 변경은 없습니다. manifest 기록 강화는 추가적
  변경입니다. 공유 object-storage manifest 기록기는 이제 manifest 잠금을 획득하고
  원자적으로(temp+fsync+os.replace) 기록하므로 기존
  `object-storage-upload-evidence` 명령도 함께 보호됩니다. 업로드 명령을 직접
  실행하기 전까지 기존 receipt와 manifest는 영향을 받지 않습니다.
- `wom-kit/schemas/object-storage-upload-receipt.schema.json`, object-storage
  실행 receipt용 doctor 점검, 읽기 전용 MCP 도구 `object_storage_upload_plan`과
  `object_storage_upload_verify`가 추가되었습니다.
  `wom-kit/docs/releases/v0.3.163.md` 참고.

## From `v0.3.161` To `v0.3.162`

이 release는 `archive remint-reconcile`를 추가합니다. canonical zet의 바이트가
디스크에서 드리프트한 뒤(CRLF/BOM 재체크아웃 또는 사람이 내용을 수정한 경우)
mint receipt에 기록된 sha256 값을 정직하게 재발급하는 명령입니다. 또한 추가적인
BOM/개행 파싱 관용과 doctor/retire의 reconcile 경로 안내가 들어갑니다.

운영자에게 보이는 변경:

- 새 명령뿐이며 자동으로 실행되는 것은 없습니다. `archive remint-reconcile
  <archive-root> (--zettel-id <id> | --path <rel>) [--dry-run | --approve]
  [--reviewed-by <actor>] [--content-changed-ack]`는 canonical zet의 드리프트를
  `format_drift`(개행/BOM만) 또는 `content_change`로 분류하고, 항상 디스크의
  현재 내용을 보여주며, 승인하려면 `--reviewed-by`가 필요합니다(`content_change`는
  `--content-changed-ack`도 필요). `wom-kit/docs/mint-receipt-reconcile.md` 참고.
- archive migration도 없고 해시 변경도 없습니다. BOM/개행 관용은 파싱/읽기
  헬퍼에만 적용되고, sha256은 여전히 원시 바이트를 읽으므로 BOM과 개행 드리프트는
  sha 불일치로 그대로 보입니다. 기존 receipt와 canonical 파일은
  `remint-reconcile`를 직접 실행하기 전까지 영향을 받지 않습니다.
- STRICT 게이트 참고(새로운 실패가 아니라 표면화): mint receipt로부터 이미
  개행/BOM으로 드리프트한 canonical zet는 이전에도 `mint_receipt_sha_mismatch`로
  `doctor`/`--strict`를 실패시켰습니다. v0.3.162부터 그 경우는
  `remint-reconcile --dry-run` 제안 명령을 함께 안내하고, canonical zet의 UTF-8
  BOM은 `zettel_has_bom` WARN을 추가하며, 이미 한 번 reconcile한 receipt가 다시
  개행/BOM으로만 드리프트하면 별도 코드
  `mint_receipt_target_byte_drift_suspected_format` ERROR로 보고합니다. 모두
  ERROR로 유지되며, edge-receipt 진화 경로는 변경되지 않고 어떤 게이트도
  완화되지 않았습니다.
- 새 mint는 canonical 쓰기를 LF 개행으로 고정해 즉각적인 재드리프트를 막습니다.
  `wom-kit/schemas/mint-reconcile-receipt.schema.json`와 `mint-receipt.schema.json`의
  `reconcile` 객체 property를 추가했습니다(required 아님, 기존 receipt는 그대로
  검증 통과). `wom-kit/docs/releases/v0.3.162.md` 참고.

## From `v0.3.159` To `v0.3.160`

이 release는 AI intake protocol(파일을 물리적으로 복사하기 전의
source-intake 게이트), doctor의 objet 저장소 git 가드 2종, `/objets/`
gitignore 안전 기본값, D2 intake 배치 규칙, operator-feedback 발견성 및
schema 파일을 추가합니다.

운영자에게 보이는 변경:

- STRICT 게이트 영향(의도된 결정, 두 단계): 첫째, `/objets/`가 권장
  `.gitignore` 기본값에 추가되었기 때문에 v0.3.160 이전에 만든 모든
  아카이브는 — `objets/` 폴더가 없어도 — 기존 경고
  `local_profile_gitignore_incomplete`가 새로 발생하며, 이것만으로도
  `archive validate`(기본적으로 warning에서 실패)와 `archive doctor
  --strict`가 실패합니다. `archive repair-gitignore <archive-root>
  --approve --reviewed-by <actor>`를 한 번 실행하면 해소됩니다. 둘째, 새
  doctor 경고 `archive_objets_layout_noncanonical`(아카이브 루트 바로 아래
  raw `objets/` 폴더 존재)와 `workspace_objet_store_git_exposure`(objet
  바이트 저장소가 상위 git working tree에 tracking될 수 있음)는 in-root
  `objets/` 폴더에 원본을 보관하거나 저장소가 노출된 아카이브에서 같은
  게이트와 `archive runtime-context --strict`를 실패시킬 수 있습니다 —
  `wom-kit/docs/artifact-hygiene.md` 5절의 migration 가이드를 완료할 때까지.
  layout 경고는 폴더를 gitignore해도 의도적으로 꺼지지 않습니다: ignore된
  원본은 git push 백업 경로에서 조용히 빠지기 때문에, 폴더를 비울 때까지
  경고가 유지됩니다.
- gitignore 변경은 추가 라인뿐입니다: 앵커된 `/objets/`(staged 트리 내부의
  중첩 `objets/` 폴더에는 영향 없음)가 권장 기본값에 추가되며, 기존
  아카이브는 `archive repair-gitignore <archive-root> --approve
  --reviewed-by <actor>`로 반영합니다(반영 전까지는 위의 완전성 경고가
  strict 게이트를 실패시킵니다). 정직한 주의 2가지: 이미 커밋된
  파일은 untrack되지 않고(필요 시 사람 검토 후 `git rm --cached`), 형제
  `<root-name>-objets` 저장소는 `objets/` 패턴과 일치하지 않으므로 exposure
  경고가 실제 폴더 이름을 안내합니다 — 저장소가 repository 루트의 직접
  하위 폴더면 앵커된 `/<name>/` 라인을, 더 깊이 있으면(앵커된 루트 라인은
  중첩 경로와 일치하지 않으므로) 앵커 없는 `<name>/` 라인을 안내합니다.
- JSON 소비자에게는 추가 필드만 보입니다: `staging_convention`에
  `matched_shape`, `recommended_in_archive_shape`,
  `in_archive_staging_supports_capture`가 추가되고,
  `recommended_first_commands`에 operator-feedback-plan 항목이 뒤에
  추가되며, `ai_runtime_order`에 step 7 `plan_operator_feedback`이
  추가됩니다. `available_safe_actions`에는 `run operator-feedback-plan
  dry-run`이 다른 read-only dry-run 액션들 옆, 리스트 중간(8개 중 3번째)에
  삽입됩니다. 전체 리스트나 위치를 고정(pin)한 소비자는 새 항목을 반영해야
  합니다.
- in-archive staging이 canonical이 됩니다:
  `<archive-root>/staging/incoming/` 아래 폴더는 이제 project-intake-plan과
  project-intake-unpack-queue에서 `follows_staging_convention: true`로
  보고되고, staged 폴더를 받지 않는 project-intake-staging-guide는 추가
  필드 `recommended_in_archive_shape` /
  `in_archive_staging_supports_capture`로 같은 in-archive 형태를 capture
  intake용으로 권장합니다. 형제
  `zettel-kasten-<profile_slug>-objets\intake\<project_slug>` 형태는 대량
  외부 원본용으로 계속 허용됩니다.
- 새 schema 파일 `wom-kit/schemas/operator-feedback.schema.json`과
  `wom-kit/schemas/operator-feedback-receipt.schema.json`은 변경 없는 기존
  record/receipt 형태를 기술하며, schema-id 문자열은 그대로입니다
  (`wom-kit/operator-feedback/v0.1`,
  `wom-kit/operator-feedback-receipt/v0.1`). record migration은 없습니다.
- 아카이브 migration은 필요하지 않습니다.
  `wom-kit/docs/releases/v0.3.160.md`와
  `wom-kit/docs/artifact-hygiene.md`를 참고하세요.

## From `v0.3.158` To `v0.3.159`

이 release는 짝지은(paired) transcript intake(승인 한 번으로 staged 원본과
이미 추출된 transcript를 함께 처리)와 BOM 인식 derive-text 인코딩을
추가합니다.

운영자에게 보이는 변경:

- 추가(ADDITIVE) manifest 필드 + 새 action 문자열: selection item은
  `derived_text` 하위 객체(`staged_text_path`, RAW 바이트에 대한
  `approved_text_sha256`, `derivation_kind`, `tool_name`, `tool_version`,
  `review_status`, 선택적 model/confidence/language/born_digital)를 가질 수
  있습니다. 짝지은 manifest는 반드시 `action:
  local_objet_capture_with_derived_text_approved`와 `schema:
  wom-kit/b4-selection/v0.3`을 씁니다. v0.3.158 이하 kit은 짝지은 manifest를
  `selection_action_invalid`로 거부합니다 — 의도된 fail-closed입니다.
  메커니즘이 중요합니다: 예전 envelope 검증기는 `schema` 필드를 무시하고
  (write-only였음) 알 수 없는 item key도 무시하므로, 예전 kit이 원본만
  캡처하고 승인된 derived 절반을 조용히 버리는 대신 거부하게 만드는 유일한
  지렛대가 ACTION 문자열입니다. v0.3.159부터 `schema` 필드를 검증합니다
  (`selection_schema_invalid`): 일반 manifest는 생성기가 항상 써 온 v0.2
  schema를 요구하고, 손으로 만든 `schema` 없는 manifest는 필드를 추가해야
  합니다.
- utf-8-sig 해시 정체성 변경(추가적이지 않음): 이 release 전에는 UTF-8 BOM이
  검증을 통과했고 raw 바이트가 BOM을 포함한 채 저장되었습니다. 이제 저장 전에
  BOM을 제거하므로, 같은 utf-8-sig 입력이 업그레이드 전 캡처와 다른
  `text_sha256`/`derived_text_id`를 만들고, 업그레이드 후 같은 입력을 다시
  실행하면 `skip_already_present` 대신 두 번째 record가 생깁니다. BOM 없는
  UTF-8 입력은 영향이 없습니다(저장 바이트 == raw 바이트).
- receipt schema 상향: `wom-kit/objet-capture-receipt/v0.2` ->
  `wom-kit/objet-capture-receipt/v0.3` (item이 `derived_text` 하위 결과를
  가질 수 있고, item/run 단위의 추가 `status_class`, 짝지은 실행에서 derived
  요약 카운터), 그리고 `wom-kit/derived-text-capture-receipt/v0.1` ->
  `wom-kit/derived-text-capture-receipt/v0.2` (`source_text_encoding`,
  `source_text_sha256`, 짝지은 등록의 `paired_with`). derived-text RECORD
  schema는 `wom-kit/derived-text-record/v0.1` 그대로이고 선택적 provenance
  필드만 추가됩니다.
- 새 blocker: `approved_text_content_mismatch`, `unsafe_staged_text_path`,
  `blocked_by_original`, `derived_text_registration_failed`,
  `selection_schema_invalid`, `text_file_bom_encoding_unsupported`,
  `text_file_bom_encoding_undecodable`, `text_file_contains_nul`,
  `text_file_too_large`. `text_file_not_utf8`은 이제 BOM 없는 비 UTF-8
  입력에만 쓰이고 정적 hint가 붙습니다. 짝지은 manifest의 메타데이터 검증은
  기존 derive-text `*_invalid` 어휘(`derivation_kind_invalid`,
  `review_status_invalid`, `tool_name_invalid`, `tool_version_invalid`,
  `confidence_invalid`, `language_invalid`, `born_digital_invalid`)를
  재사용하고, 문자열이 아닌 선택적 model 필드에 대해 `model_name_invalid` /
  `model_version_invalid`를 추가합니다.
- archive migration은 필요 없습니다. `wom-kit/docs/releases/v0.3.159.md`와
  `wom-kit/docs/derived-text.md`의 Encoding 절을 보세요.

## From `v0.3.157` To `v0.3.158`

이 release는 실제(비 sandbox) archive의 local objet capture를 소유자 승인으로 여는 기능을 추가합니다.

운영자에게 보이는 변경:

- 새 CLI 명령 `archive objet-capture-enable <archive-root>` (alias
  `archive capture-enable`): `--dry-run`은 read-only 자격 보고이고,
  `--approve --reviewed-by <actor>`는 `receipts/capture-enablement/` 아래
  영수증(receipt)을 먼저 쓰고 단일 `ops/capture-enablement.yml` 동의 record를
  나중에 씁니다. `--revoke --approve`는 철회하고, never-touch 이름 패턴에
  걸리는 root는 `--acknowledge-never-touch-name`이 필요하며, 철회된 record
  위에 다시 승인하려면 `--reenable`이 필요합니다. 이 명령은 CLI 전용이고
  MCP로는 노출되지 않습니다.
- JSON 필드 이름은 바뀌지 않습니다. `objet-capture` refusal에
  `enablement_state` 필드 하나가 추가되고, `blocked_by` id는 그대로입니다.
- `objet-capture` refusal hint 두 개의 문구가 바뀌었습니다. hint는 정적
  문자열이지 파싱 계약이 아닙니다. `"separate planned flow"` 부분 문자열을
  검사하던 downstream 사본은 같은 갱신이 필요합니다.
- per-item never-touch 판정은 유효하게 enable된 root에서만 바뀝니다:
  패턴을 enable된 root 아래 archive-relative 구성요소에만 적용합니다.
  enable되지 않은 root(모든 sandbox-marked archive 포함)는 이전과 완전히
  같게 동작합니다.
- archive migration은 필요 없습니다. `wom-kit/docs/capture-enablement.md`와
  `wom-kit/docs/releases/v0.3.158.md`를 보세요.

## From `v0.3.3` To `v0.3.4`

This release adds the first derived text capture layer.

What changed:

- added CLI `archive derive-text capture <archive-root> --text-file <file> --source-object-id <object-id> --derivation-kind <kind> --tool-name <name> --tool-version <version> --review-status <status> --dry-run|--approve`,
- added `objects/manifests/derived-text.jsonl` for provenance-aware derived text records,
- approved capture stores UTF-8 text bodies under `objects/derived-text/sha256/` and writes `receipts/derived-text-capture/*.json`,
- `archive index` ingests derived text records and `archive search` can return `type: derived_text`,
- doctor validates derived text JSONL, source object references, vocabulary, and stored text hashes when present,
- updated version metadata to `0.3.4`.

The source object must already exist in `objects/manifests/files.jsonl`.
`derive-text capture` does not run OCR, ASR, parsers, LLM vision, provider APIs,
drafting, or minting. Rebuild the generated search index after approved derived
text capture:

```text
archive index <archive-root>
```

## From `v0.3.2` To `v0.3.3`

This is a compatible field-feedback hardening release.

What changed:

- CLI output is resilient to console encodings that cannot represent every character,
- doctor and validate now fail more clearly on unquoted YAML timestamp frontmatter,
- `validate --strict` is accepted for parity with doctor,
- `staged-cleanup-check` exits `0` only when `safe_to_cleanup` is true; unsafe cleanup reports exit `1`,
- `view-zets` can match scalar facet filters against list-valued zettel facets after re-indexing,
- list-valued view filter inputs block instead of being guessed or broadened,
- objet-capture source-intake plan SHA binding is regression-tested with a real `source-intake --dry-run` producer plan through dry-run and approve,
- updated version metadata to `0.3.3`.

Archives authored under v0.3.2 rules need no schema migration. If you rely on
facet views, rebuild the disposable search index once:

```text
archive index <archive-root>
```

If you automate staged-folder cleanup checks, treat the new nonzero exit on
unsafe reports as expected fail-closed behavior and read the JSON
`safe_to_cleanup` field before any manual cleanup decision.

This release does not touch live archives, providers, ZET transport, MCP write
tools, cleanup targets, or the v0.3.1 frontmatter schema itself.

## From `v0.3.1` To `v0.3.2`

This release ships the frontmatter v0.3 compatibility migration, the local objet
capture spine, and consistent redacted-zettel suppression.

What changed:

- added approval-gated CLI `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run|--approve --format json`,
- added approval-gated CLI `archive objet-capture <archive-root> --selection <manifest> --dry-run|--approve --reviewed-by <actor>` writing content-addressed objets, manifest records, and capture receipts into sandbox-marked archives only,
- added report-only CLI `archive staged-cleanup-check <archive-root> --staged <folder> --dry-run`,
- added read-only CLI `archive related-zets` (typed-edge backlinks) and `archive view-zets` (facet view execution),
- indexed typed edges and zettel facets in the disposable search index,
- enforced redacted-zettel content suppression across search, the index, list-zettels, read-zettel, block-header previews, projection previews, related-zets, and view-zets,
- added the report-only artifact hygiene checker and file-lifecycle baseline,
- updated version metadata to `0.3.2`.

Archives authored under v0.3.1 rules need no frontmatter changes; the v0.3.1
schema is unchanged. Archives authored from older v0.2-draft frontmatter rules
should run:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before strict v0.3 validation, and apply only after reviewing the plan on a
backup or sandbox copy.

Rebuild the local search index once to pick up edges and facets:

```text
archive index <archive-root>
```

The objet-capture write path refuses archives without an explicit sandbox marker
(`.wom-sandbox` file or top-level `environment: sandbox`). This release does not
touch live archives, providers, ZET transport, MCP write tools, or the v0.3.1
schema itself.

## From `v0.3.0` To `v0.3.1`

This is a compatible read-only route-preview release.

What changed:

- added CLI `archive shared-update-route-preview <archive-root> --record <path> --dry-run --format json`,
- added a local service that reuses `zet_shared_update_record_review_preview` before returning any route pointer,
- added route pointer fields for `delegate`, `attest`, `anchor`, and `none`,
- added explicit `related_shared_update_review_required_flags` when the route points toward `shared-update-attestation-review`,
- hardened route selection so free-form or hostile `proposed_action` metadata is not echoed,
- added `wom-kit/docs/shared-update-route-preview.ko.md`,
- updated version metadata to `0.3.1`.

The route-preview command itself requires no provider, transport, or
shared-update record migration. Archives authored from older v0.2-draft
frontmatter rules should run:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before strict v0.3 validation.

The new command is read-only and dry-run only. It writes no files and only points a human toward an existing canonical command surface. It does not expose an MCP write/apply/approve tool and does not create real ZET transport, keys, feed updates, trust/import/acceptance, attestations, signatures, anchors, public proofs, provider sync, projection writes, queues/workers, wallet/key custody, payment/staking/consensus/blockchain, tokens, model training, backpropagation, or full-auto behavior.

## From `v0.2.60` To `v0.3.0`

This is a compatible first v0.3.0 write-boundary release.

What changed:

- added CLI `archive shared-update-attestation-review <archive-root> --record <path> --decision <attest|needs_more_review|reject> --reviewed-by <actor> --approve --format json`,
- added a local service that reuses `zet_shared_update_record_review_preview` before writing,
- added deterministic receiver-side review record and receipt paths,
- added replay/overwrite refusal and receipt-failure rollback,
- added `wom-kit/docs/shared-update-attestation-review-write.md`,
- updated version metadata to `0.3.0`.

The shared-update attestation/review command itself requires no provider,
transport, or shared-update record migration. Archives authored from older
v0.2-draft frontmatter rules should run:

```text
archive migrate <archive-root> --target frontmatter-v0.3 --dry-run
```

before strict v0.3 validation.

The new command writes only a local shared update attestation/review record and matching receipt. It does not expose an MCP write/apply tool and does not create real ZET transport, keys, feed updates, trust/import/acceptance, signatures, anchors, public proofs, provider sync, projection writes, queues/workers, wallet/key custody, payment/staking/consensus/blockchain, tokens, model training, backpropagation, or full-auto behavior.

## From `v0.2.59` To `v0.2.60`

This is a compatible documentation, version, and test checkpoint for the v0.2.x freeze and v0.3.0 entry boundary.

What changed:

- added `wom-kit/docs/v02x-freeze-v03-entry-boundary.md`,
- added the v0.2.60 release note and public-safe work log,
- updated the capability matrix with the v0.2.x freeze, public proof boundary, DID-compatible identity research boundary, and proposed first v0.3.0 write boundary,
- updated version metadata to `0.2.60`.

No private archive migration is required.

This release adds no product CLI command, MCP tool, archive service behavior, or schema change. It records that the proposed v0.3.0 first boundary should be one narrow receiver-side, replay-gated, human-approved, local-first, body-safe write. It does not add real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, feed updates, trust/import/acceptance/anchor mutation, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, queues/workers, DID registry, wallet/key custody, public proof anchoring, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.58` To `v0.2.59`

This is a compatible read-only ZET transport threat model and would-transport planning patch.

What changed:

- added CLI `archive zet-transport-plan <archive-root> --record <path> --method <key-sharing|radio-frequency|mirroring> --dry-run --format json`,
- added MCP `zet_transport_would_plan`,
- added service `zet_transport_would_plan`,
- added `wom-kit/docs/zet-transport-threat-model.md`,
- updated version metadata to `0.2.59`.

No private archive migration is required.

The new command reads one local archive-contained shared update record JSON, reuses the v0.2.56 single-record review preview policy, writes nothing, and returns a planning-only risk/control preview for a future transport method. It does not add real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, shared-update review writes, receiver-side renewal writes, neighbor feed update, recommendation execution, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, queues/workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.57` To `v0.2.58`

This is a compatible read-only shared update review index patch.

What changed:

- added CLI `archive shared-update-record-review-index <archive-root> --records-dir <path> --dry-run --format json`,
- added MCP `zet_shared_update_record_review_index`,
- added `wom-kit/docs/zet-shared-update-record-review-index.md`,
- updated version metadata to `0.2.58`.

No private archive migration is required.

The new command inspects only direct-child local JSON records under an archive-relative directory, reuses the v0.2.56 single-record review policy, writes nothing, and returns a compact deterministic index. It does not add shared-update review writes, shared-update transport, real ZET transport, neighbor feed update, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.56` To `v0.2.57`

This is a compatible capability matrix and README readability patch.

What changed:

- added `wom-kit/docs/capability-matrix.md`,
- shortened the top-level README status summary and linked to the capability matrix,
- restored the missing `v0.2.55` README release-tag entry,
- documented a proposed v0.2.x closing plan and narrow proposed v0.3.0 boundary,
- updated version metadata to `0.2.57`.

No private archive migration is required.

This release adds no archive product CLI, MCP, or service behavior. It does not add provider calls, real ZET transport, shared-update writes, receiver-side renewal writes, RF access, key-sharing registry, mirroring delivery, neighbor feed update, automatic feed renewal, recommendation execution, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.55` To `v0.2.56`

This is a compatible read-only ZET shared update record review preview patch.

What changed:

- added CLI `archive shared-update-record-review <archive-root> --record <path> --dry-run --format json`,
- added MCP `zet_shared_update_record_review_preview`,
- added `wom-kit/docs/zet-shared-update-record-review-preview.md`,
- updated version metadata to `0.2.56`.

No private archive migration is required.

The new command reads only one archive-relative JSON record and writes nothing. It blocks unsafe record paths, body-included records, token/secret-like values, local absolute path leakage, and true mutation/write/transport/provider/trust flags. It does not add shared-update transport, real ZET transport, neighbor feed update, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.54` To `v0.2.55`

This is a compatible ZET shared update record baseline documentation/example patch.

What changed:

- added `wom-kit/docs/zet-shared-update-record-baseline.md`,
- added a sanitized non-executable example at `wom-kit/examples/zet-shared-update-record/shared-update.example.json`,
- updated version metadata to `0.2.55`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not add shared-update transport, real ZET transport, RF access, key-sharing registry, mirroring delivery, neighbor feed update, automatic feed renewal, recommendation execution, trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes or receipts, workers, payments/staking/consensus/blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.53` To `v0.2.54`

This is a compatible main branch protection readiness documentation patch.

What changed:

- added `wom-kit/docs/main-branch-protection-readiness.md`,
- documented a staged path from local release gate to future GitHub Actions, required status checks, and optional review requirements,
- updated version metadata to `0.2.54`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not add GitHub Actions, enable branch protection, change repository settings, call GitHub APIs, call providers, edit GitHub Releases, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.52` To `v0.2.53`

This is a compatible release readiness gate patch.

What changed:

- added `wom-kit/tools/check_release_readiness.py`,
- added tests for expected child checker paths, pass/fail behavior, failure output, current-repository pass behavior, and network-free / release-edit-free gate scope,
- documented the gate at `wom-kit/docs/release-readiness-gate.md`,
- updated version metadata to `0.2.53`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. The gate is local-only and read-only. It runs the public link, Korean product-language, and public privacy hygiene checkers only. It does not rewrite files, fetch external URLs, call GitHub APIs, add GitHub Actions, enable branch protection, run product doctors/tests, call providers, edit GitHub Releases, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## From `v0.2.51` To `v0.2.52`

This is a compatible public privacy hygiene checker patch.

What changed:

- added `wom-kit/tools/check_public_privacy.py`,
- added tests for local user-home paths, token-like strings, private key headers, seed-phrase-like text, private/local endpoint examples, placeholders, and network-free checker scope,
- documented the checker at `wom-kit/docs/public-privacy-hygiene.md`,
- updated version metadata to `0.2.52`.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. The checker is local-only and read-only. It does not rewrite files, fetch external URLs, call providers, inspect private archives, edit GitHub Releases, scan the whole disk, run ZET transport, create trust/import/acceptance/anchor, write attestations/signatures, publish to WordPress, write projection records or receipts, fetch/rank recommendations, update feeds, add workers, run payments/staking/consensus/blockchain, train models, backpropagate, or enable full-auto behavior.

## `v0.2.50`에서 `v0.2.51`로

이번 버전은 한국어 제품 언어 hygiene checker를 추가하는 호환 가능한 문서/도구 패치입니다.

바뀐 점:

- `wom-kit/tools/check_korean_product_language.py`를 추가했습니다.
- 필수 한국어 제품 언어 anchor와 위험한 wording drift를 검사하는 test를 추가했습니다.
- `wom-kit/docs/korean-product-language-hygiene.md`에 checker 설명을 추가했습니다.
- version metadata를 `0.2.51`로 업데이트했습니다.

private archive migration은 필요 없습니다.

이번 버전은 archive product CLI나 MCP behavior를 추가하지 않습니다. checker는 local-only/read-only입니다. 파일을 자동 수정하거나 implementation identifier를 rename하거나 외부 URL을 가져오거나 provider를 호출하거나 GitHub Release를 수정하지 않습니다. ZET transport, trust/import/acceptance/anchor, attestation/signature write, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, worker, payment, staking, consensus, blockchain, model training, backpropagation, full-auto behavior를 구현하지 않습니다.

## `v0.2.49`에서 `v0.2.50`으로

이번 버전은 한국어 제품 언어 기준선을 추가하는 호환 가능한 문서 패치입니다.

바뀐 점:

- `wom-kit/docs/concepts/korean-product-language-baseline.ko.md`를 추가했습니다.
- WOM, zettel-kasten, zet, ZET, objet, lifecycle 동사, block/header/body, foreign block 안전 용어, 공유 형식/방식, surface/action 용어, SNS형 ZET 행동, 메신저형 ZET 스레드의 한국어 설명 기준을 정리했습니다.
- README와 공개 문서 지도에서 새 기준선으로 연결했습니다.
- version metadata를 `0.2.50`으로 업데이트했습니다.

private archive migration은 필요 없습니다.

이번 버전은 archive product CLI나 MCP behavior를 추가하지 않습니다. CLI command, JSON field, schema field, filename, implementation identifier도 한국어로 바꾸지 않습니다. real ZET transport, real trust/import/acceptance/anchor, attestation/signature write, RF access, key-sharing registry, mirroring delivery, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, payment, staking, consensus, blockchain, model training, backpropagation, full-auto behavior를 구현하지 않습니다.

## From `v0.2.48` To `v0.2.49`

This is a compatible public release link hygiene patch.

What changed:

- added `wom-kit/tools/check_public_links.py`,
- added tests for repo-local Markdown links and GitHub Release body link hygiene,
- documented repo-local Markdown links versus GitHub Release body links,
- converted known unsafe release-note relative file links to absolute GitHub `blob` URLs.

No private archive migration is required.

This release adds no archive product CLI or MCP behavior. It does not edit GitHub Releases, fetch external URLs, call providers, publish to WordPress, write projection records or receipts, run ZET transport, fetch or rank recommendations, update neighbor feeds, create trust/import/acceptance/attestation/signature/minting changes, add background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.47` To `v0.2.48`

This is a compatible ZET radio-frequency recommendation model baseline patch.

What changed:

- documented followed/neighbor feeds versus recommended/broadcast feeds,
- documented the radio-frequency metaphor for user/node-selected ZET channels or scopes,
- documented prompt-as-algorithm selectors as inspectable policy/rule/config/code bundles,
- added a sanitized non-executable selector example.

No private archive migration is required.

This release adds no CLI or MCP behavior. It does not fetch recommendations, rank feeds, update neighbor feeds, call providers, publish to WordPress, write projection records or receipts, run real ZET transport, create trust/import/acceptance/attestation/signature/minting changes, add background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.46` To `v0.2.47`

This is a compatible ZET closed sharing model baseline patch.

What changed:

- documented the base zettel-kasten layer as GitHub-tracked records, object storage, and DB relationships,
- documented the unit layer distinction between `zet` and `objet`,
- documented the future ZET closed sharing/SNS layer above the base system,
- clarified that GitHub is not the whole ZET sharing architecture,
- clarified that WordPress is one possible user-selected projection surface, not the WOM/ZET UI,
- added sanitized non-executable closed sharing examples.

No private archive migration is required.

This release adds no CLI or MCP behavior. It does not call providers, publish to WordPress, write projection records or projection receipts, implement real ZET transport, automatically update neighbor feeds, mint, trust, import, accept, attest, sign, anchor, apply, introduce Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## From `v0.2.45` To `v0.2.46`

This is a compatible ZET projection plan dry-run preview patch.

What changed:

- added `archive projection-plan <archive-root> --zet <zet-id-or-path> --surface <surface-kind> --dry-run --format json`,
- added read-only MCP `zet_projection_plan_check`,
- added metadata-only planning output for one local zet and one operator-declared surface kind,
- added closed safety flags for provider calls, WordPress publishing, projection writes, projection receipts, trust/import/acceptance, attestation, signature, minting, ZET transport, and full-auto behavior.

No private archive migration is required.

The preview reads one local archive zet only enough to confirm existence and extract safe metadata. It does not output the full zet body, write files, create receipts, call providers, publish to WordPress, mint, trust, import, accept, attest, sign, anchor, apply, or run ZET transport.

## From `v0.2.44` To `v0.2.45`

This is a compatible ZET publication surface baseline patch.

What changed:

- added documentation for the no-UI WOM core and user-selected publication/projection surfaces,
- added sanitized example files for a future projection envelope, WordPress-like title, and WOM Safe HTML-compatible post body,
- clarified that posting is not minting,
- clarified that a surface locator is not the canonical zet identity.

No private archive migration is required.

This release adds no CLI or MCP behavior. It does not call providers, publish to WordPress, implement projection-plan CLI/MCP, create projection receipts, trust, import, accept, attest, sign, mint, anchor, run ZET transport, add payments, staking, consensus, blockchain, Redis, model training, backpropagation, or full-auto behavior.

## From `v0.2.43` To `v0.2.44`

This is a compatible foreign block attestation statement draft decision preview patch.

What changed:

- added `archive attestation-statement-draft-decision <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--decision-intent`, `--reviewer`, `--expected-review-scope`, `--expected-statement-style`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_statement_draft_decision_preview`,
- added route previews for keeping a draft under review, revising it, rejecting it later, preparing a future explicit attestation statement review, or requesting more review.

No private archive migration is required.

The preview revalidates the current statement draft review index, statement draft record/receipt, candidate record/receipt, quarantine case/receipt, and decision record/receipt. It writes nothing and records no decision. Review notes are local preview context only; raw note bodies are not echoed or stored. Statement drafts remain untrusted and do not create trust, import, acceptance, attestation, signature, mint, receipt write, WordPress publishing, provider calls, sharing, or ZET transport.

## From `v0.2.42` To `v0.2.43`

This is a compatible foreign block attestation statement draft review index patch.

What changed:

- added `archive attestation-statement-draft-review <archive-root> --format json`,
- added optional `--case-id`, `--statement-style`, `--review-scope`, and `--include-receipts` filters,
- added read-only MCP `foreign_block_attestation_statement_draft_review_index`,
- added consistency checks for recorded statement draft records, statement draft receipts, current candidate records/receipts, quarantine cases/receipts, and decision records/receipts.

No private archive migration is required.

The review index writes nothing, keeps `dry_run: true`, and returns `would_change: []`. `--statement-style` and `--review-scope` filter displayed records only; they do not hide blockers from other discovered records. `--case-id` intentionally scopes the verdict to that one case. Indexed statement drafts remain untrusted and do not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.41` To `v0.2.42`

This is a compatible foreign block attestation statement draft write approval patch.

What changed:

- added `archive record-attestation-statement-draft <archive-root> --draft-preview <json-file> --dry-run --format json`,
- added CLI-only `--approve --reviewed-by <safe-actor-id>` to record the statement draft and matching receipt,
- added read-only MCP `record_attestation_statement_draft_check`,
- added stale/tamper checks that revalidate the current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt before writing.

No private archive migration is required.

Dry-run writes nothing. Approved mode writes exactly two local files and keeps the foreign block untrusted. It does not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.40` To `v0.2.41`

This is a compatible foreign block attestation statement draft preview patch.

Changed:

- added `archive attestation-statement-draft <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-review-scope`, `--prospective-attestor`, `--statement-style`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_statement_draft_preview`,
- added non-binding statement draft output for one recorded attestation review candidate.

No private archive migration is required.

The preview re-reads current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt state before returning a draft. It writes nothing and does not create trust, import, attestation, signature, mint, receipt, sharing, provider calls, or ZET transport.

## From `v0.2.39` To `v0.2.40`

This is a compatible foreign block attestation review candidate index patch.

Changed:

- added `archive attestation-candidate-review <archive-root> --format json`,
- added optional `--case-id`, `--review-scope`, and `--include-receipts`,
- added read-only MCP `foreign_block_attestation_review_candidate_index`,
- added consistency checks for candidate records, candidate receipts, quarantine cases/receipts, and decision records/receipts.

No private archive migration is required.

The command writes nothing, keeps `dry_run: true`, and returns `would_change: []`. Filters only change displayed candidates; all discovered candidate records are still validated before top-level `ok` is set. Indexed candidates remain untrusted and do not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

## From `v0.2.38` To `v0.2.39`

This is a compatible foreign block attestation review candidate write approval patch.

Changed:

- added `archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --dry-run --format json`,
- added CLI-only `--approve --reviewed-by <actor-id>` for recording an untrusted candidate record and receipt,
- added optional replay guards for case id, review scope, and prospective attestor,
- added read-only MCP `record_attestation_review_candidate_check`.

No private archive migration is required.

Dry-run writes nothing. Approved CLI mode writes exactly one untrusted candidate record and one receipt. It does not trust, import, attest, sign, mint, accept, share, call providers, or run ZET transport.

## From `v0.2.37` To `v0.2.38`

This is a compatible foreign block attestation review candidate planning patch.

Changed:

- added `archive attestation-review-candidate <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- added optional `--expected-decision`, `--expected-outcome`, `--prospective-attestor`, `--review-scope`, and `--review-note`,
- added read-only MCP `foreign_block_attestation_review_candidate_plan`,
- added a safe candidate packet for human review when the recorded decision is `eligible_for_attestation_review`.

No private archive migration is required.

The planner writes nothing. It does not trust, import, attest, mint, anchor, delegate, sign, accept, apply, share, call providers, or run ZET transport.

## From `v0.2.36` To `v0.2.37`

This compatible patch adds a read-only outcome planner for one recorded quarantine decision:

- `archive quarantine-decision-outcome <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-decision`, `--reviewer`, and `--review-note`,
- read-only MCP `foreign_block_decision_outcome_plan`,
- conservative next-step routing for recorded decisions.

No private archive migration is required.

The planner writes nothing. It does not trust, import, attest, mint, anchor, delegate, sign, accept, apply, share, or call providers. `eligible_for_attestation_review` only becomes `prepare_attestation_review_candidate` for a future explicit workflow.

## From `v0.2.35` To `v0.2.36`

This compatible patch adds a read-only review index for recorded quarantine decisions:

- `archive quarantine-decision-review <archive-root> --format json`,
- optional `--case-id`, `--decision`, and `--include-receipts`,
- read-only MCP `foreign_block_quarantine_decision_review_index`,
- consistency checks for quarantine decision records and matching decision receipts.

No private archive migration is required.

The command writes nothing. It does not trust, import, attest, mint, anchor, delegate, sign, accept, apply, share, or call providers.

## From `v0.2.34` To `v0.2.35`

This compatible patch adds CLI-only approved quarantine decision recording:

- `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --dry-run --format json`,
- `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --approve --reviewed-by <actor-id> --format json`,
- optional `--expected-case-id`, `--expected-decision`, and `--review-note`,
- read-only MCP `record_quarantine_decision_check`.

No private archive migration is required.

Approved mode writes exactly two local files:

```text
quarantine/foreign-blocks/<case-id>/quarantine-decision.json
receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json
```

This records only an operator-reviewed quarantine decision. It does not trust, import, attest, mint, anchor, delegate, sign, accept, apply, share, or call providers.

## From `v0.2.33` To `v0.2.34`

This compatible patch adds a foreign block quarantine decision preview:

- `archive quarantine-decision <archive-root> --case-id <safe-id> --dry-run --format json`,
- optional preview context: `--decision-intent`, `--reviewer`, and `--review-note`,
- read-only MCP `foreign_block_quarantine_decision_check`,
- decision-path preview for existing untrusted quarantine cases.

No private archive migration is required.

The preview reads one quarantine case and matching receipt. It does not write a decision, record approval, trust, import, attest, mint, anchor, delegate, sign, accept, apply, or call providers.

Possible preview decisions:

- `keep_quarantined`,
- `reject_and_keep_record`,
- `eligible_for_attestation_review`,
- `needs_more_review`.

`eligible_for_attestation_review` is not trust. It only means a future explicit attestation review path may be appropriate.

## From `v0.2.32` To `v0.2.33`

This compatible patch adds a foreign block quarantine review index:

- `archive quarantine-review <archive-root> --format json`,
- optional `--case-id`, `--status`, and `--include-receipts`,
- read-only MCP `foreign_block_quarantine_review_index`,
- read-only checks for existing untrusted quarantine cases and matching quarantine write receipts.

No private archive migration is required.

The review index reads only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Indexing does not mean trust, import, acceptance, attestation, minting, anchoring, delegation, signing, or apply approval. It only gives a stable review list for untrusted quarantine cases.

## From `v0.2.31` To `v0.2.32`

This compatible patch adds approved foreign block quarantine writes:

- `archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json`
- `archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json`
- read-only MCP `quarantine_foreign_block_check`

No private archive migration is required.

Approved quarantine write creates only:

- `quarantine/foreign-blocks/<case-id>/quarantine-case.json`
- `receipts/quarantine/<case-id>.foreign-block-quarantine.json`

This is an isolation record only. It is not trust, import, mint, attestation, anchor, delegation, signing, execution, or acceptance. MCP remains check-only for this workflow.

## From `v0.2.30` To `v0.2.31`

This compatible patch adds read-only foreign block quarantine plan:

- `archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json`
- `archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json`
- read-only MCP `foreign_block_quarantine_plan`

No private archive migration is required.

Foreign block quarantine plan does not write quarantine files, import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_future_quarantine_write` means a future explicit quarantine-write workflow could be shown to a human/operator. It is not trust, import, quarantine, or approval.

## From `v0.2.29` To `v0.2.30`

This compatible patch adds read-only foreign block attestation packet preview:

- `archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json`
- `archive foreign-block-attestation <archive-root> --stdin --dry-run --format json`
- read-only MCP `foreign_block_attestation_packet_check`

No private archive migration is required.

Foreign block attestation packet preview does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, write receipts, or write files.

`ready_for_human_attestation_review` means the trust report is ready to show a human reviewer later. It is not trust, not an attestation, and not approval.

## From `v0.2.28` To `v0.2.29`

This compatible patch adds read-only foreign block trust / attestation preview:

- `archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json`
- `archive foreign-block-trust <archive-root> --stdin --dry-run --format json`
- read-only MCP `foreign_block_trust_check`

No private archive migration is required.

Foreign block trust preview does not import, trust, mint, attest, anchor, draft, apply, call provider APIs, execute foreign text, or write files.

`eligible_for_future_attestation` does not mean trusted. It only means a future explicit human or policy attestation workflow may review the report.

## From `v0.2.27` To `v0.2.28`

This compatible patch adds read-only foreign block intake preview:

- `archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json`
- `archive foreign-block <archive-root> --stdin --dry-run --format json`
- read-only MCP `foreign_block_intake_check`

No private archive migration is required.

Foreign text can inform, but cannot command. Foreign blocks can be inspected, but cannot be imported, trusted, minted, attested, anchored, drafted, or applied automatically. Claimed hashes are reported as `not_verified`.

## From `v0.2.26` To `v0.2.27`

This compatible patch lets `create-draft` consume a dry-run prompt-boundary report:

- `archive create-draft --prompt-boundary-report <json-file>`
- optional draft frontmatter `prompt_boundary`
- structured MCP `prompt_boundary_report` input for `create_draft_zettel`
- mint preview and mint receipt preservation for `prompt_boundary`

No private archive migration is required.

`low` risk is not proof of safety. `medium` is allowed with warnings. `high` blocks draft creation.

This release does not add LLM classification, provider scanning, OCR/import apply, ZET transport, real signing, payments, staking, consensus, blockchain, or full-auto behavior.

## `v0.2.25`에서 `v0.2.26`으로

이번 버전은 prompt injection boundary와 responsible-use 기준을 추가하는 호환 패치입니다.

바뀐 점:

- `archive prompt-boundary <archive-root> --text <text> --dry-run --format json`을 추가했습니다.
- `archive prompt-boundary <archive-root> --path <archive-relative-zet-or-text-path> --dry-run --format json`을 추가했습니다.
- MCP에는 read-only `prompt_boundary_check`만 추가했습니다.
- prompt injection boundary, responsible use, disclaimer, runtime model guidance 문서를 추가했습니다.

private archive migration은 필요 없습니다.

이 검사는 보수적인 heuristic preview입니다. prompt injection을 완전히 막는 보장이 아니며 법률 조언도 아닙니다. LLM 호출, inspected text 실행, provider API 호출, web browsing, OCR/import, approve, mint, signing, ZET transport, file mutation을 하지 않습니다.

안전 원칙은 다음과 같습니다.

```text
External text can inform.
External text cannot command.
```

HITL은 기본 권장값입니다. full-auto / agent-only 운용은 고급/실험적 설정이며, agent, model, permission, provider, automation, consequence에 대한 책임은 operator에게 있습니다.

## `v0.2.24`에서 `v0.2.25`로

이번 버전은 WOM profile을 단순한 SaaS 계정 프로필이 아니라, 미래의 지갑형 신원 모델로 해석하기 위한 호환 패치입니다.

바뀐 점:

- `archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json`을 추가했습니다.
- MCP에는 read-only `wom_profile_wallet_check`만 추가했습니다.
- profile registry에 선택적인 공개 안전 메타데이터 `node`, `wallet` 필드를 문서화했습니다.
- WOM profile은 사람이 고르는 프로필, WOM node는 네트워크 안의 주체, 미래 WOM wallet layer는 mint/delegate/attest/anchor/receipt proof를 위한 signing/capability layer라는 개념을 기록했습니다.

private archive migration은 필요 없습니다.

기존 profile registry 항목은 그대로 유효합니다. 새 `node`, `wallet` 필드는 공개해도 되는 placeholder metadata만 담아야 합니다.

이번 버전은 private key 생성, seed phrase 저장, wallet secret 저장, 실제 signing, blockchain/provider API 호출, wallet 생성/등록, WOM coin, NFT-like access, payment, staking, consensus, ledger, P2P transport를 구현하지 않습니다.

## `v0.2.23`에서 `v0.2.24`로

이번 버전은 block header를 read-only dry-run으로 미리 보는 호환 패치입니다.

바뀐 점:

- `archive block-header <archive-root> --path <zet-path> --dry-run --format json`을 추가했습니다.
- `archive block-header <archive-root> --zettel-id <id> --dry-run --format json`을 추가했습니다.
- `block = zet + header` 모델에 맞춰 header preview를 만듭니다.
- body, header, block hash preview를 안정적으로 계산합니다.
- MCP에는 read-only `block_header_check`만 추가했습니다.

private archive migration은 필요 없습니다.

이 버전은 zet 수정, mint, receipt 쓰기, referenced objet/source file body 읽기, referenced source hash 계산, provider URL 추적, provider API 호출, transport/economic layer 구현을 하지 않습니다.

안전한 개념 순서는 다음과 같습니다.

```text
zet -> header -> block -> receipt -> attestations -> anchors -> possible token layer later
```

## `v0.2.22`에서 `v0.2.23`으로

이번 버전은 source intake dry-run 결과를 `create-draft`가 안전하게 소비하도록 하는 호환 패치입니다.

바뀐 점:

- `archive create-draft --source-intake-plan <json-file>`을 추가했습니다.
- source intake plan이 성공한 dry-run이고, blocker가 없고, metadata-only이며, 안전한 refs만 담았는지 검증합니다.
- `source_refs_for_draft`를 draft `source_refs`로 병합하면서 기존 `--source-ref`도 보존합니다.
- draft frontmatter에 선택적 `source_intake` metadata를 추가해 plan hash와 content access proof를 남깁니다.
- MCP `create_draft_zettel`이 structured `source_intake_plan` object를 받을 수 있습니다.

private archive migration은 필요 없습니다.

이 버전은 원본 source file을 읽거나, plan 안의 local path를 따라가거나, source intake apply, objet capture, copy, upload, import, OCR, transcription, full source hash, provider API call, automatic mint, MCP real minting을 구현하지 않습니다.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json > source-intake-plan.json

archive create-draft <archive-root> --dry-run \
  --title "Draft title" \
  --body "Draft body" \
  --source-intake-plan source-intake-plan.json \
  --format json
```

## `v0.2.21`에서 `v0.2.22`로

이번 버전은 source intake를 먼저 dry-run으로 계획하는 호환 가능한 패치입니다.

바뀐 점:

- `archive source-intake <archive-root> --dry-run --format json` 명령을 추가했습니다.
- local file, source map item, source-relative path, manifested objet, provider ref, AI artifact를 metadata-only로 분류합니다.
- draft에 넘길 수 있는 안전한 `source_refs_for_draft`를 반환합니다.
- `provider-bindings.yml`을 읽어 object storage context를 보고합니다.
- MCP에는 읽기 전용 `source_intake_plan`만 추가했습니다.

private archive migration은 필요 없습니다.

이번 버전은 file body 읽기, full hash 계산, copy, upload, import, OCR, transcription, extraction, provider API 호출, 자동 draft creation, mint, provider sync를 하지 않습니다.

```bash
archive source-intake <archive-root> --dry-run \
  --object-id sha256:<hash> \
  --format json
```

## `v0.2.20`에서 `v0.2.21`로

이번 버전은 object storage/objet setup을 먼저 dry-run으로 계획하는 호환 가능한 패치입니다.

바뀐 점:

- `archive object-storage <archive-root> --dry-run --format json` 명령을 추가했습니다.
- 기본 bucket/container 이름은 `zettel-kasten-<normalized-profile-slug>-objets`입니다.
- 기본 오브제 prefix는 `archives/<archive_id>/objets/`입니다.
- provider kind, profile slug, bucket/container name, region, endpoint ref, storage account ref에 안전성 검사를 추가했습니다.
- `--approve --reviewed-by`는 provider API를 건드리지 않고 local metadata와 setup receipt만 씁니다.
- `--write-local-profile`은 ignored local object storage account hint만 `profiles/local/` 아래에 씁니다.
- MCP에는 읽기 전용 `object_storage_setup_plan`만 추가했습니다.

private archive migration은 필요 없습니다.

이번 버전은 bucket/container 생성, OAuth, provider API 호출, upload, sync, source file copy, file hash 계산, source content import를 하지 않습니다.

```bash
archive object-storage <archive-root> --dry-run \
  --provider cloudflare-r2 \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --storage-account-ref storage:account:honggildong \
  --format json
```

## `v0.2.19`에서 `v0.2.20`로

이번 버전은 WOM profile별 GitHub repository setup을 먼저 dry-run으로 계획하는 호환 패치입니다.

바뀐 점:

- `archive github-repo <archive-root> --dry-run --format json` 명령이 추가되었습니다.
- 기본 repository 이름은 `zettel-kasten-<profile_slug>`입니다.
- profile slug, repository name, GitHub owner, account ref에 대해 path/URL/token/email처럼 위험한 값을 막습니다.
- `--approve --reviewed-by`는 GitHub를 건드리지 않고 local `provider-bindings.yml`과 setup receipt만 씁니다.
- `--write-local-profile`을 쓰면 ignored local account hint를 `profiles/local/` 아래에 씁니다.
- MCP에는 읽기 전용 `github_repository_setup_plan`만 추가되었습니다.

private archive migration은 필요 없습니다.

이 버전은 GitHub repository 생성, OAuth, GitHub API 호출, `gh` 실행, git remote 설정, push, sync를 하지 않습니다.

```bash
archive github-repo <archive-root> --dry-run \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --github-owner example-user \
  --github-account-ref github:account:honggildong \
  --format json
```

## `v0.2.18`에서 `v0.2.19`로

이번 버전은 WOM-kit naming/path cleanup을 위한 호환 가능한 패치입니다.

바뀐 점:

- 구현 폴더가 `wom-kit/`으로 바뀌었습니다.
- Python import package가 `wom_kit`으로 바뀌었습니다.
- package metadata의 project name이 `wom-kit`이 되었습니다.
- 기존 `archive`, `archive-mcp` console script는 compatibility surface로 유지됩니다.
- 설치 환경에서는 선호 alias인 `wom`, `wom-mcp`도 사용할 수 있습니다.

private archive migration은 필요 없습니다.

현재 명령 예시는 새 path/package를 사용합니다:

```bash
python wom-kit/cli/archive.py doctor wom-kit/examples/fake-life-archive --strict
python -m wom_kit.archive_cli doctor wom-kit/examples/fake-life-archive --strict
```

## `v0.2.17`에서 `v0.2.18`로

이번 버전은 profile-aware draft zet creation dry-run을 추가하는 호환 가능한 패치입니다.

바뀐 점:

- `archive create-draft --dry-run --format json` 명령이 추가되었습니다.
- draft id, created-at timestamp, expected body hash, draft approver를 replay 값으로 사용할 수 있습니다.
- resolved profile id, operator id, authority mode, source refs, local AI sessions, assisted-by, supervised-by를 draft provenance에 남길 수 있습니다.
- MCP `create_draft_zettel`도 같은 dry-run/profile-aware 입력을 받습니다.
- 실제 draft write는 계속 `inbox/` 안으로만 제한됩니다.
- minting은 여전히 `mint-zet --approve --reviewed-by`로 분리된 승인 단계입니다.

private archive migration은 필요 없습니다. 기존 draft는 그대로 유효합니다.

profile-bound AI write는 먼저 profile-resolve와 runtime-context를 확인하고, create-draft dry-run을 본 뒤, 사람이 draft를 승인했을 때 같은 draft id, created-at, expected archive id/type, profile id, expected body hash로 replay해야 합니다.

```bash
git fetch --tags
git checkout v0.2.18
```

## `v0.2.16`에서 `v0.2.17`로

이번 버전은 WOM Profile Registry dry-run을 추가하는 호환 가능한 패치입니다.

바뀐 점:

- `archive profile-list --registry <path> --format json` 명령이 추가되었습니다.
- `archive profile-resolve --registry <path> --target <query> --format json` 명령이 추가되었습니다.
- MCP에도 읽기 전용 `wom_profile_list`, `wom_profile_resolve` 도구가 추가되었습니다.
- AI runtime이 runtime-context나 draft 작업 전에 요청된 profile을 먼저 확인할 수 있습니다.
- 예시 registry는 `wom-kit/templates/profiles/wom-profiles.example.yml`에 추가되었습니다.

private archive migration은 필요 없습니다.

이번 버전은 profile 등록, token 저장, create-draft dry-run, provider API sync, UI, MCP를 통한 real minting, MCP write/register/apply tool을 추가하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.17
```

## `v0.2.15`에서 `v0.2.16`으로

이번 버전은 WOM AI Runtime Context Layer를 추가하는 호환 가능한 패치입니다.

바뀐 점:

- `archive runtime-context <archive-root> --format json` 명령이 추가되었습니다.
- `--expected-archive-id`, `--expected-type`, `--strict` 옵션으로 AI runtime이 draft를 만들거나 dry-run을 실행하거나 mint 승인을 요청하기 전에 올바른 archive에 붙어 있는지 확인할 수 있습니다.
- 기본 출력은 로컬 절대경로를 숨기고 archive-relative path만 보여줍니다. 신뢰할 수 있는 로컬 디버깅 때만 `--no-redact-local-paths`를 사용할 수 있습니다.
- MCP에도 읽기 전용 `archive_runtime_context` 도구가 추가되었습니다. 기존 MCP allowed roots 규칙을 그대로 따릅니다.

private archive migration은 필요 없습니다.

이번 버전은 create-draft dry-run, provider API sync, UI, MCP를 통한 real minting, MCP apply tool을 추가하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.16
```

## `v0.2.14`에서 `v0.2.15`로

WOM Safe HTML Profile dry-run validator 패치이며, 호환 가능한 변경입니다.

변경 사항:

- `archive check-safe-html --path <zet> --dry-run`이라는 읽기 전용 CLI 명령을 추가했습니다. v0.2 Markdown 호환 zet가 미래의 WOM Safe HTML Profile 마이그레이션과 호환 가능한지 미리 검사합니다.
- validator는 `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URL, 그리고 `onclick=` 같은 inline event handler attribute가 zet body 안에 있으면 차단합니다.
- validator는 `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, `source_reference_preview` 필드를 포함한 구조화된 JSON을 반환합니다.

실제 private archive migration은 필요 없습니다.

이번 릴리스는 Markdown-to-HTML 변환기, profile allowlist, UI, live sharing, P2P transport, external provider sync를 구현하지 않습니다. 기존 Markdown 호환 zets는 그대로 유효합니다.

```bash
git fetch --tags
git checkout v0.2.15
```

## `v0.2.13`에서 `v0.2.14`로

WOM Safe HTML Profile을 위한 호환 가능한 문서/스펙 기준선 패치입니다.

변경 사항:

- `WOM`, `zet`, `ZET`의 차이를 문서화했습니다.
- `zet`는 zettel-kasten 안에서 민팅되는 단위 문서라고 명확히 했습니다.
- `ZET`는 메신저, SNS/feed, 협업툴로 확장될 수 있는 미래 통신 계층이라고 명확히 했습니다.
- WOM Safe HTML Profile을 장기 canonical/interchange/rendering target으로 기록했습니다.
- Markdown은 v0.2 authoring/import compatibility format으로 유지했습니다.

실제 private archive migration은 필요 없습니다.

이번 릴리스는 Markdown-to-HTML converter, profile validator, UI, live sharing, P2P transport, external provider sync를 구현하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.14
```

## `v0.2.12`에서 `v0.2.13`으로

호환 가능한 WOM 명칭 기준선과 CLI alias 패치입니다.

변경 사항:

- `WOM`을 전체 umbrella name으로, `Widesider of Modernity`를 그 확장명으로 기록했습니다.
- zet를 민팅하는 선호 명령으로 `archive mint-zet`을 추가했습니다.
- 기존 `archive mint-zettel`은 compatibility alias로 유지했습니다.
- 범위가 정해진 portable unit을 만드는 선호 명령으로 `archive parcel`을 추가했습니다.
- 기존 `archive pack`은 compatibility alias로 유지했습니다.
- parcel/workpack을 들여오는 과정을 미리 검토하는 선호 명령으로 `archive admit --dry-run`을 추가했습니다.
- 기존 `archive import --dry-run`은 compatibility alias로 유지했습니다.

실제 private archive migration은 필요 없습니다.

기존 스크립트는 옛 이름을 계속 써도 됩니다. 다만 새 사용자-facing 문서는 `mint-zet`, `parcel`, `admit`을 우선 사용해야 합니다.

```bash
git fetch --tags
git checkout v0.2.13
```

## `v0.2.11`에서 `v0.2.12`로

호환 가능한 real delegate receipt write 패치입니다.

변경 사항:

- `archive delegate-zet --approve --reviewed-by <actor>` 추가,
- 실제 delegate 실행 시 `receipts/delegate/*.delegate.json` 생성,
- `archive doctor`가 applied delegate receipt 검증,
- real delegate capability receipt에 nonce 생성,
- claim/spent/revocation registry는 아직 구현하지 않음을 명시.

private archive migration은 필요하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.12
```

## `v0.2.10`에서 `v0.2.11`로

호환 가능한 delegate capability 계약 패치입니다.

변경 사항:

- `archive delegate-zet --dry-run`에 `--target-policy counterparty_bound|claimable_once` 추가,
- `claimable_once` delegate preview에서는 `--target-archive` 없이도 실행 가능,
- `delegation_capability`, `claim_binding`, `settlement_condition` preview field 추가,
- settlement는 아직 비금융 상태이며 `mode: "none"`으로만 기록,
- 실제 P2P, claim registry, spent registry, revocation, blockchain, payment는 아직 구현하지 않음.

private archive migration은 필요하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.11
```

## `v0.2.9`에서 `v0.2.10`으로

이 버전은 호환 가능한 dry-run lifecycle 기능 패치입니다.

변경 사항:

- `archive delegate-zet --dry-run` 추가,
- `archive attest-zet --dry-run` 추가,
- `archive anchor-zet --dry-run` 추가,
- delegate, attest, anchor를 위한 read-only MCP check 추가,
- delegate receipt, attestation receipt, anchor metadata schema 추가.

private archive migration은 필요하지 않습니다.

실제 P2P, feed, transport, 외부 전송, foreign zet import는 아직 구현하지 않습니다.

```bash
git fetch --tags
git checkout v0.2.10
```

## `v0.2.8`에서 `v0.2.9`로

호환 가능한 용어 안정화 패치입니다.

변경 사항:

- 새 archive는 `human_minting`을 기본값으로 사용합니다.
- 기존 `human_promotion` archive도 계속 유효합니다.
- zettel rules에서 `minting_rules`를 사용할 수 있습니다.
- `promotion_rules`는 v0.2 legacy fallback으로 유지됩니다.
- 사용자-facing 문서는 minting 언어를 우선 사용합니다.

실제 private archive migration은 필요 없습니다.

```bash
git fetch --tags
git checkout v0.2.9
```

## `v0.2.7`에서 `v0.2.8`로

호환 가능한 민팅 라이프사이클 기능 패치입니다.

변경 사항:

- `archive mint-zettel --dry-run`을 추가했습니다.
- `archive mint-zettel --approve --reviewed-by <id>`를 추가했습니다.
- `receipts/mint/` 아래 mint receipt를 추가했습니다.
- `receipts/mint/drafts/` 아래 draft snapshot을 추가했습니다.
- canonical zettel의 `mint` frontmatter를 추가했습니다.
- doctor가 mint receipt와 SHA-256 파일 연결을 검증합니다.
- read-only MCP `mint_zettel_check`를 추가했습니다.

실제 private archive migration은 필요 없습니다.

새 zettel을 민팅했다면 canonical zettel, mint receipt, draft snapshot을 함께 보관하세요.

```bash
git fetch --tags
git checkout v0.2.8
```

## `v0.2.3`에서 `v0.2.4`로

문서 정돈 패치입니다.

변경 사항:

- `README.md`를 더 정돈된 영문 프로젝트 진입 문서로 다시 작성했습니다.
- `README.ko.md`를 한국어 공식 진입 문서로 추가했습니다.
- 업그레이드 문서를 영문/한국어로 분리했습니다.
- 공개 포지셔닝, 현재 상태, privacy boundary, storage model, text provenance 설명을 정리했습니다.

실제 private archive migration은 필요 없습니다.

권장 명령:

```bash
git fetch --tags
git checkout v0.2.4
```

## `v0.2.2`에서 `v0.2.3`으로

한영 문서 병기 패치입니다.

실제 private archive migration은 필요 없습니다.

```bash
git fetch --tags
git checkout v0.2.3
```

## `v0.2.1`에서 `v0.2.2`로

문서, provenance, 공개 히스토리 정리 패치입니다.

실제 private archive migration은 필요 없습니다.

중요 개념:

```text
original editable text != OCR/AI-derived text
```

둘 다 보관하지만, OCR/AI-derived text는 derivation metadata와 review status를 남겨야 합니다.

## 이전 버전에 남기

사용자는 오래된 버전에 남을 수 있습니다.

이것도 설계의 일부입니다.

```text
old version -> old rule set
new version -> updated rule set
```

미래의 sharing/collaboration 기능은 sender/receiver version을 명시해야 합니다.

## 앞으로의 릴리스 요구사항

앞으로 공개 릴리스는 반드시 다음을 포함해야 합니다.

- changelog entry,
- `wom-kit/docs/releases/` 아래 release note,
- compatibility statement,
- migration instructions,
- test/doctor verification status,
- privacy scan status,
- Git tag,
- GitHub Release.
