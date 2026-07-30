# v0.3.289 휠 리소스 무결성 검사 강화 지시서

- 작성일: 2026-07-30
- 작업 브랜치: `codex/v0.3.289-wheel-resource-integrity`
- 작업 기준 커밋: `84a5f504fb59b010426b56b192839fb9b4b79b73`
- 공개 순서: `v0.3.286 -> v0.3.287 -> v0.3.288 -> v0.3.289`
- 베타테스터 보관소: **읽기 전용**

## 1. 목적

현재 휠 설치 검사는 패키지 리소스가 대략 존재하는지만 확인한다. 이번 릴리스에서는
휠 안의 리소스 manifest와 각 리소스 파일이 저장소에서 검토한 정확한 바이트와
일치하는지 검증한다.

검사는 다음 질문에 모두 답해야 한다.

1. 휠의 manifest가 저장소의 canonical manifest와 정확히 같은가?
2. manifest에 선언된 리소스 집합과 휠에 들어간 리소스 집합이 정확히 같은가?
3. 각 리소스의 크기와 SHA-256이 manifest와 일치하는가?
4. 각 리소스의 실제 바이트가 저장소의 packaged mirror와 정확히 같은가?
5. ZIP 경로, 중복 member, JSON 형식이 안전하고 엄격한가?

## 2. 허용 범위

### 생산 코드 담당

오직 다음 파일만 수정한다.

```text
wom-kit/tools/check_wheel_install.py
```

### 테스트 담당

오직 다음 파일만 새로 만들거나 수정한다.

```text
wom-kit/tests/test_wheel_install.py
```

### 루트 감독자 담당

버전, 릴리스 문서, 결정 기록, 구현 기록, packaged resource 동기화 및 통합 검증을
담당한다.

## 3. 생산 검사기 계약

기존 `assert_wheel_resources(wheel: Path)` 진입점을 유지한다.

다음 항목을 모두 거부해야 한다.

- 동일한 ZIP member 이름이 두 번 이상 나타나는 휠
- 절대 경로
- 빈 path segment
- `.` 또는 `..` segment
- 백슬래시가 들어간 경로
- 정규화되지 않은 경로
- manifest JSON의 중복 key
- UTF-8 또는 JSON 파싱 실패
- 엄격한 schema/type/count 불일치
- manifest와 휠의 리소스 집합 불일치
- 선언 크기, ZIP member 크기, 실제 읽은 바이트 수의 불일치
- 선언 SHA-256과 실제 SHA-256 불일치
- 휠 manifest와 저장소 canonical manifest의 바이트 불일치
- 휠 리소스와 저장소 packaged mirror의 바이트 불일치

다음은 이번 릴리스의 검증 대상이 아니다.

- ZIP 압축률 또는 압축 방법
- ZIP member 순서
- ZIP timestamp
- 권한 bit
- ZIP offset
- 전체 휠의 재현 가능 바이트 동일성

`BadZipFile`, UTF-8 오류, JSON 오류, 잘못된 schema, 리소스 읽기 실패 등은
사용자에게 Python traceback으로 새지 않아야 한다. 검사 경계에서
`WheelCheckError`로 정규화한다.

성공 출력은 적어도 다음 수치를 명시한다.

- `manifested_resource_count`
- `verified_resource_count`
- `verified_resource_bytes`
- `wheel_file_count`

## 4. 테스트 계약

작은 임시 ZIP fixture를 사용해 다음을 독립적으로 검증한다.

- 정상 휠 성공
- 중복 ZIP member 거부
- 위험하거나 비정규화된 경로 거부
- malformed ZIP 거부
- malformed UTF-8/JSON 거부
- duplicate JSON key 거부
- schema/type/file_count 오류 거부
- 누락·추가 리소스 거부
- 크기 및 SHA-256 오류 거부
- canonical manifest 바이트 불일치 거부
- packaged mirror 바이트 불일치 거부
- 저수준 예외가 `WheelCheckError`로 정규화됨
- 성공 통계가 실제 검증 결과를 정확히 반영함

테스트 전용으로 전역 경로를 monkeypatch할 수 있지만, 공개 CLI 계약을 테스트 때문에
넓히지 않는다.

## 5. 금지 사항

- 베타테스터 보관소에서 새 명령을 실행하거나 파일을 쓰지 않는다.
- 이번 단계에서 commit, push, PR, tag, release를 만들지 않는다.
- 다른 담당자의 소유 파일을 수정하지 않는다.
- manifest에 없는 리소스를 추론하거나 자동 복구하지 않는다.
- 다른 릴리스의 기능을 함께 끼워 넣지 않는다.

## 6. 완료 조건

1. 생산 검사기와 전용 회귀 테스트가 계약을 모두 만족한다.
2. 관련 테스트, 문서 테스트, 전체 소스 테스트가 통과한다.
3. 패키지 리소스 동기화가 통과한다.
4. 깨끗한 exact-tree wheel에서 설치·네 진입점·onboarding·Doctor 검증이 통과한다.
5. 독립 검수에서 남은 P1/P2가 없다.
6. 통합 검수 전에는 commit 또는 push하지 않는다.
