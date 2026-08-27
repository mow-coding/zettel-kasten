# WOM-kit Python 도구 설치

상태: v0.4.10 검증된 GitHub wheel 및 제한된 배치 운용

WOM-kit은 명령줄 도구입니다. 일반 앱 프로젝트의 Python 의존성과 섞지 말고
별도의 격리된 Python 환경에 설치하는 것이 좋습니다.

## 한 Windows 계정에서 여러 클라이언트 폴더를 쓸 때

`uv tool`의 격리 환경은 Python 의존성을 다른 앱과 분리하지만, PATH에 노출한
`archive.exe`를 현재 폴더 전용으로 만들지는 않습니다. 같은 Windows 계정에서
같은 실행 파일을 찾는 모든 프로세스는 다음 명령 실행부터 교체된 버전을 볼 수
있습니다. 따라서 `archive --version`은 현재 실행한 공용 도구 버전일 뿐, 특정
클라이언트 프로젝트가 업데이트됐다는 증거가 아닙니다.

같은 컴퓨터의 베타 클라이언트는 두 층을 함께 확인해야 합니다.

```powershell
archive --version
archive version <project-or-archive-root> --format json
```

두 번째 결과의 project source, pin, `project_runtime`을 보고 그 클라이언트의
업데이트 필요 여부를 결정합니다. 개발·릴리스 검증 때는 별도 임시 가상환경에
wheel을 설치하고 그 환경의 `Scripts\archive.exe`를 정확한 경로로 실행해야
합니다. 테스트 과정에서 사용자 공용 PATH 도구를 교체하지 않습니다. 같은
검증된 project updater는 선택한 프로젝트의
`.zettel-kasten/runtimes/vX.Y.Z/`에 정확한 릴리스 wheel을 설치하고
`.zettel-kasten/bin/archive.cmd`를 활성화합니다. 이후 그 프로젝트의 일반 WOM
명령은 이 launcher로 실행합니다. 다른 프로젝트 폴더와 사용자 공용 PATH
실행기는 바뀌지 않습니다. 이 경계는 WOM 명령의 프로젝트 런타임 격리이며,
Windows 사용자 권한이나 WOM 밖의 프로그램까지 격리한다는 뜻은 아닙니다.

아래 v0.4.10 URL은 조건부 계약이며 공개 자산이 실제로 존재한다는 증거가
아닙니다. 정확히 일치하는 GitHub Release가 존재하고 검증된 wheel을 자산으로
나열한 뒤에만 사용하세요. 소스 상태와 릴리스 증거의 구분은
[v0.4.10 릴리스 노트](releases/v0.4.10.md)를 보세요.

설치된 이전 client에는 v0.4.10의 인증된 배치 intake-to-capture 경로가
없을 수 있습니다. 저장소 파일만 업데이트해도 분리된 `uv tool`
또는 가상환경 wheel은 바뀌지 않습니다. 검증된 v0.4.10 자산이 실제로 생긴 뒤 그
정확한 wheel을 설치하고 새 프로세스를 시작하세요.

## 권장 프로젝트 부트스트랩

정확한 WOM GitHub Release가 실제로 존재하고 검증된 wheel을 자산으로 나열한
뒤에만 임시 부트스트랩을 만드세요. 버전이 들어간 URL만으로 파일이 실제 공개되었다는
증거가 되지는 않습니다. 이 임시 환경은 검사할 프로젝트·보관함 밖에 두어야
프로젝트 입력이나 updater 충돌 항목이 되지 않습니다.

```powershell
$womBootstrapRoot = Join-Path $env:LOCALAPPDATA "WOM\bootstrap-v0410"
py -m venv $womBootstrapRoot
& "$womBootstrapRoot\Scripts\python.exe" -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.10/wom_kit-0.4.10-py3-none-any.whl"
& "$womBootstrapRoot\Scripts\archive.exe" --version
```

새 프로세스가 정확히 `archive 0.4.10`을 보고하면 그 명시적 부트스트랩으로
`project-version-update`를 실행합니다. 승인 성공 뒤 프로젝트 런타임을
검증하고 해당 launcher를 사용합니다.

```powershell
.\.zettel-kasten\bin\archive.cmd version <project-or-archive-root> --format json
.\.zettel-kasten\bin\archive.cmd git-backup-plan <archive-root> --remote origin --dry-run --format json
```

이 명령은 쓰기 없이 체크아웃된 symbolic branch와 remote ref를 관찰합니다.
정확한 승인·resume 경로만 결속된 선택을 commit하고 non-force push할 수
있습니다. 결과를 해석하거나 승인하기 전에 [Git 백업 계획과 재조정
계획](git-backup-plan.md)을 읽으세요.

`uv tool install`은 도구 전용 환경을 만들고 패키지가 제공하는 명령을 꺼내
줍니다. WOM-kit은 `archive`, `wom`, `archive-mcp`, `wom-mcp` 네 명령을
설치합니다. 이 환경은 의존성 면에서는 격리되지만, 밖으로 꺼낸 명령은 사용자
PATH가 공유하는 실행점이지 프로젝트 폴더 전용 명령이 아닙니다.

이번 릴리스는 WOM-kit을 PyPI에 공개하지 않습니다. 따라서 아직은
`pip install wom-kit`이 공식 명령이 아닙니다. 정확한 GitHub 릴리스 URL을
사용하면 설치 파일을 검토된 저장소 태그에 묶을 수 있습니다.

### 설치된 이전 전역 CLI 교체

v0.4.10 Release와 wheel이 실제로 공개된 뒤, 격리된 `uv tool` 환경을 교체하고
새 프로세스에서 결과를 확인합니다.

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.10/wom_kit-0.4.10-py3-none-any.whl"
archive --version
```

공식 `uv` 계약상 같은 `uv tool install`을 다시 실행하면 보통 `uv`가 관리하던
기존 도구를 교체합니다. `uv`가 관리하지 않는 실행 파일 충돌을 명시적으로
보고하고 사람이 그 실행 파일을 검토한 경우에만 `--force`를 사용하세요. 이
옵션은 `uv`가 관리하지 않는 실행 파일도 교체할 수 있습니다. [공식 `uv tool
install` 문서](https://docs.astral.sh/uv/reference/cli/#uv-tool-install)를 보세요.

결과는 정확히 `archive 0.4.10`이어야 합니다. 이것은 전역 CLI만 바꾸는
부트스트랩입니다. project-local `.zettel-kasten/source` mirror와 version pin은
바꾸지 않습니다. project updater는 별도의 exact-human workflow이고,
collision 변경과 bytecode repair는 계속 고정 차단됩니다. pin을 손으로 고치지
마세요. [Project Version Update](project-version-update.md)와 [업그레이드
가이드](../../UPGRADE.ko.md)를 보세요.

## 일반 pip 대안

일반 `pip`도 전용 가상환경 안에서는 사용할 수 있습니다.

```powershell
py -m venv "$HOME\.wom-tools\wom-kit"
& "$HOME\.wom-tools\wom-kit\Scripts\python.exe" -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.10/wom_kit-0.4.10-py3-none-any.whl"
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
릴리스 전 wheel 검사는 그 manifest가 검토된 저장소 manifest와 byte 단위로
같은지, packaged resource 집합이 정확한지, 각 리소스가 선언된 digest와 저장소
packaged mirror 모두에 정확히 일치하는지도 검증합니다.

## 설치가 하지 않는 일

설치만으로 다음 일은 일어나지 않습니다.

- 아카이브 생성 또는 수정,
- zet 본문 또는 오브제 바이트 읽기,
- 외부 서비스, 오브제 저장소, 외부 DB 호출,
- 자격증명 읽기,
- 내장 Agent Skill을 AI 호스트 설정 폴더에 설치,
- 생성된 그래프를 정본으로 지정하기.

## 프로젝트와 전역 명령의 버전이 다를 때

`archive version <project-or-archive-root> --format json`은 현재 실행 중인
import와 프로젝트의 소스 미러·버전 핀을 비교합니다.
`project-version-update`가 성공해도 `PATH`가 선택하는 Python 도구를 몰래
교체하지는 않습니다.

v0.3.291부터 프로젝트 미러와 핀끼리는 일치하지만 현재 import만 다르면
`project_scoped_bridge_available` 상태를 보고할 수 있습니다. 신뢰할 수 있는
로컬 디버깅에서는 `--no-redact-local-paths`로 정확한 구조화 bridge argv를
받을 수 있습니다. 단, 프로젝트 안의 실제 경로와 `.git` 메타데이터,
worktree 원본 바이트·index·flag, 닫힌 import 트리, 정확한 annotated tag,
태그 안 버전, `origin/main` 계보, 리소스 manifest에 기록된 모든 동기화 리소스가 맞아
`runtime_alignment.integrity.verified`가 true여야 합니다. Python `-I -S`
bootstrap은 예상 commit·tag·wrapper blob·리소스 blob을 argv에 묶고,
검증한 wrapper를 메모리에서 실행하며 읽기 전용 `version` 명령만
허용합니다. 프로젝트 source root는 `sys.path`에 넣지 않습니다. 프로젝트
alias를 지운 뒤 정확한 object id 전용 finder가 `wom_kit`만 불러오므로,
검증 후 생긴 최상위 `yaml` 또는 `sqlite3` shadow는 실행될 수 없습니다.
`-S`는 bootstrap 전에 `site` 초기화, 실행 가능한 `.pth`,
`sitecustomize`를 막습니다. 검증 뒤에는 표준 라이브러리 `sysconfig`가
알려 준 `purelib`·`platlib` 경로만 `site.py` 처리 없이 추가합니다.
네트워크와 origin URL 값은 사용하지 않습니다. 이 argv는
검증된 프로젝트 소스를 한 번 실행하는 경로일 뿐이며, 전역 도구를
업데이트·재설치·제거하지 않습니다. WOM은 그 도구가 pip, uv, pipx,
editable 설치 중 무엇으로 관리되는지도 추측하지 않습니다.

기존 프로젝트 미러에서는 이전 CRLF checkout 때문에 raw-byte 관문을
통과하지 못할 수 있습니다. `project-version-update --dry-run`은 대상
commit의 추적 파일 전체를 검사합니다. 시작 전에
Windows·macOS·Linux에서 충돌할 경로와 파일/폴더 전환을 검사하고, index를
다시 만든 뒤 원본 바이트와 리소스를 검증합니다. `git status`와 저장소
filter를 사용하지 않습니다. 폴더 scan은 entry 수 상한을 둔 streaming
방식이며, ignore되어 있고 이름 충돌이 없는 `wom-kit/src` shadow라도
쓰기 전에 차단합니다. 독점 lock/receipt 소유권과 source/pin checkpoint는
관찰한 변경을 감지하지만, 파일 단위의 원자적 compare-and-swap은 아닙니다.
따라서 외부 writer가 파일을 절대 덮지 않는다고 보장하지 않습니다.

v0.4.3의 승인은 검토된 Windows native exact-human 경로에서만 가능합니다.
계획은 현재 source·pin, 대상 annotated tag·commit, rollback 상태, 영수증의
approval reference를 묶습니다. 취소·drift·불명확·미지원 플랫폼 시도는 project를
바꾸지 않습니다. collision 변경과 bytecode repair는 별도의 fixed-closed
표면으로 남습니다.

v0.3.314부터 명시한 output은 시작 직후 내용 없는 `operation_ref`도 출력합니다.
호출 화면이 timeout으로 먼저 끝나면 updater를 중복 실행하지 말고, 그 reference와
정확한 시작 root로 `operation-control` status 또는 제한된 wait를 실행하세요.
archive root에서 시작한 update의 output은 새
`.wom-scratch/diagnostics/*.json` 경로를 사용합니다. cancel과 resume은 구현되지
않았고, status는 update 완료 후 새 프로세스의 `archive version` 확인을 대신하지
않습니다.

결과에는 `external_writer_quiescence_required: true`,
`external_writer_quiescence_affirmed: true`,
`atomic_file_compare_and_swap: false`,
`checkpointed_change_detection: true`가 기록됩니다. v0.2 영수증에는
`external_writer_quiescence: {affirmed: true, scope:
complete_project_version_update_transaction}`가 남습니다. 기존 v0.1
영수증도 계속 호환됩니다. 진짜 file-handle/descriptor 기반 CAS는 향후
과제입니다. 이 프로젝트 범위 업데이트는 전역 console 도구를 재설치하거나
교체하지 않습니다.

설정 checkpoint digest는 effective Git config와 정확히 `GIT_ASKPASS`,
`GIT_PROXY_COMMAND`, `GIT_SSH`, `GIT_SSH_COMMAND`만 환경 변수로 묶습니다.
선택된 Git 실행 파일, `PATH`, `HTTP_PROXY`, `HTTPS_PROXY`,
`SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `SSH_AUTH_SOCK`, `HOME`, 그 밖의
비-Git toolchain·transport 환경은 digest에 묶지 않습니다. 이 값들도
신뢰할 수 있고 안정적인 운영 전제조건으로 유지해야 합니다. rollback
직전 묶인 설정 digest가 달라지면 복원을 건너뛰고 소유한 lock을 보존하며
rollback을 불완전 상태로 보고합니다.

과거 v0.3.291 writer는 Windows에서만 가능했습니다. WOM은 project,
source/`.git`, pin, lock, receipt 경로의 검증된 폴더 handle을
`FILE_SHARE_DELETE` 없이 계속 잡아 둡니다. 그래서 실행 중 다른 process가
그 폴더를 rename·삭제하거나 junction으로 바꿀 수 없습니다. receipt 상위
폴더와 최종 폴더가 없으면 한 단계씩 만들고 바로 hold하며, hold되지 않은
receipt root에는 영수증을 쓰지 않습니다.

v0.4.3에서도 읽기 전용 dry-run은 끝까지 실행됩니다. POSIX 결과 status는
`preview_only_platform_unsupported`이고
`write_boundary.approval_platform_supported`는 `false`입니다. Windows native
exact-human writer는 실행하지 않습니다.

runtime Agent Skill은 또 다른 별도 lifecycle입니다. Python 도구를
설치·업데이트해도 Skill이 자동 설치되지 않으며, `runtime-skill-install`도
Python CLI를 교체하지 않습니다.

아카이브 생성은 별도의 미리보기 우선 작업입니다.

```powershell
archive onboard --target-root <새-아카이브-폴더> --type personal --archive-id <아카이브-아이디> --principal-id <주체-아이디> --dry-run --format json
```

v0.4.3에서는 미리보기에서 멈춥니다. 온보딩 승인은 대상·템플릿·제공자
정보를 읽기 전에 `compound_exact_human_approval_binding_required`로 차단되며
아카이브를 만들지 않습니다.

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
검사한 뒤 새 가상환경에 설치합니다. 두 CLI의 버전 출력을 실제로 실행하고,
두 MCP 별칭에는 초기화·도구 목록·EOF 절차를 실행합니다. 이때 엄격한 UTF-8,
비어 있는 표준 오류, 제한된 출력량과 실행 시간, 하위 프로세스 격리, 완전하고
바이트 단위로 같은 도구 목록을 요구합니다. 이어서 버릴 수 있는 호스트
폴더에서 Agent Skill 미리보기·설치·검증·제거를 실행합니다. 아카이브
온보딩은 미리보기만 정상 실행하고, 실제 쓰기 요청은 파일을 하나도 만들지
않은 채 고정 차단되는지 검증합니다. 엄격한 검진은 설치된 엔트리포인트로
저장소의 가짜 아카이브 fixture를 검사합니다. v0.4.1부터는 그 합성 fixture의
두 번째 임시 사본에서 격리 설치된 wheel만 사용해 준비된
`zettel-objet-link` 계획, 정확히 승인된 `written` 결과, canonical 문서에
추가된 정확한 object 링크, 바뀌지 않은 Markdown 본문 시작 바이트, 정확한
snapshot, 스키마에 맞는 v0.2 영수증, 영수증 조회 성공까지 검증합니다.
JSON 결과는
`wom-kit/wheel-install-check/v0.3`을 사용하고 온보딩 쓰기 상태를
`fixed_closed`로, Letter 140 설치 실행 근거를 별도로 기록합니다. 즉,
v0.4가 새 실제 아카이브를 만들었다고 주장하지 않습니다. 이 전체 검사가
통과한 wheel만 릴리스 자산으로 보존할 수 있습니다.
