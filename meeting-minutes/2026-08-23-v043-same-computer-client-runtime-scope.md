# 2026-08-23 v0.4.3 같은 컴퓨터의 클라이언트 실행 범위

## 대화와 문제 제기

사용자는 WOM 개발진과 여러 베타테스터 클라이언트가 같은 Windows 사용자
계정의 서로 다른 프로젝트 폴더를 사용할 때, 개발진이 공용 WOM 명령을
업데이트하면 다른 클라이언트가 직접 업데이트하지 않았는데도 새 버전을 보게
되는 혼란을 지적했다. 핵심 질문은 GitHub Release의 자동 설치 여부가 아니라,
한 컴퓨터의 공용 실행 파일과 프로젝트별 작업 환경의 경계였다.

처음 답변은 GitHub Release와 설치를 함께 설명해 질문의 핵심을 흐렸다. 이를
정정하고 현재 로컬 상태와 실제 실행 경계를 다시 확인했다.

## 2026-08-23 읽기 전용 확인

- Windows PATH가 고른 공용 실행 파일은 사용자 로컬 `.local/bin` 아래의
  `archive.exe`였다. 공개 기록에는 실제 사용자 폴더 이름을 남기지 않는다.
- 공용 `archive --version`은 v0.4.2였다.
- Basoon의 `parent_of_archive/.zettel-kasten/source`와 프로젝트 핀은 v0.4.0이었다.
- v0.4.3은 개발 worktree에서만 실행했으며 공용 도구에는 설치하지 않았다.
- v0.4.3 소스로 Basoon을 읽기 전용 검사한 결과는 running v0.4.3과 project
  v0.4.0을 분리해 보고했고, `running_version_differs_from_project_source`와
  `project_scoped_bridge_available`을 반환했다.
- 이 bridge는 검증된 프로젝트 버전으로 `version` 명령을 한 번 실행하는 좁은
  경계이며 일반 쓰기 명령용 프로젝트 샌드박스는 아니다.

## 결론

`uv tool install`이 만드는 Python 환경은 애플리케이션 의존성과 분리되지만,
그 환경이 PATH에 노출하는 `archive.exe`는 같은 Windows 사용자 계정의 여러
폴더와 세션이 공유할 수 있다. 따라서 공용 도구 교체는 폴더별 업데이트가
아니며, 프로젝트별 격리를 증명하지 않는다.

WOM 클라이언트의 업데이트 여부는 `archive --version` 하나로 판정하지 않는다.
공용 실행 버전과 함께 `archive version <project-or-archive-root> --format json`의
프로젝트 source mirror, pin, runtime alignment를 확인해야 한다.

## v0.4.3 릴리스 운영 결정

- 개발·wheel 설치 검증은 공유 PATH를 바꾸지 않는 전용 임시 가상환경과 명시적
  실행 파일 경로로 수행한다.
- 이 개발 세션은 공용 v0.4.2 도구를 v0.4.3으로 교체하지 않는다.
- GitHub Release와 wheel 검증, 공용 CLI 교체, 프로젝트 source/pin 업데이트는
  서로 다른 결과로 기록한다.
- Basoon 실제 업데이트는 Basoon 프로젝트에 결속된 exact-human workflow로만
  수행한다.
- 같은 계정에서 완전히 독립된 클라이언트 실행이 필요하면 프로젝트별 전용
  가상환경 또는 별도 OS 사용자 경계가 필요하다. 현재 WOM은 일반 명령 전체에
  대한 자동 폴더별 샌드박스를 제공한다고 주장하지 않는다.

## 영향받은 파일

- `meeting-minutes/2026-08-23-v043-same-computer-client-runtime-scope.md`
- `wom-kit/docs/archive-infra-decision-log-2026-08-23-v043-client-runtime-scope.md`
- `wom-kit/docs/python-tool-install.md`
- `wom-kit/docs/python-tool-install.ko.md`
- `wom-kit/docs/version-truth-source.md`
- `wom-kit/docs/releases/v0.4.3.md`

실제 Basoon 데이터, 공용 Python 도구, PATH, provider, 자격증명은 변경하지 않았다.
