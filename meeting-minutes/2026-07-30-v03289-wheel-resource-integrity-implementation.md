# v0.3.289 휠 리소스 무결성 구현 기록

- 날짜: 2026-07-30
- 브랜치: `codex/v0.3.289-wheel-resource-integrity`
- 시작 기준: `84a5f504fb59b010426b56b192839fb9b4b79b73`
- 상태: 구현 및 검증 진행 중

## 사용자 의도

사용자는 베타테스터가 남긴 과제와 아직 해결하지 못한 항목을 한꺼번에 서두르지
말고, 작은 공개 릴리스를 차례로 내면서 끝까지 처리하라고 승인했다.

이번 릴리스는 다음 기능 릴리스로 넘어가기 전에 배포 아티팩트 자체의 신뢰 경계를
강화한다. 존재 확인만으로 설치 wheel을 통과시키지 않고, 검토한 리소스의 정확한
byte가 실제 wheel에 들어갔는지 증명한다.

## 계획

1. 생산 검사기와 전용 회귀 테스트의 소유 파일을 분리해 병렬 구현한다.
2. manifest, ZIP 경로, 리소스 집합, byte 수, SHA-256, packaged mirror의
   정확한 일치를 하나의 계약으로 고정한다.
3. 버전·설치 문서·능력표·결정 기록·릴리스 노트를 갱신한다.
4. packaged resource를 동기화하고 focused/docs/full suite를 실행한다.
5. 독립 검수를 받은 뒤 exact-tree wheel을 만들고 fresh-install 생명주기를
   확인한다.
6. 앞선 릴리스가 공개된 순서대로만 PR·병합·tag·Release를 진행한다.

## 현재 구현 결정

- `assert_wheel_resources(wheel: Path)` 공개 진입점은 유지한다.
- 검사기는 wheel manifest의 raw byte가 저장소 manifest와 같은지 먼저
  확인한다.
- JSON은 duplicate key를 허용하지 않는 엄격한 형태로 읽는다.
- ZIP member 이름은 유일하고 상대적인 정규화 POSIX 경로여야 한다.
- manifest의 declared resource set과 wheel의 actual resource set은 정확히
  같아야 한다.
- 각 resource는 manifest byte 수, ZIP size, 실제 읽은 byte 수, SHA-256,
  저장소 mirror byte와 모두 일치해야 한다.
- 저수준 ZIP/UTF-8/JSON/schema/I/O 오류는 `WheelCheckError`로 제한한다.
- 압축 방식·순서·시간·권한·offset·whole-wheel reproducibility는 이번
  주장에 포함하지 않는다.

## 독립 검수에서 발견한 P1과 수정 방향

첫 독립 검수는 archive 안의 정확한 이름과 실제 설치 경로가 달라질 수 있는
두 가지 P1 우회를 재현했다.

1. 정상 lowercase 리소스 뒤에 대소문자만 다른 악성 member를 추가하면 기존
   검사는 통과했지만 Windows 추출 결과에서 검증된 파일이 덮였다.
2. 정상 리소스 뒤에
   `<dist>.data/purelib/wom_kit/_resources/<resource>` 또는 `platlib`
   별칭을 넣으면 기존 검사는 통과했지만 `pip install`이 이를 패키지 경로로
   이동시켜 POSIX와 Windows 모두에서 검증된 파일을 덮었다.

수정 계약:

- 모든 member에 Windows 대소문자 충돌 key를 적용한다.
- Win32 금지 문자, 끝 점/공백, 예약 장치명과 COM/LPT의 `¹²³` 별칭을
  거부한다.
- 현재 WOM-kit은 `.data` scheme이 필요 없는 pure wheel이므로 모든 최상위
  `<dist>.data/...` member를 보수적으로 거부한다.
- 실제 우회 fixture를 회귀 테스트로 남긴다.

## 병렬 소유권

- 생산 코드:
  `wom-kit/tools/check_wheel_install.py`
- 전용 테스트:
  `wom-kit/tests/test_wheel_install.py`
- 루트 감독자:
  버전, 문서, resource 동기화, 통합 테스트, 독립 검수, 후보 wheel

## 안전 경계

- 베타테스터 보관소는 읽기 전용이다.
- 다른 worktree와 기존 stash를 건드리지 않는다.
- 공개 순서는 `v0.3.286 -> v0.3.287 -> v0.3.288 -> v0.3.289`이다.
- 검증 결과가 생기기 전에 테스트 수, 해시, CI, tag 또는 공개 완료를
  주장하지 않는다.

## 현재 후보 검증 기록

- 전용 wheel 무결성 회귀: 20/20 통과
- 문서 계약 테스트: 143/143 통과
- packaged resource 동기화: v0.3.289, 102개 통과
- release readiness: 공개 링크, 한글 제품 언어, 공개 개인정보, runtime skill
  4/4 통과
- `py_compile`, staged/unstaged `git diff --check`: 통과
- 일반 독립 품질 검수: 남은 P1/P2 없음

독립 품질 검수는 WOM-kit README가 v0.3.288 MCP 오류 봉투를 “현재 릴리스
노트”라고 부르는 문서 P2 한 건도 발견했다. 현재 노트가 v0.3.289로 바뀐
상태에서 모호한 표현이므로 v0.3.288 릴리스 노트의 정확한 링크로 고쳤고,
문서 테스트·resource 동기화·release readiness를 다시 통과했다.

## 아직 완료되지 않은 검증

후보의 기반이 되는 v0.3.287 Python 3.10 호환 수정과 v0.3.288 최종 계보를
반영해 rebase한 뒤 다음을 처음부터 다시 실행해야 한다.

- complete source suite
- exact-tree clean wheel
- four entrypoints
- runtime skill lifecycle
- onboarding dry-run 및 approve
- strict Doctor
- PR/main/tag CI, GitHub Release, 비로그인 공개 다운로드

현재 후보 checkpoint는 rebase 가능한 로컬 구현 증거이며 공개 릴리스 완료
주장이 아니다.
