# WOM 아카이브 Agent Skill 설치

상태: v0.3.244 미리보기 우선, 사람 승인형 로컬 호스트 수명주기

## 무엇을 하는 기능인가

WOM-kit에는 이미 `wom-archive` Agent Skill이 들어 있습니다. 이 명령은
그 스킬 묶음을 AI 호스트의 스킬 폴더 한 곳에 복사해, 사람이 파일을 하나씩
옮기지 않아도 호스트가 찾을 수 있게 합니다.

Python 도구 설치와 AI 호스트 스킬 설치는 서로 다른 작업입니다.

- `uv tool install` 또는 전용 `pip` 가상환경은 WOM-kit 명령을 설치합니다.
- `runtime-skill-install --approve`는 사람이 검토한 스킬 묶음을 선택한
  호스트 스킬 폴더에 씁니다.

첫 번째 작업을 했다고 두 번째 작업까지 승인된 것은 아닙니다.

## Codex 사용자 범위 설치

현재 Codex 공식 문서는 사용자 스킬을 `$HOME/.agents/skills`에서 찾고,
저장소 전용 스킬을 해당 저장소 안의 `.agents/skills`에서 찾습니다.
WOM-kit의 `--host codex`도 이 위치를 사용하며, 예전 `.codex/skills`를
새 설치 대상으로 사용하지 않습니다.

먼저 현재 상태만 확인합니다.

```powershell
archive runtime-skill-status --format json
```

설치를 미리 봅니다.

```powershell
archive runtime-skill-install --dry-run --format json
```

결과의 `target`, `source_package`, `installation`, `would_write`,
`operation_plan_sha256`을 검토합니다. 그다음 방금 본 계획만 승인합니다.

```powershell
archive runtime-skill-install `
  --approve `
  --reviewed-by person:local-owner `
  --expected-plan-sha256 <operation_plan_sha256> `
  --format json
```

마지막으로 다시 확인합니다.

```powershell
archive runtime-skill-status --format json
```

정상 완료 상태는 `managed_current`입니다. 보통 Codex가 변경된 스킬을
자동으로 찾으며, 목록에 나타나지 않을 때만 다시 시작하면 됩니다.

## 저장소 범위 설치

특정 저장소에서 작업할 때만 스킬을 보이게 하려면 다음처럼 미리 봅니다.

```powershell
archive runtime-skill-install `
  --host codex `
  --scope repo `
  --repo-root <repository-root> `
  --dry-run `
  --format json
```

승인할 때도 같은 대상 옵션을 사용합니다. 실제 대상은
`<repository-root>/.agents/skills/wom-archive`이며, 저장소가 없거나 심볼릭
링크이거나 경로가 저장소 밖으로 나가면 차단합니다.

## 직접 지정한 다른 호스트

WOM-kit은 다른 제품의 현재 사용자 폴더를 추측하지 않습니다. 다른 호스트나
시험 환경은 스킬 폴더를 직접 지정해야 합니다.

```powershell
archive runtime-skill-install `
  --host custom `
  --scope custom `
  --skills-root <skills-root> `
  --dry-run `
  --format json
```

표준 Agent Skill 묶음을 복사하지만, 모든 호스트가 지정한 폴더를 실제로
읽는다고 주장하지는 않습니다.

## 상태 뜻

| 상태 | 뜻 | 안전한 다음 작업 |
| --- | --- | --- |
| `absent` | 대상 스킬 폴더가 없습니다. | 설치를 미리 봅니다. |
| `managed_current` | 모든 파일이 WOM 설치 목록 및 현재 내장본과 같습니다. | 할 일이 없습니다. |
| `managed_outdated` | 설치 파일은 손대지 않았지만 더 최신 내장본이 있습니다. | 같은 설치 명령으로 업데이트를 미리 봅니다. |
| `unmanaged_conflict` | 폴더는 있지만 WOM 소유권 근거가 없습니다. | 덮어쓰거나 지우지 말고 사람이 확인합니다. |
| `managed_drift` | WOM이 설치한 파일·폴더·링크가 설치 목록과 다릅니다. | 사람의 변경을 보존하고 직접 검토합니다. |
| `managed_invalid` | 설치 목록이 깨졌거나 현재 대상 계약과 맞지 않습니다. | 아무것도 쓰거나 지우지 않습니다. |

같은 설치 명령이 첫 설치와 검증된 업데이트를 처리합니다. 소유권을 모르는
폴더를 멋대로 인수하지 않고, 사람이 고친 관리 파일도 덮어쓰지 않습니다.

## 설치 목록

승인 후 쓰기는 스킬 폴더 안에 `.wom-kit-install.json`을 남깁니다.
여기에는 WOM-kit 버전, 호스트와 범위, 스킬 묶음 해시, 설치 시각, 안전한
검토자 아이디, 파일 이름·바이트 수·SHA-256이 들어갑니다.

목록 본문의 SHA-256도 함께 남겨, 목록 자체를 실수로 또는 손으로 고친
경우에도 안전하게 차단합니다.

절대 원본/대상 경로, 아카이브 데이터, 프롬프트, 대화 내용, 외부 서비스
계정, 토큰, 자격증명, 비밀정보는 기록하지 않습니다.

업데이트와 제거는 이 목록을 바탕으로 관리 파일 전체를 다시 검사합니다.
검토한 계획도 대상 위치 해시, 내장 스킬, 이전 상태, 설치 목록 해시를 함께
묶으므로 오래된 승인은 차단됩니다.

## 안전한 제거

먼저 제거를 미리 봅니다.

```powershell
archive runtime-skill-uninstall --dry-run --format json
```

방금 반환된 계획만 승인합니다.

```powershell
archive runtime-skill-uninstall `
  --approve `
  --reviewed-by person:local-owner `
  --expected-plan-sha256 <operation_plan_sha256> `
  --format json
```

제거는 손대지 않은 WOM 관리 폴더에만 작동합니다. 검증된 폴더를 활성 스킬
폴더 밖으로 먼저 옮긴 뒤 삭제하므로, 청소가 실패해도 스킬이 계속 활성
상태로 남지는 않습니다. 소유권을 모르는 폴더나 사람이 고친 스킬은 절대
지우지 않습니다.

## 안전 경계

이 명령들은 내장 공개 스킬과 선택한 대상 폴더만 읽고, 로컬 경로는 기본으로
가립니다. 네트워크, 외부 서비스, 모델, DB, 오브제 저장소, 자격증명을
호출하지 않으며 WOM 아카이브, zet, objet, 관계, 영수증도 읽거나 쓰지
않습니다. 생성 그래프나 색인을 만들지 않고 MCP 쓰기 도구도 노출하지
않습니다. 승인 후 쓰기 직전에는 전용 잠금 안에서 계획을 다시 검사합니다.

PyPI 공개와 일반 `pip install wom-kit`은 여전히 별도 미래 작업입니다.
조직 단위 재사용 배포를 위한 Codex plugin도 다음 배포 선택지이며,
v0.3.244는 좁고 안전한 로컬 스킬 수명주기만 제공합니다.
