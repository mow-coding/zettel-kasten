# WOM-kit Python 도구 설치

상태: v0.3.292 GitHub wheel 및 objet 연결 수 일관성 체크포인트

WOM-kit은 명령줄 도구입니다. 일반 앱 프로젝트의 Python 의존성과 섞지 말고
별도의 격리된 Python 환경에 설치하는 것이 좋습니다.

## 권장 설치

정확한 WOM 릴리스에 붙은 검증된 wheel을 `uv`로 설치합니다.

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.292/wom_kit-0.3.292-py3-none-any.whl"
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
& "$HOME\.wom-tools\wom-kit\Scripts\python.exe" -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.292/wom_kit-0.3.292-py3-none-any.whl"
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
태그 안 버전, `origin/main` 계보, 동기화된 리소스 103개가 모두 맞아
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

기존 Windows 프로젝트 미러에서는 이전 CRLF checkout 때문에 raw-byte 관문을
통과하지 못할 수 있습니다. 승인된 `project-version-update`는 대상
commit의 추적 파일 전체를 정확한 blob으로 직접 다시 만듭니다. 시작 전에
Windows·macOS·Linux에서 충돌할 경로와 파일/폴더 전환을 검사하고, index를
다시 만든 뒤 원본 바이트와 리소스를 검증합니다. `git status`와 저장소
filter를 사용하지 않습니다. 폴더 scan은 entry 수 상한을 둔 streaming
방식이며, ignore되어 있고 이름 충돌이 없는 `wom-kit/src` shadow라도
쓰기 전에 차단합니다. 독점 lock/receipt 소유권과 source/pin checkpoint는
관찰한 변경을 감지하지만, 파일 단위의 원자적 compare-and-swap은 아닙니다.
따라서 외부 writer가 파일을 절대 덮지 않는다고 보장하지 않습니다.

모든 승인 전에 먼저 dry-run을 실행하세요. 그 다음 editor, 동기화 client,
backup 도구, 다른 모든 Git writer를 전체 업데이트 transaction 동안
멈추고, 멈춘 상태에서 다음처럼 승인해야 합니다.

```powershell
archive project-version-update <project-or-archive-root> --target vX.Y.Z --approve --reviewed-by <actor> --affirm-external-writers-quiescent --format json
```

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

v0.3.291의 실제 승인은 Windows에서만 가능합니다. WOM은 project,
source/`.git`, pin, lock, receipt 경로의 검증된 폴더 handle을
`FILE_SHARE_DELETE` 없이 계속 잡아 둡니다. 그래서 실행 중 다른 process가
그 폴더를 rename·삭제하거나 junction으로 바꿀 수 없습니다. receipt 상위
폴더와 최종 폴더가 없으면 한 단계씩 만들고 바로 hold하며, hold되지 않은
receipt root에는 영수증을 쓰지 않습니다.

POSIX에서도 읽기 전용 dry-run은 끝까지 실행됩니다. 다만 결과 status는
`preview_only_platform_unsupported`이고
`write_boundary.approval_platform_supported`는 `false`입니다. POSIX의 열린
directory descriptor는 경로 rename을 막지 못하므로 `--approve`는 차단되며,
Git과 전체 트리 작업이 처음부터 끝까지 descriptor-relative가 된 뒤에야
승인 지원을 검토할 수 있습니다.

runtime Agent Skill은 또 다른 별도 lifecycle입니다. Python 도구를
설치·업데이트해도 Skill이 자동 설치되지 않으며, `runtime-skill-install`도
Python CLI를 교체하지 않습니다.

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
