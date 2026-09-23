# 활동을 보존하고 끝내기

이 문서는 개발 중인 통합 변경의 사용 계약이다. 공개 설치판 적용 여부는 릴리스 노트와 설치 버전을 확인한다.

## 미발행 zet 보강

편지 초안 수정과 zet 수정은 서로 다르다. 아직 inbox에 있는 zet은 기존 ID·위치·오브제 연결·관계·생성 이력을 유지하며 제목·본문·요약·품질 메타데이터를 수정한다.

1. 같은 ID의 수정 제안 Markdown을 비공개 workbench에 작성한다. 기존 오브제 연결과 출처는 보존한다. AI 근거 문서는 UTF-8, LF 줄바꿈을 유지한다.
2. `draft-revision-plan <archive-root> --draft <inbox-relative-path> --proposal <proposal-relative-path>`으로 근거와 품질을 확인한다.
3. `draft-revision-write`에 동일한 대상·제안, `--approve --reviewed-by <actor> --expected-plan-sha256 <plan-sha>`를 전달한다.
4. `zet-quality-check --dry-run` 후 `mint-zet --dry-run`의 새 근거 지문으로 발행한다. 수정 명령은 자동 발행하지 않는다.
5. 중간 종료 후에는 원래 제안·지문에 `--resume --approve`를 붙인다. 바뀐 대상이나 제안은 덮어쓰지 않는다.

수정 전 본문과 추가 수정 영수증은 보존하며 최초 생성 영수증을 교체하지 않는다. 이미 정본으로 발행했다면 기존 `zet-revision-plan/write`를 사용한다.

## 세션 범위와 같은 목록의 백업·비우기

기본 범위는 해당 세션의 반입 및 작성·수정·발행·연결 작업에서 실제 사용한 오브제다. 검색·열람은 사용 증거로 간주하지 않는다. 인증된 세션·작업 근거가 없는 옛 자료는 귀속 불명으로 표시한다. 날짜나 디렉터리 이름으로 세션을 추정하지 않는다.

`object-storage-scope-list <archive-root> --this-session --output <private-list-outside-archive>`로 정확한 객체 목록을 만든다. 다른 세션과 기존 목록도 명시적으로 추가할 수 있다. 새 목록은 기존 파일을 덮어쓰지 않는다. 개인 목록과 원본 피드백은 공개 저장소에 올리지 않는다.

업로드를 완료하면 `offload_handoff`에 업로드한 동일 객체 목록과 지문이 나온다. 이 목록으로 `object-storage-offload --object-list <private-list> --dry-run`을 확인한 뒤 별도로 실행한다. 업로드만 요청하면 로컬 파일을 삭제하지 않는다. 기본 `--min-age-days 0`은 날짜 필터 없음이며 날짜 미상도 포함한다. 사용자가 직접 지정한 나이 필터와 다른 보존 조건은 결과의 제외 건수로 확인한다.

원격 보존은 전체 다운로드 SHA·크기와 같은 응답의 강한 ETag를 결합한다. 다음 검사는 조건부 HEAD로 같은 바이트 세대인지 확인한다. 약한 ETag나 옛 증거는 필요할 때 한 번 스트리밍 검증하며 원본을 로컬로 복원하지 않는다. 같은 활동 실행의 하위 업로드·비우기는 검증 근거를 공유한다. 연결 실패·원격 변경은 삭제 성공으로 처리하지 않는다. [R2 공식 API](https://developers.cloudflare.com/r2/api/s3/api/#implemented-object-level-operations)

## 외부 파일과 개발 폴더

`activity-cleanup <archive-root> --request <private-request> --dry-run|--approve|--resume`으로 정확한 파일 목록을 처리한다. 요청 스키마는 `activity-cleanup-request-v1.schema.json`이다. 요청 파일은 다음 정보를 가진다.

- `activity_id`: 재개에 사용할 고유한 활동 이름.
- `roots`: 작업 대상의 절대 디렉터리 목록. WOM 아카이브 자체를 외부 원본으로 지정하지 않는다.
- `items`: 각 파일의 절대 경로, `role`, 판단 근거 `reason`, `disposition`.
- 역할은 `deliverable` / `source` / `evidence` / `temporary` / `unknown`. 판단 불명 항목은 먼저 분류해야 한다.
- 기본 `disposition`은 `preserve`. `discard`는 명시적 폐기 의도를 가진 임시물에 사용하며 `discard_intent: true`가 필요하다.
- `storage`: 비공개 공급자·저장소 참조와 자격증명 **참조 이름**. 비밀값을 요청에 적지 않는다.
- `remove_empty_directories`: 파일 처리 후 실제 비었을 때만 제거할 디렉터리.

`--private-plan-output <new-private-file>`은 파일별 판단 근거와 Git/파일 상태를 비공개 계획 파일로 제공한다. 일반 출력은 경로·원문 대신 번호와 건수만 표시한다. 파일명만 보고 폐기하지 않는다.

Git 이력·미커밋·미추적 파일·비밀설정 후보·외부 워크트리 의존성을 구분한다. 코드 파일 몇 개의 보존을 폴더 전체 보존이라고 부르지 않는다. 공용 Git 메타데이터를 쓰는 다른 워크트리가 남아 있으면 그 메타데이터의 삭제를 실행하지 않는다. 새 파일·교체 파일·잠긴 파일은 남기고 별도 결과로 알린다.

실제 삭제는 Windows 네이티브 파일 핸들에 결합된 기존 삭제기를 사용한다. 다른 운영체제에서는 계획과 분류만 지원하며 삭제 부작용 전에 미지원 상태를 알린다. 재개는 서명된 원래 요청과 파일별 기록을 사용한다. 이미 처리한 파일은 다시 삭제하지 않는다. 부분 결과는 `partial`이며 전체 완료가 아니다.

유효한 전체 액세스에서는 하위 반입·업로드·정리를 포함해 추가 승인창이 없다. 만료된 권한은 다시 사용하지 않는다. 제품의 외부 정리 정책은 공식 활동 명령을 지원하도록 갱신된다. 임의의 사용자 작성 지침을 몰래 고치지 않으며, 명시된 현행 지침과 충돌하면 원인과 공식 경로를 표시한다.

## 품질·비용·진행 표시

직접 만든 표는 `parse_review.table_origin: authored`, 원본을 전사한 표는 `transcribed`, 혼합은 `mixed`로 구분한다. 직접 만든 표에 없는 원본 행 번호를 요구하지 않는다. `structure_reviewed` 등 검토 표시는 실제 검토 뒤에만 작성하며 WOM이 자동으로 완료 처리하지 않는다.

업로드·비우기·백업 상태의 용량은 객체 ID 기준으로 중복 제거한다. 기록 시점 원격 보존과 현재 원격 확인은 다르며 이를 구분한다. R2 Standard 예상 월 저장비와 요청 비용을 별도로 표시한다. 계정 전체 사용량을 모르면 무료 한도를 빼지 않는다. 출처·기준일·계산 가정과 실제 청구액 미확정 상태를 함께 표시한다. [R2 공식 요금표](https://developers.cloudflare.com/r2/pricing/)

`--progress-log`는 기존 파일을 덮어쓰지 않고 `.1`, `.2`로 새 로그를 만든다. 옵션 오류는 옵션명만 표시하며 값·개인 경로를 노출하지 않는다.
