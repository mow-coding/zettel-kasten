# 2026-08-23 v0.4.3 통합과 릴리스 준비 근거

## 통합 결과

v0.4.3 공통 exact-operation 기반, 프로젝트 업데이트, Git backup writer,
feedback CAS/supersession, Letter 138 `source_properties` 복구를 하나의
`codex/v0.4.3-recovery` 브랜치에 통합했다.

충돌은 승인 operation enum/label과 현재·역사적 command inventory 및 공개 문서에
한정됐다. 최종 parser-derived inventory는 다음과 같다.

- canonical executable commands: 315;
- alias invocation paths: 259;
- total invocation paths: 574;
- approval available: 38;
- approval fixed closed: 76;
- approval not exposed: 201;
- conditional approval scopes: 1 (`migrate --target notion-source-properties`);
- unmatched fixed-close entries: 0.

## 자동 테스트

- Letter 138, command inventory, Letter 137 경계, v0.4.0-v0.4.3 릴리스 문서,
  capability 문서 통합 회귀: 242 tests passed.
- exact manifest, 선형 checkpoint, Git 대형 트리/writer, Letter 139 CLI와 plan,
  feedback draft CAS/supersession 통합 회귀: 93 tests passed in 387.047 seconds.
- 대형 Git 테스트는 8,192개 변경 분할, 40,000 ignored-file 경계, commit/push
  직후 중단, same-claim resume, remote race와 drift fail-close를 포함했다.
- release readiness의 공개 링크, 한국어 제품 용어, 민감정보, runtime skill
  검사는 모두 통과했다.

## Letter 138 실제 자료 읽기 전용 재검증

통합된 v0.4.3 소스로 전체 검증 대상 mirror를 두 번 읽었다. 첫 번째 pass는
내용을 쓰지 않고 exact acceptance candidate를 계산했고, 두 번째 pass는 그
candidate를 다시 결속해 verified plan을 만들었다.

- total source pages: 11,585;
- mapped/backfill: 8,566;
- already equal: 0;
- unmapped: 2,882;
- human review: 137;
- review reasons: legacy root without properties 110, indeterminate property 27;
- unexplained populated-property omissions: 0;
- unexplained populated-property-type omissions: 0;
- manifest effects: 8,566;
- acceptance verified: true;
- zero silent omission: true;
- first status: 0.000 seconds;
- maximum progress gap: 1.765 seconds;
- two-pass elapsed: 448.641 seconds;
- writes, provider calls, private output reflection: none.

Content-free bindings:

- acceptance: `sha256:11d4c132fd5f74f782d0b94eac6e6228de25bc59e6712de057d91517b20bef7b`;
- classification: `sha256:261ba9ae2663ab218f3533042e543a9f8e8d89ecf6398c3f0c81e0c56321c18f`;
- unresolved source set: `sha256:e2528253767988022e1850b2f3e47c5dee71bf06d50023f33ebdffa57e5c7ccb`.

## 격리 wheel 검증

`tools/check_wheel_install.py`가 새 임시 가상환경을 만들고 공용 PATH 설치를
교체하지 않은 채 wheel을 설치·검증한 뒤 그 임시 환경을 제거했다.

- wheel: `wom_kit-0.4.3-py3-none-any.whl`;
- SHA-256: `657fcac68ea59f25350fd4264f8b61c7717349f9e38e9c3a5c3c7674f9aabf55`;
- package resources: 161/161, 669,174 bytes;
- wheel files: 225;
- CLI entrypoints `archive` and `wom`: v0.4.3 agreement;
- MCP entrypoints `archive-mcp` and `wom-mcp`: v0.4.3, 130-tool inventories
  byte-identical;
- installed Letter 140 exact-link smoke, runtime skill lifecycle, onboarding
  preview, strict Doctor: passed;
- onboarding write: expected fixed-close.

같은 Windows 계정의 공용 `archive` v0.4.2는 교체하지 않았다. 실제 Letter 138
apply, native approval, rollback drill, 검증 대상 project update, Git backup과 feedback
resolved 상태 갱신은 이 기록 시점에는 아직 수행하지 않았다.

## 재개 후 독립 감사와 후보 근거 무효화

컴퓨터 중단 뒤 작업을 재개하면서 PR #77을 병합하기 전에 프로젝트 updater를
다시 독립 추적했다. 그 결과, 위 자동 테스트와 wheel 검증은 당시 소스의 역사적
결과로는 유효하지만 v0.4.3 릴리스 완료 근거로는 더 이상 사용할 수 없다고
판정했다. 이후 코드가 바뀌므로 위 후보 wheel과 SHA-256도 폐기한다.

확인된 병합 차단 사유는 다음과 같다.

- 기존 흐름은 exact-human 승인 뒤에 tag와 `origin/main`을 fetch하여, 승인 대상에
  없던 commit과 runtime policy가 실제 적용 대상으로 들어올 수 있었다.
- 기존 runtime 재사용은 receipt의 과거 boolean과 실행 파일 존재만 믿어, 보존
  artifact나 설치 payload가 바뀐 상태를 실제 새 프로세스로 다시 검증하지 않았다.
- 최초 runtime 설치는 WOM wheel만 고정하고 PyYAML 등 의존성은 live pip index에
  맡겨, 같은 v0.4.3 승인으로 서로 다른 dependency bytes가 설치될 수 있었다.
- `index`는 승인 플래그 없이 SQLite를 쓰므로 project runtime mismatch guard를
  우회했고, updater의 공식 별칭 두 개는 반대로 잘못 차단됐다.
- runtime materializer가 반환 전에 실패하고 내부 삭제까지 실패하면 orphan을
  outer rollback이 보지 못한 채 성공으로 기록할 수 있었다.

교정 결정은 승인 창을 lock-held transaction 안으로 옮겨 승인 전에 release
evidence를 전부 준비하고 승인 후 네트워크를 0회로 만드는 것이다. Runtime은
tagged exact supply lock의 PyYAML 6.0.3 및 unicodedata2 17.0.1 Windows CPython
3.12 wheels까지 size/hash로 결속하고, offline/no-deps 설치와 retained-artifact,
installed-payload, fresh-process 재검증을 모두 요구한다. Runtime-root snapshot이
원상 복귀하지 않으면 rollback incomplete로 남기고 update lock을 보존한다.

이 교정의 focused 테스트와 전체 CI, 새 wheel 생성·해시 검증이 끝나기 전까지
v0.4.3은 계속 미출시이며 실제 개인 프로젝트 apply, provider call, 공용 PATH 교체는 없다.

## 재개 후 승인·트랜잭션 증거 경계 결정

내구 트랜잭션 통합 중 기존 v0.3 프로젝트 업데이트 영수증이 승인 뒤에 생성되는
`approval_id`, 승인 authority digest, 실행 시각을 본문에 포함한다는 충돌을
확인했다. 이 바이트들은 네이티브 사람 승인 전에 존재하지 않으므로, 해당
영수증 전체를 승인 전 immutable intent의 exact postimage로 결속할 수 없다.

다음 경계로 교정한다.

- 프로젝트 업데이트 디스크 영수증은 예약 단계에서 고정한 transaction reference와
  생성 시각, exact plan SHA-256, target binding SHA-256을 포함하는 정적 문서로 만든다.
- 승인 뒤에만 생기는 `approval_id`와 authority digest는 정적 영수증 본문에 넣지
  않고, 성공한 authenticated claim과 hash-chained transaction journal에 기록한다.
- writer는 정적 영수증을 포함한 모든 domain postimage를 검증하고
  `domain_committed`까지 남긴 뒤에만 성공을 반환한다.
- workflow가 claim을 durable `succeeded`로 만든 다음 bounded finalizer가 같은
  claim reference를 journal의 `claim_succeeded`에 결속하고, 그 뒤에만
  `ready_to_unlock`, exact lock 제거, `lock_released`를 진행한다.
- CLI 결과에는 동적 승인 요약을 계속 제공할 수 있지만, 디스크 영수증의
  preapproval exactness와 혼동하지 않는다.

이 결정은 승인받지 않은 동적 바이트를 immutable intent에 끼워 넣거나, 반대로
영수증 postimage 검사를 약화하는 두 가지 오류를 모두 피한다. 기존
`exact_human_approval_link`는 source-fidelity archive 내부 경계에 한정되어 있고
프로젝트 updater의 프로젝트 root와 approval archive root가 다를 수 있으므로
이 통합을 위해 범위를 확장하지 않는다.

추가로 claim을 durable `succeeded`로 바꾼 직후 finalizer 전에 hard exit가 나는
창을 확인했다. 기존 resume은 `started` claim만 다시 열 수 있으므로 이 경우
writer를 재실행하지 않는 succeeded-claim tail recovery를 추가했다. 이 경로는
동일 context와 authenticated claim, transaction checkpoint를 재검증한 뒤 bounded
finalizer만 실행하며 native 승인 창과 domain writer를 다시 호출하지 않는다.
관련 exact-human-approval 전체 focused 검증은 44 tests와 27 subtests가 통과했다.

## 승인 후 로컬 Git 명령 경계 강화

재개 감사에서 현재 materializer 자체는 checkout/filter가 아니라 검증한 blob을 직접
쓰고 `read-tree`, `update-ref` 등 로컬 plumbing만 사용한다는 것을 재확인했다. 다만
실행기가 알려진 transport verb만 거부하면 미래 변경에서 `remote update`나
`archive --remote` 같은 우회형 네트워크 명령이 들어올 수 있었다.

따라서 trusted Git runner에 updater가 실제 사용하는 로컬 plumbing allowlist를
추가했다. checkout, remote, archive, 외부 filter/textconv, write-capable config와
hash-object, worktree를 건드리는 `read-tree -u`는 실행기 자체에서 거부한다.
실행기 version probe를 제외한 모든 호출은 고정된 fsmonitor/hooks/attributes/excludes
설정과 절대 working root를 포함하는 정확한 prologue만 허용해 임의 `-c`, `-C`,
`--git-dir`, `--work-tree`, namespace 우회도 차단한다. 실제 무결성 검사에 필요한
`hash-object --no-filters -- <safe-relative-path>`는 정확한 한 형태로만 허용한다.
독립 focused 검증은 Git runner와 approval binding 합계 16 tests, 133 subtests가
통과했다. 이 기록 시점에도 실제 릴리스, 프로젝트 설치, 개인 프로젝트 쓰기는 수행하지
않았다.

## 승인 전 runtime parent의 정직한 분류

완성된 runtime candidate를 승인 뒤 copy 없이 같은 volume에서 원자적으로 승격하려면
`.zettel-kasten/runtimes` 부모의 identity를 승인 전에 고정할 필요가 있다. 후보 준비가
이 빈 부모를 exact-owned 상태로 만들 수 있는데, 이를 단순히 “승인 전 write 없음”으로
표시하는 것은 부정확하다는 통합 감사를 반영했다.

안전한 선생성은 유지하되 이를 transient control scaffold로 별도 공개한다. 승인 전
runtime bytes 설치, pin/launcher/source 변경, 활성화는 모두 false이고, 취소 때 해당
부모가 이번 transaction에서 생성됐으며 여전히 정확히 비어 있을 때만 제거한다.
기존 부모는 보존한다. 따라서 정상 취소의 보장은 “write가 한 번도 없었다”가 아니라
“지속되는 domain effect가 없고 exact control scaffold가 원복됐다”이다. 이 구분은
approval projection, transaction evidence, 취소 테스트에 함께 결속한다.

## durable updater 최종 통합과 독립 재검증

새 프로젝트별 runtime 후보, exact-human claim workflow, held Git runner, 내구
transaction journal을 실제 `project-version-update` 서비스와 CLI에 연결했다. 공개
승인 경로는 승인 전에 runtime candidate와 모든 승인 입력을 봉인하고, 승인 뒤에는
같은 held Git 실행기와 로컬 plumbing만 사용한다. 기존 역사적 core는 read-only
preview와 과거 회귀 근거를 위해 남겨 두었지만, 현재 공개 live approval은 새 durable
writer로 분기하거나 필수 입력이 없으면 차단되므로 예전 materializer로 우회하지
않는다.

통합 구현자가 먼저 전체 `ArchiveCliTests -k project_version_update`를 실행해 41 tests를
통과했고 direct-worker 전용 1건은 의도된 skip이었다. 그 뒤 주 작업 세션에서 다음을
독립 재실행했다.

- Python compileall과 `git diff --check`: 통과;
- held Git runner, durable transaction, approval binding, exact-human workflow:
  66 tests passed in 35.109 seconds;
- 실제 venv/wheel 설치, 정적 영수증, claim finalizer와 7개 hard-exit 경계 재개:
  2 tests passed in 298.634 seconds;
- 2초 내 최초 상태와 10초 미만 heartbeat, idempotent replay, 승인 취소,
  fetch 준비 실패, 승인 뒤 ref/pin/policy drift의 pre-writer 차단:
  5 tests passed in 72.702 seconds.

hard-exit 수동 검증이 남긴 `.test-hard-exit-domain-20260823`은 현재 작업이 만든
untracked test artifact임을 확인한 뒤 정확한 경로만 제거했다. 긴 Windows 경로와
내부 test Git repository가 포함되어 `core.longPaths=true`와 double-force가 필요한
범위였으며, 다른 untracked 파일은 정리하지 않았다.

이 시점의 판정은 **v0.4.3 updater 통합과 핵심 복구 테스트 통과, 전체 CI 대기**다.
아직 GitHub merge/tag/release, 실제 native 승인, 프로젝트 전용 공식 설치, 개인 프로젝트
Letter 138 apply/rollback/독립 검증, provider 호출, 공용 PATH 교체는 수행하지 않았다.

## 전체 CI 전 역사 회귀 교정

이전 PR #77 실패 로그를 job별로 다시 수집해 실제 실패 범위를 다섯 모듈로 고정했다.
문서의 현재 버전, v0.4.2 역사 검증, resource/privacy subset, feedback CAS 호출 계약,
Letter 129 canary가 해당 범위였다.

재실행 과정에서 trusted Git runner를 필수 인자로 바꾼 뒤 역사적
`project-bytecode-repair` planner가 옛 무인자 호출을 남겨 둔 새 회귀를 발견했다.
공개 updater의 held runner 경계를 완화하지 않고, 역사적 read-only planner 전용
short-lived sealed runner adapter를 추가해 metadata, local Git probe, collision batch,
target ref snapshot을 모두 명시적으로 로컬 read-only 경계에 연결했다.

또 v0.4.3 공개 runtime policy와 exact public wheel이 없는 역사적 합성 fixture가 업데이트
성공을 기대하던 canary를 교정했다. 이 fixture는 bytecode 복구 planner의 보존을 증명한
뒤 공개 updater가 durable runtime supply 부재로 쓰기 전에 차단되는지를 검증한다.
실제 exact broker 성공은 wheel/venv와 durable candidate를 포함하는 별도 끝단 통합
테스트가 담당하므로, 합성 fixture를 성공으로 꾸미지 않는다.

privacy predecessor subset은 새 회의록 경로의 개인 프로젝트 이름 세 건을 일반화해
새 공개 경로에 그 식별자가 추가되지 않도록 했다. 검사 허용 목록을 넓히지 않았다.
최종적으로 이전 PR 실패 다섯 모듈의 66 tests가 91.703 seconds에 통과했고 Windows
조건 2건만 정상 skip됐다. GitHub 병렬 전체 CI는 아직 새 커밋을 올리기 전이다.

## 2026-08-24 PR 첫 전체 CI와 Windows 회귀 교정

통합 커밋 `905463b8`을 PR #77에 올린 뒤 GitHub Actions run
`32642358548`의 모든 job을 끝까지 확인했다. Release readiness gate 자체는
통과했지만 8개 unittest shard는 역사적 호출 계약과 새 프로젝트 runtime 계약의
불일치 때문에 실패했고, Windows raw resource hash도 checkout의 CRLF 변환 때문에
실패했다. 이 상태에서는 PR을 병합하거나 tag/release를 만들지 않았다.

실패를 다음 경계로 교정했다.

- trusted runner가 필요한 역사적 batch/collision 테스트는 실제 임시 절대 Git
  mirror와 명시적인 runner를 전달하도록 바꿨다. 서비스가 runner를 몰래 생성하는
  옛 계약으로 되돌리지 않았다.
- updater가 실제로 사용하는 안전한 read-only 명령 중
  `describe --tags --exact-match HEAD`, `tag --list v*`,
  `show -s --format=%s HEAD`만 runner allowlist에 추가하고 변형은 계속 거부했다.
- 공개 exact-human production wrapper의 서명은 기존 세 인자 계약을 보존하고,
  project updater 전용 claim finalizer는 내부 core 경로에서만 전달하도록 했다.
- source checkout이나 v0.4.3 side-by-side runtime이 없는 옛 합성 fixture는 성공으로
  꾸미지 않고 `project_runtime_mismatch`로 차단되는 현재 계약을 검증하게 했다.
- runtime policy와 supply lock은 Windows checkout에서도 raw SHA-256이 동일하도록
  `.gitattributes`에서 LF를 명시했다. privacy/resource 검사의 부분집합은 약화하지
  않았다.

강제 종료 뒤에도 위 변경 열 건이 작업 트리에 보존됐음을 확인하고 중단된 검증을
재개했다. 최종 로컬 증거는 다음과 같다.

- pytest-native exact CI 집합: 210 tests passed in 16.70 seconds;
- two-shard의 shard 1: 1,721 tests passed in 1,060.916 seconds,
  19 skipped;
- `tests.test_cli`: 1,402 tests passed in 2,532.614 seconds,
  9 skipped;
- shard 0의 비-CLI 62개 모듈 분리 실행: 545 tests passed, 5 skipped;
- 분리 명령의 module search path 때문에 import되지 않은
  `test_project_runtime_candidate`는 원래 tests 경계에서 독립 재실행해
  3 tests passed in 261.040 seconds;
- release readiness 네 gate, 163개 package resource sync/check와
  `git diff --check`: 통과.

따라서 이전 shard 0 실행의 5 failures와 출력이 잘린 17 errors는 현재 수정본에서
재현되지 않는다. 다음 단계는 이 기록을 포함해 resource/privacy 검사와 새 wheel을
다시 검증하고 한 커밋으로 push한 뒤, 새 GitHub Actions run의 Ubuntu Python
3.10/3.12와 Windows Python 3.12 전체 job이 모두 통과하는지 확인하는 것이다.
그 전까지 merge/tag/release, 실제 프로젝트 설치, Letter 138 데이터 쓰기,
provider 호출과 공용 `archive.exe` 교체는 계속 금지한다.

## 현재 수정본의 새 격리 wheel

이전 후보 SHA-256은 폐기한 채 현재 수정본으로 새 wheel을 만들었다.
`tools/check_wheel_install.py`는 OS 임시 폴더의 새 가상환경에만 설치했고 공용 PATH와
프로젝트 pin은 변경하지 않았다.

- wheel: `wom_kit-0.4.3-py3-none-any.whl`;
- size: 2,291,226 bytes;
- SHA-256: `535f99f2e6d53c17bfc62cb05674d5df634deaf30ac7afbf3ec92da5db6f2064`;
- package resources: 163/163, 685,190 bytes;
- wheel files: 230;
- runtime skill lifecycle, onboarding preview/fixed-close, strict Doctor fixture:
  passed;
- 독립 `Get-FileHash` 결과: checker의 SHA-256과 일치;
- wheel 전체 entry의 실제 Windows 사용자명, long path와 8.3 short path 흔적:
  0건.

공개 문서의 `C:\Users\<user>` 및 `C:\Users\example`은 설명용 placeholder이고,
실제 사용자 폴더 경로가 아니다. 추적 파일의 실제 사용자명 문자열 1건은
privacy 회귀 테스트가 해당 이름이 직렬화 결과에 없음을 검증하는 부정 assertion이다.
privacy gate는 그대로 통과했다. 이 wheel은 로컬 후보 근거이며 아직 GitHub Release
asset이 아니다.

## PR 재실행의 Linux test-helper 경로 교정

수정 커밋 `24182942`로 시작한 GitHub Actions run `32650396904`에서 release
readiness, Ubuntu Python 3.10 shard 2/2와 Windows Python 3.12 shard 3/4는
먼저 통과했다. Ubuntu Python 3.12 shard 1/2는 1,944 tests를 실행한 뒤
14 errors로 실패했지만 assertion failure는 없었다. 14건의 traceback은 모두
`ArchiveCliTests.project_runtime_candidate_artifact_fixture`의
`from tests.test_project_runtime import ...` 한 줄에서 같은
`ModuleNotFoundError: No module named 'tests'`로 귀결됐다.

CI는 repository root에서 test file path를 직접 unittest에 전달하므로 Linux에서는
`wom-kit/tests`가 `tests` namespace package로 고정되지 않는다. 테스트 파일 자신의
절대 parent를 `TESTS_ROOT`로 계산해 `sys.path` 뒤에 추가하고,
`test_project_runtime` 보조 모듈을 직접 import하도록 교정했다. Production source,
runtime writer, 승인 경계와 wheel payload는 바꾸지 않았다.

GitHub와 같은 file-path unittest 호출 형태로 대표 cleanup uncertainty 테스트와
전체 approve/fetch/verify/replay 테스트를 재실행해 각각 11.091초와 49.748초에
통과했다. 남은 첫 run job 결과도 확인하되, 이 교정을 새 커밋으로 push한 뒤 새
전체 CI run을 기준으로 병합 가능 여부를 다시 판정한다.
