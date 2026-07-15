# WOM-kit Python 도구 설치

상태: v0.3.247 GitHub wheel 및 AI 운영자 아티팩트 우선 원칙 체크포인트

WOM-kit은 명령줄 도구입니다. 일반 앱 프로젝트의 Python 의존성과 섞지 말고
별도의 격리된 Python 환경에 설치하는 것이 좋습니다.

## 권장 설치

정확한 WOM 릴리스에 붙은 검증된 wheel을 `uv`로 설치합니다.

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.250/wom_kit-0.3.250-py3-none-any.whl"
archive --version
```

`uv tool install`은 도구 전용 환경을 만들고 패키지가 제공하는 명령을 꺼내
줍니다. WOM-kit은 `archive`, `wom`, `archive-mcp`, `wom-mcp` 네 명령을
설치합니다.

이번 릴리스는 WOM-kit을 PyPI에 공개하지 않습니다. 따라서 아직은
`pip install wom-kit`이 공식 명령이 아닙니다. 정확한 GitHub 릴리스 URL을
사용하면 설치 파일을 검토된 저장소 태그에 묶을 수 있습니다.

## 일반 pip 대안

일반 `pip`도 전용 가상환경 안에서는 사용할 수 있습니다.

```powershell
py -m venv "$HOME\.wom-tools\wom-kit"
& "$HOME\.wom-tools\wom-kit\Scripts\python.exe" -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.250/wom_kit-0.3.250-py3-none-any.whl"
& "$HOME\.wom-tools\wom-kit\Scripts\archive.exe" --version
```

이 환경은 도구 전용입니다. WOM 아카이브 폴더가 아니며 아카이브 안에 만들지
않습니다.

## wheel에 들어 있는 것

wheel에는 Python 명령과 그 명령이 실행될 때 필요한 자원이 함께 들어 있습니다.

- 검증과 검진이 사용하는 JSON 스키마,
- 개인·가족·회사·AI runtime 템플릿,
- 단계별로 읽는 `wom-archive` Agent Skill 묶음,
- 기본 zettel-kasten 규칙과 연결 유형,
- 현재 릴리스 신원 문서.

저장소의 원본 파일이 계속 정본입니다. 결정적으로 생성되는 manifest가 패키지
사본 각각의 정확한 바이트 길이와 SHA-256을 묶습니다.

## 설치가 하지 않는 일

설치만으로 다음 일은 일어나지 않습니다.

- 아카이브 생성 또는 수정,
- zet 본문 또는 오브제 바이트 읽기,
- 외부 서비스, 오브제 저장소, 외부 DB 호출,
- 자격증명 읽기,
- 내장 Agent Skill을 AI 호스트 설정 폴더에 설치,
- 생성된 그래프를 정본으로 지정하기.

아카이브 생성은 별도의 미리보기 우선 작업입니다.

```powershell
archive onboard --target-root <새-아카이브-폴더> --type personal --archive-id <아카이브-아이디> --principal-id <주체-아이디> --dry-run --format json
```

미리보기를 검토한 뒤에만 `--dry-run`을 `--approve`로 바꿉니다.

## 선택형 Agent Skill 활성화

Python 설치는 활성화 명령을 사용할 수 있게만 하며 자동 실행하지 않습니다.
Codex 사용자 범위 대상을 별도로 미리 봅니다.

```powershell
archive runtime-skill-install --dry-run --format json
```

반환된 정확한 계획만 승인하세요. 사용자·저장소·다른 호스트 범위, 업데이트,
상태 확인, 안전한 제거 방법은
[WOM 아카이브 Agent Skill 설치](runtime-skill-install.ko.md)를 보세요.

## 릴리스 검증

관리자는 다음 명령을 실행합니다.

```powershell
python wom-kit/tools/sync_package_resources.py --check
python wom-kit/tools/check_wheel_install.py --format json
```

두 번째 명령은 깨끗한 소스 사본에서 wheel을 만들고, manifest의 모든 자원을
검사하고, 새 가상환경에 설치하고, 네 실행 명령을 확인하고, 버릴 수 있는
호스트 폴더에서 Agent Skill 미리보기·설치·검증·제거를 실행하고, 버릴 수
있는 아카이브를 미리 본 뒤 실제 생성하고, 엄격한 검진까지 실행합니다.
이 전체 검사가 통과한 wheel만 릴리스 자산으로 보존할 수 있습니다.
