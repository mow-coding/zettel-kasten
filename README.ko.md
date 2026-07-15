# WOM

> Widesider of Modernity: 인간 인식의 지평을 넓히기 위한 local-first, AI-native, Web3 지향 archive/communication system.

[English README](README.md) · [공개 문서 지도](wom-kit/docs/public-documentation-map.ko.md) · [업그레이드 가이드](UPGRADE.ko.md) · [변경 기록](CHANGELOG.md) · [릴리스 노트](wom-kit/docs/releases/) · [보안 정책](SECURITY.md)

`WOM`은 `Widesider of Modernity`의 약자입니다.

이 이름은 modernity의 최전선에서 인간이 인식할 수 있는 지평을 넓히겠다는 의도를 담습니다.

WOM 안에서:

- `zettel-kasten`은 역사적 뿌리이자 local archive method입니다.
- `zet`는 zettel-kasten 안에서 민팅되는 단위 문서입니다.
- `ZET`는 zettel-kasten 기반 통신 계층입니다. 1:1이면 메신저, 1:다수면 SNS/feed, 다수:다수면 협업툴이 될 수 있습니다.
- `node`는 subject/archive participant입니다.
- 선호 lifecycle은 `mint -> delegate -> attest -> anchor`입니다.

`zettel-kasten`은 repository와 archive system의 뿌리로 남지만, 제품 언어는 `WOM`, `zet`, `ZET`, `node`를 중심으로 정리합니다.

## 현재 상태

<!--
유지보수 계약 (decision log v0.3.161, v0.3.245): 릴리스마다 (1) 아래 code
block의 현재 공개 기준 한 줄, (2) 단 하나의 이전 공개 기준 줄, (3) 안정된
빠른 시작의 정확한 wheel 버전, (4) feature 릴리스라면 "현재 포함된 것"의
주제별 bullet 최대 한 개만 수정합니다. 릴리스 이력은 CHANGELOG.md와
wom-kit/docs/releases/에만 쌓고, baseline 사다리와 tag 목록을 여기서 다시
키우지 않습니다.
-->

현재 공개 기준:

```text
v0.3.249 pre-release
```

이전 공개 기준: v0.3.248 pre-release.

전체 릴리스 이력은 [CHANGELOG.md](CHANGELOG.md)와 [wom-kit/docs/releases/](wom-kit/docs/releases/)를 보세요.

이 저장소는 공개 전시용이자 reference implementation 작업공간입니다. 아직 production-ready 제품은 아닙니다.

Roadmap 요약: `v0.1.x`는 아이디어/프로토콜 언어 라인, `v0.2.x`는 첫 local
구현 라인, `v0.3.x`는 현재 진행 중인 WOM 실사용 피드백과 안전성 강화 라인,
`v0.4.x`는 custom UI control layer 라인, `v0.5.x`는 ZET 실사용 피드백
라인으로 계획되어 있습니다. phase gate와 future-only 경계는
[WOM Product Roadmap](wom-kit/docs/product-roadmap.md)을 보세요.

## 빠른 시작

정확한 릴리스 파일을 격리된 명령줄 도구로 설치합니다.

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.249/wom_kit-0.3.249-py3-none-any.whl"
archive --version
```

WOM-kit은 아직 PyPI에 공개하지 않았으므로 `pip install wom-kit`은 공식 설치
명령이 아닙니다. 일반 `pip`는 전용 가상환경에서 정확한 릴리스 파일을 지정할
때만 지원합니다. Python 도구 설치만으로 보관함을 열거나 바꾸지 않으며, AI
호스트 설정도 조용히 수정하지 않습니다.

릴리스 파일에는 `wom-archive` Agent Skill도 들어 있습니다. 현재 Codex
사용자에게 활성화하기 전, 먼저 쓰기 없는 미리보기를 확인합니다.

```powershell
archive runtime-skill-install --dry-run --format json
```

이어서 [한글 Python 도구 설치 안내](wom-kit/docs/python-tool-install.ko.md),
[영문 설치 안내](wom-kit/docs/python-tool-install.md), 또는
[한글 Agent Skill 활성화·제거 안내](wom-kit/docs/runtime-skill-install.ko.md)를
보면 됩니다.

## 현재 포함된 것

주제별로 묶은 현재 기능입니다. 각 기능이 실제 구현인지, read-only preview인지, 승인 write인지, 문서만 있는지 보려면 [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md)를 보세요.

### Archive 핵심과 lifecycle

- WOM / zet / ZET 설계 기준, specs, schemas, fake archive, release notes, work logs,
- 아티팩트 우선 인간 기억 원칙. 특정 시점의 로컬 아티팩트와 시간순 이력이 다시 만들 수 있는 엔티티·그래프 투영보다 우선하며, 같은 라벨은 자동 동일성 병합의 권한이 아니고, 정본은 객관적 진실이 아니라 사용자가 승인한 현재 아카이브 상태이며, AI가 맥락을 다시 추론하더라도 인간의 변화는 보이게 남깁니다. 자세한 내용은 [제품 철학](wom-kit/docs/concepts/product-philosophy.ko.md)을 보세요.
- 기계가 읽을 수 있는 local sovereignty 계약. 검토된 local WOM 상태가 정본이고, GitHub는 metadata/version 이력 백업, object storage는 objet byte 백업, 외부 DB는 local 관계 기록에서 재생성 가능한 지도 백업/복제본입니다. runtime/start-here/recovery 표면은 offline 범위, 충돌 우선순위, 복구 방향, 영수증 경계를 동일하게 제공합니다.
- `wom-kit/` 안의 local CLI와 MCP tooling,
- 깨끗한 환경에서 온보딩과 엄격한 검진에 필요한 runtime 스키마·템플릿·기본 규칙·릴리스 신원 문서를 정확한 GitHub 릴리스 파일 하나에 담은 v0.3.242 자체 완결 Python wheel. 격리된 `uv tool install`을 권장하고 전용 `pip` 가상환경도 지원하지만 PyPI 공개는 아직 미래 작업으로 명시합니다.
- doctor, draft, mint, delegate, receipt, search, metadata review 같은 private archive lifecycle 도구. draft 생성은 forward-only draft-id 위생을 갖춰 제목이 없거나 한글뿐인 제목이 더 이상 오해를 주는 `_draft` id로 떨어지지 않고, draft 시점에 `--kind`를 검증해 경고와 함께 유효한 kind 목록을 보여줍니다. mint는 attributed `--affirm` 플래그로 두 human-review 체크리스트 항목을 raw YAML 편집 대신 검토자 귀속(attributed)·감사 가능한 CLI 행위로 충족합니다(mint receipt에 기록, `--reviewed-by` 없으면 무효, machine-enforced 항목은 절대 덮어쓰지 않음).
- 정직한 `archive remint-reconcile`(그리고 retire receipt용 형제 명령 `archive retire-draft-reconcile`): zet의 바이트가 디스크에서 드리프트한 뒤(CRLF/BOM 재체크아웃 또는 사람의 내용 수정) receipt에 기록된 sha256을 재발급합니다. draft 스냅샷 자체가 드리프트한 경우에도 드리프트를 개행/BOM만인 `format_drift`나 `content_change`로 분류하되, 모든 content frontmatter 필드를 검사(전체 필드 재구성 + mint receipt의 `id`/`title` 대조)하므로 어떤 필드를 수정하거나 내용이 변조된 스냅샷도 절대 `format_drift`의 앵커가 되지 않습니다. 항상 디스크의 현재 내용을 보여주고, 승인하려면 reviewer가 필요하며, 내용 변경 ack 게이트를 절대 우회하지 않는 opt-in `--strip-bom`을 제공하고(그리고 v0.3.172부터 dry-run에서도 approve 실행이 기록하는 것과 동일한 strip 의도 메타데이터를 미리 보여줍니다 — 분류에는 전혀 영향이 없는 no-op이며 `content_change`를 절대 세탁하지 않습니다), v0.3.176부터는 BOM/개행 정규화 이후에도 본문이 여전히 다른 `content_change`에 대해 내용을 노출하지 않는 `body_diff_diagnostic`(카테고리 라벨 + 정규화 형태에서의 바이트 오프셋 + 길이 델타뿐, 본문 텍스트는 절대 없음)을 함께 보여주고, dry-run JSON `--diagnostic-only`로 canonical 본문 텍스트와 초록 데이터 값을 빼고도 그 drift 숫자를 볼 수 있게 합니다. v0.3.230부터 모든 `content_change`는 내용을 싣지 않은 순서형 사람 검토 계획을 함께 반환하고 승인 때 그 SHA-256을 다시 요구하므로, 검토 뒤 바이트나 영수증 참조가 바뀌면 아무것도 쓰기 전에 오래된 승인을 막습니다. 손상을 절대 가리지 않으며, in-place receipt 갱신과 별도의 불변 audit receipt를 함께 씁니다.
- reconcile approve 결과는 이제 `status: reconcile_applied`와 doctor 재검증 next-action을 보여줍니다. 즉 승인 적용이 끝난 JSON/text 출력에 이전 dry-run의 "검토 필요" 상태가 그대로 남지 않습니다.
- object-storage doctor는 이제 같은 key의 `skipped_remote_same` coverage를 인정하고, 진짜 누락된 `wom_uploaded` manifest binding은 승인 게이트가 있는 `object-storage-wom-location-reconcile`로 복구할 수 있게 하며, 그 명령의 audit receipt도 전용 schema로 검증합니다.
- 완료된 전체 검진 인수인계 문서는 ERROR/WARN을 단순 개수로 버리지 않고 제한된 항목, 전체 코드별 개수, 권장 명령을 남깁니다. BOM 진단은 검증된 canonical zet 아이디를 reconcile 미리보기에 실제로 채우며, 아이디가 없거나 안전하지 않으면 미완성 placeholder 명령을 내보내지 않습니다. compact heartbeat는 보존된 과거 엣지 집계보다 현재 local-profile secret-safety의 파일·내용·프로필 처리량을 우선하며, 일반 파일 안전 순회는 확인한 디렉터리 경계를 재사용하면서 심볼릭 링크 이탈 검사는 엄격하게 유지합니다.
- read-only `archive zet-quality-check --dry-run`으로 mint 전 entity-term, document-type, OCR/parse metadata, table-structure, correction-event, source-rights, audience, derived-artifact dependency 위험을 점검합니다. 선택적 `zet-quality-rules.yml` 프로젝트 규칙은 matched term을 출력하지 않으면서 금지 entity alias를 mint blocker로 만들 수 있습니다.
- read-only `archive status-board --dry-run`으로 canonical zet, active draft, retire 대기 minted draft, document/audience metadata gap, source metadata gap, derived-artifact sync gap, 선택적 quality count를 한 번에 요약합니다. title/body/source value/provider URL/local path는 출력하지 않습니다.
- 초록 데이터만 읽는 `archive first-read-readiness --dry-run`과 MCP `first_read_readiness`는 일반 보관함 검진과 AI 기억 재구성 준비 상태를 분리합니다. 비공개 처리되지 않은 모든 정본 zet에 명시적 `abstract`가 있고 모든 zet 아이디가 하나로 안전하게 해석될 때만 `ready`가 됩니다. 호환용 요약과 제한된 보완 후보는 보여주되 제목, 초록 문장, 본문, 중복 아이디 값, 절대 경로, 외부 서비스 값, 비밀정보는 출력하지 않습니다. `create-draft`는 초록이 없는 미완성 생각도 보존하지만, `mint-zet`, `mint-zettel`, 이전 `promote`는 정본 발행 파일을 쓰기 전에 명시적이고 안전한 초록 데이터를 요구하고 다시 검증합니다. 이어서 읽기 전용 `archive abstract-freshness --dry-run`과 MCP `abstract_freshness`는 현재 초록 데이터와 본문의 해시 짝을 사람이 검토한 근거와 대조해 `fresh`, `stale`, `unverified`, `missing`, `unreadable`, 정책상 제외 상태를 한 번의 영수증 색인과 한 번의 정본 순회로 구분하며, 문장을 출력하거나 기억을 자동 수정하지 않습니다. 읽기 전용 `archive zet-revision-plan --dry-run`과 MCP `zet_revision_plan`은 `.wom-scratch/revisions/` 아래의 비공개 전체 zet 수정안 하나를 현재 정본 바이트와 묶고, 아이디·발행 이력·최초 작성자 정보를 고정한 채 해시와 고정된 변경 종류만 보여줍니다. 이어서 CLI 전용 `archive zet-revision-write --dry-run|--approve`는 실제 쓰기 후보의 별도 해시, 명시적 사람 검토, 교체 직전 바이트의 로컬 콘텐츠 주소형 오브제 보존, 원자 교체, 실행 중 오류 복구, 중단 뒤 영수증 마무리, 초록 신선도 근거가 되는 불변 v0.2 수정 영수증을 제공합니다. 읽기 전용 CLI `archive zet-revision-receipt-audit --dry-run`은 일반 수정과 정확 복원을 하나의 엄격한 시간순 사건 이력으로 검사하고, 새 이전-상태 보존본과 목록 기록을 검증하며, 근거가 완전한 반복 상태(예: `A -> B -> A`)는 허용하고, 비공개 내용을 출력하거나 잠금을 지우지 않은 채 남은 작업 잠금을 분류합니다. CLI 전용 `archive zet-revision-restore-proposal-from-snapshot --dry-run|--approve`은 검증된 v0.2 이전-상태 보존본을 정본 변경 없이 독립된 콘텐츠 주소형 비공개 검토 복사본으로 만듭니다. CLI 전용 `archive zet-revision-restore-plan --dry-run`은 비공개 백업에서 따로 복구한 과거 전체 zet를 실제 최신 영수증 사건의 이전 상태와 묶고 현재 정책을 다시 검사합니다. 이어서 별도의 승인형 `archive zet-revision-restore-write --dry-run|--approve`는 사람이 검토한 그 바이트만 원자적으로 설치하고, 과거 형식과 `updated_at`을 보존하며, 실행 중 오류를 되돌리고, 중단된 작업을 재개하고, 불변 복원 영수증을 남깁니다. 이것은 WOM이 말하는 **메멘토 문제**에 대한 답의 한 층입니다. 새 AI 세션은 흐려지는 대화 기억을 믿거나 근거 없이 기억을 직접 고치는 대신, 사람이 검토한 로컬 아티팩트에서 오래가는 맥락을 다시 세우고 수정하며 필요할 때 근거 있는 복구를 수행해야 합니다. v0.3.240부터 첫 읽기 진단 완료와 준비 완료를 분리하고, 최신성 검진은 영속 캐시 없이 현재 필요한 증거 후보만 열며, 2단계 진행 순서를 표시하고, 대형 옛 보관함은 자동 대량 보완이 아니라 사람이 검토하는 3건 표본부터 시작합니다. v0.3.241부터 최신성 검진은 최대 8개 작업으로 제한된 초록 데이터를 읽고, 유효한 명시적 초록 데이터가 있는 대상만 전체 본문 바이트를 엽니다.
- read-only `archive derived-artifact-staleness --dry-run`으로 `derived_artifacts`가 마지막 검토 sync 이후 더 최신 source zet을 놓치고 있는지 확인합니다. 외부 보고서 본문은 열지 않고, artifact ref/title/body/provider URL/local path는 출력하지 않습니다.
- 오래 도는 `validate`, `doctor --strict`, 대형 `object-storage-adopt-existing` 실행을 위한 선택형 stage/count progress 출력. 진행률은 stderr로만 나가며 object id, remote key, bucket name, provider URL, 정확한 credential ref, token, secret value를 싣지 않습니다. 대형 adopt plan resolution은 이제 실행별 manifest index를 쓰고, read-only `--stop-after-plan`, matching resume count, same-provider nonmatching store/key 진단, 같은 store_ref의 `wom_uploaded` raw count와 실제 skip 후보 count 차이를 함께 보여주며, doctor는 receipt 검사 중 파일 SHA/frontmatter cache, mint-link sub-step, receipt 완료 progress, receipt별 heartbeat, receipt별 file-ref liveness, target file-ref drilldown, 엣지 영수증 파일명 인덱스의 시작/heartbeat/완료와 source·후보·cache hit 누계 및 최종 요약, hash 시작/완료 liveness, retired source skip, local-profile secret-safety liveness, 초기 ETA warm-up, compact 기본 `--progress`, opt-in verbose trace, JSONL progress log, archive-relative `--output` full result capture, compact summary, stdout severity filter, output/progress-log path-policy metadata를 제공합니다. source별 후보 묶음 상세는 compact stderr를 도배하지 않고 verbose/JSONL에 남습니다. `ai-start-here`, `upgrade-check`, CLI `zet-catalog`도 내용이 없는 진행 표시, 10초 heartbeat, 임시 결과 저장 계약을 공유합니다. `zet-catalog-pass`는 한 프로세스에서 strict 페이지를 끝까지 읽고 마지막 로컬 재검증 뒤 SHA-256이 붙은 비공개 임시 JSONL을 완성합니다. `zet-catalog-pass-read`는 전체 파일을 검증한 뒤 한 페이지만 제한해 반환하고, `zet-catalog-pass-cleanup`은 미리보기와 사람의 명시 승인 뒤 해시가 같은 완성 파일 하나만 삭제합니다. `read-zettel --section document`는 사람이 읽는 문서 화면에서 raw YAML frontmatter를 숨기는 read-only 보기 모드를 제공합니다.

### Capture와 intake

- 모든 runtime-visible surface(AGENTS.md template, runtime SKILL.md, skill/plugin layer 문서)에 적용되는 규범적 AI intake protocol,
- 어떤 로컬 파일이든 archive나 objet 저장소로 물리적으로 복사하기 전에 먼저 실행하는 source-intake dry-run과, canonical intake 위치(D2)인 in-archive `staging/incoming/` capture staging,
- 검토된 selection -> 승인된 capture만이 capture 권한이라는 규칙과, 대량 외부 저장소를 위한 prehashed-ledger 증거,
- 추가 read-only doctor 가드 2종(raw in-root `objets/` 폴더에 대한 `archive_objets_layout_noncanonical`과 migration 가이드, objet 바이트 저장소가 상위 git working tree에 tracking될 수 있을 때의 `workspace_objet_store_git_exposure`)과 앵커된 `/objets/` `.gitignore` 안전 기본값,
- `archive objet-capture-selection --derived-text-staged-path`로 여는 짝지은(paired) transcript intake: 하나의 검토된 selection manifest가 staged 원본과 이미 추출된 transcript를 함께 승인하고(원시 바이트 `approved_text_sha256` 커밋, staged-path와 동일한 confinement 검사), 한 번의 `archive objet-capture` 실행이 원본을 발행한 뒤 발급된 object_id에 묶인 derived text를 등록합니다.
- item/run 단위의 추가 `status_class`(`partial` = 원본은 durable, derived는 재시도 가능)와 BOM 인식 derive-text 디코딩(BOM 표기 UTF-8/UTF-16은 BOM 없는 UTF-8로 저장하고 원시 바이트 provenance 기록, UTF-32와 BOM 없는 비 UTF-8은 결정적으로 차단),
- `archive objet-capture-enable`로 여는 실제(비 sandbox) archive의 local objet capture 소유자 승인 흐름: read-only dry-run 자격 보고, 승인형 `ops/capture-enablement.yml` 동의 record와 영수증(receipt), never-touch 이름 패턴 명시적 확인, forward-only revoke와 `--reenable` 보호, doctor 진단까지 포함합니다. 이 record는 같은 write-trust domain 안의 동의 표시이지 보안 경계가 아닙니다.
- derived-text coverage/toolchain/doctor/agent-contract read-only gate와 PATH에 없는 로컬 추출 도구를 위한 비공개 tool-hint path,

### 조회와 view

- runtime context, profile, source/objet intake, block header, prompt boundary를 위한 read-only preview layer. 선택형 360자 `frontmatter.abstract`와 CLI/MCP `zet-catalog`는 모든 zet를 초록+타이 compact projection으로 열거하고, strict 연속 노드 완주, snapshot/항목/전체 응답/envelope 예상 토큰 증거와 선택형 envelope 예비 공간을 제공합니다. 첫 페이지는 전체 진단을 유지하고 이후에는 항목과 완주 증거를 그대로 둔 채 반복 진단만 줄이는 선택형 compact continuation 응답을 쓸 수 있습니다. 검증된 seed의 가까운 타이부터 읽되 끊어진 모든 component까지 포함하는 연결 순서와, 각 항목이 seed인지 어떤 타이를 따라왔는지 설명하는 선택형 `routed_reading`도 제공합니다. 별도 준비 상태는 모든 노드 방문, 비공개 처리되지 않은 초록의 실제 이용 가능 여부, 후속 본문 읽기를 위한 고유 ID 상태를 구분하며, generated index/map이나 영구 WOM goal/loop 상태를 만들지 않습니다. 비공개 처리되지 않은 `read-zettel`은 AI가 실제로 읽은 파일·본문의 정확한 해시를 함께 주고, `zet-abstract-backfill-plan`은 초록 누락 후보를 현재 정본 바이트와 대조합니다. `zet-abstract-backfill-write`는 사람이 검토한 SHA 기반 초록만 반영하고, `zet-abstract-backfill-revert`는 이후 정본 수정이 없을 때만 삽입 전 바이트를 복원합니다. `zet-abstract-backfill-receipt-audit`은 모든 적용/되돌리기 영수증 생명주기와 남은 강제 종료 의심 잠금을 내용 없이 한 번에 검진합니다. 공개 출력에는 아이디·경로·본문·초록·검수자 값이 나오지 않습니다.
- read-only objet reference resolution 및 zettel objet link preview,

### 공유와 ZET preview

- foreign block review, projection, shared update review/index, shared update route preview, ZET would-transport planning을 위한 read-only preview layer,
- 사람 승인 뒤에만 동작하는 일부 local write path,

### Privacy와 redaction

- `zet-self-contained-check`, AI scratch lifecycle 관리, v0.3.187 pre-release에서 도입된 read-only AI artifact inventory. 공개 외부 인용 URL은 zet 본문이나 `source_refs`에 남길 수 있고, private provider locator와 원본 파일 위치는 여전히 durable WOM ref가 필요하며, `.wom-scratch/`, `workbench/ai-scratch/`, `staging/ai/inbox/`, `staging/ai/reviewed/`는 제한된 AI artifact/scratch 표면입니다. `archive ai-artifact-inventory --dry-run`은 파일 본문을 읽지 않고 기본적으로 경로를 출력하지 않으며, 파일 쓰기/삭제, zet 생성, provider 호출 없이 AI 산출물 후보의 운명 후보를 보여줍니다. 승인된 mint는 명시된 scratch ref를 canonical zet에서 제거하고 cleanup receipt를 남기며 해당 scratch 파일을 소비할 수 있습니다.
- read-only `archive secret-signal-taxonomy --dry-run`으로 AI 운영자가 harmless concept word와 safe ref를 실제 secret-like value, private locator, account identifier, unknown sensitive context와 구분하게 합니다.

### AI operator 계약과 runtime handoff

- CLI 전용 로컬 Agent Skill 호스트 수명주기. 읽기 전용 `runtime-skill-status`, 계획 해시로 묶인 `runtime-skill-install --dry-run|--approve`, 설치 목록으로 검증하는 `runtime-skill-uninstall --dry-run|--approve`가 현재 Codex 사용자·저장소 `.agents/skills` 위치 또는 직접 지정한 다른 스킬 폴더 한 곳을 다룹니다. 경로는 기본으로 가리고, 승인 후 쓰기에는 검토자와 미리보기의 정확한 해시를 요구하며, 소유권을 모르는 폴더나 사람이 고친 스킬은 덮어쓰거나 지우지 않습니다. Python 설치 자체는 호스트 설정을 쓰지 않고 MCP 쓰기 표면도 추가하지 않습니다.
- 표준 형식과 호환되는 `wom-archive` Agent Skill 묶음. 처음 읽는 `SKILL.md`는 104줄이고, 자주 쓰는 일을 여섯 개의 집중 참고문서로 나누며, 정확한 고급 명령이 필요할 때만 기존 전체 운영 계약을 읽습니다. 릴리스 검사는 메타데이터, 링크와 경로 안전, 모든 참고문서의 발견 가능성, 문맥 길이, 승인·비밀정보 경계, 아티팩트 우선 원칙과 조용한 동일성 병합 금지를 함께 지킵니다. AI는 정본을 객관적 진실이 아니라 사람이 검토한 현재 상태로 다루고 인간의 변화를 보존하며, 스스로를 조용히 설치하지 않습니다.
- read-only `archive version`으로 현재 실행 버전·프로젝트 핀·소스 미러를 확인하고, 승인형 `archive project-version-update`로 설정된 원격의 `main`과 정확한 릴리스 태그를 한 번에 받아 검증한 뒤 소스 미러와 알려진 버전 핀을 함께 갱신합니다. 더러운 작업 폴더, 버전 불일치, downgrade, 알 수 없는 파일은 차단하고 중간 실패 시 checkout과 핀을 복구하며 영수증을 남깁니다. 성공 직후에도 현재 Python 프로세스는 이전 버전이므로 새 프로세스에서 `archive version`을 다시 확인해야 하며, 이 명령이 처음 들어가는 v0.3.215 이전 설치는 이번 한 번만 기존 안전 절차로 v0.3.215까지 올라와야 합니다.
- read-only `archive capabilities --machine`으로 AI 운영자가 현재 설치본의 실행 가능한 CLI 명령, alias, 필수 인자, option, nested subcommand, local release identity를 안정된 `ok/state/summary/data/blockers/warnings` 봉투로 확인할 수 있습니다. GitHub나 provider는 호출하지 않습니다.
- read-only `archive operator-feedback-plan --dry-run`과 승인형 `archive operator-feedback-record --approve`로 AI 운영자가 만든 도구 피드백을 `ops/feedback/` 아래 draft/delivered/acknowledged/resolved/archived 상태 메타데이터로 추적합니다. 여기에 더해 read-only `archive operator-feedback-ledger --dry-run`(별칭 `feedback-ledger`, `feedback-board`)은 전달 상태를 상태별 카운트와 대기(draft) 목록으로 집계하고, 승인형 `archive operator-feedback-mark-delivered --approve`는 draft→delivered 전달 경계를 한 번에 처리하며 `delivered_at`를 찍고 receipt 하나를 씁니다. 피드백 본문은 읽지 않고, 피드백 ref/제목을 노출하지 않으며, 외부 제출도 하지 않고(메타데이터일 뿐이며 `delivered`는 운영자가 직접 찍은 표시일 뿐 외부 전달의 증거가 아닙니다), 사용자 지식 `objets/`를 피드백 수명주기 표면으로 쓰지 않게 합니다.
- read-only `archive approval-handoff-plan --dry-run`과 승인형 `archive approval-handoff-record --approve`로 AI가 사람 승인으로 넘겨야 하는 순간을 `ops/approval-handoffs/` 아래 needs_review/approved_once/denied/superseded/resolved 상태 메타데이터로 기록합니다. 실제 작업 실행, private material 읽기, provider 호출, target/action 값 재출력은 하지 않습니다.
- read-only `archive approval-handoff-audit --dry-run`으로 후속 작업이 handoff 기록을 승인 근거로 쓰기 전에 상태, 작업 종류, reviewed_by 등을 검사합니다. 실제 작업 실행이나 target/action 값 재출력은 하지 않습니다.
- read-only `archive operation-status-taxonomy --dry-run`으로 AI 운영자가 succeeded/preview/written/no_change와 partial/truncated/blocked/failed를 구분하게 합니다. 일부만 성공했거나 출력이 잘린 결과를 완료로 말하지 않기 위한 기준입니다.
- read-only `archive input-provenance-taxonomy --dry-run`으로 AI 운영자가 tool-discovered/receipt-verified 입력과 caller-supplied/AI-generated/fixture/environment-inferred/unknown 입력을 구분하게 합니다. 호출자가 준 입력을 도구가 발견한 source truth처럼 말하지 않기 위한 기준입니다.
- read-only `archive ai-response-contract --dry-run`으로 AI 운영자가 사람에게 답하기 전에 outcome, evidence basis, privacy/approval boundary, remaining work, conversational status board를 확인하게 합니다. 별도 web UI는 필요하지 않습니다.
- 핵심 read-only operator 명령들은 top-level `status_class`, `input_provenance_class`, `secret_signal_class`, `operator_envelope` 필드를 노출하므로 AI가 prose를 추론하지 않고 응답 계약을 적용할 수 있습니다.
- read-only `archive ai-start-here <archive-root> --dry-run --format markdown|json`과 빠른 기본 CLI/MCP 인수인계 문서(`runtime-context`)는 모든 zet와 영수증을 훑지 않고 정체성, canonical entrypoint, 로컬 주권, 작업기록, 신원 문서 일치 상태를 보여줍니다. 전체 검진은 `--full-doctor`를 명시할 때만 실행하며, 엣지 영수증 이력 검사는 파일명 지도 하나를 만든 뒤 SHA가 다른 zet에 속한 영수증만 읽고 별도 개수로 진행 상황을 보여줍니다. AI 스타팅 메뉴얼은 인수인계 문서가 이미 포함되었다고 표시하고 `completed_commands`와 `next_commands`를 분리합니다. 새 아카이브는 초기화할 때 템플릿 신원정보를 교체하고, 기존 같은 주체의 템플릿/표시정보 불일치는 실제 값을 출력하지 않는 `identity-reconcile --dry-run`과 세 해시에 묶인 명시적 승인으로 안내합니다.
- `ai-response-concept-guide --topic operator_vocabulary --locale ko-KR`로 AI 운영자가 이미 확정된 제품어(`WOM`, `zet`, `ZET`, `objet`, `receipt`=`영수증`, `mint`=`발행하다`, `canonical`=`정본`, `node`=`노드`, `edge`=`엣지`, `tie`=`타이`, `archive`=`아카이브 폴더`, `ai_start_here`=`AI 스타팅 메뉴얼`, `frontmatter`=`초록 데이터`)와 확정된 operator 용어(`object_id`=`오브제 아이디`, `doctor`=`검진`, `provider`=`외부 서비스`, `containment`=`포함 관계`, `safe_preview`=`미리보기`, `approved_write`=`승인 후 쓰기`, `external_report`=`공개용 문서`, `private_working_note`=`비공개 문서`)를 그대로 쓰게 합니다.
- operator용 runtime 표면(`AGENTS.md` 템플릿, runtime skill, plugin-layer 문서)에 담은 normative plain-language 규약: 운영자 AI가 사람에게 답할 때 git/infrastructure/WOM 내부 용어를 일상어로 옮기고 정확한 기술 용어는 괄호나 로그에만 남기게 합니다. read-only `ai-response-concept-guide --topic git_infra_terms` 조회 레이어가 뒷받침하며, 이는 사람 대상 산문에만 적용하는 AI의 지침일 뿐 WOM이 강제·검증하는 검사는 아닙니다.
- 같은 runtime 표면에 담은 normative AI-Operator Discipline 섹션: 운영자 AI가 지키는 세 가지 행동 규범을 정합니다. 사용자가 실제로 접한 출처(그들이 본 정확한 영상·판본·번역·언어)를 기록하고 "더 권위 있는" 원본으로 조용히 바꾸지 않으며(provenance hierarchy의 source-substitution 축과 짝을 이룸), 어떤 작업을 불가능하다고 선언하거나 낮춰 처리하기 전에 설치·사용 가능한 도구를 먼저 열거하고, 이미 설정·승인된 상태를 처음처럼 다시 묻지 않고 이어받습니다. 이는 AI가 적용하는 지침일 뿐 WOM이 강제·검증하는 검사는 아닙니다.

### Provider 연동

Tiro:

- read-only Tiro 회의 transcript import 계획(회의 메타/화자 turn/timestamp/confidence/audio objet ref 보존, transcript 본문·참가자명·URL·파일명·경로·계정·토큰 무출력),
- read-only Tiro full-data 무손실 복구 계획, `env:`/Windows Credential Manager 기반 `keyring:`/`credential-manager:` ref로 하는 approval-gated live Tiro REST fetch, raw 복구 번들의 WOM objet 캡처(해시·개수·상대경로·gap 범주만 보고),

Notion:

- 승인형 `archive migrate --target base-link-types`: 자체 `types.yml`을 vendoring한 archive에 누락된 모든 base WOM-kit link type을 덧붙입니다(recommended-9 집합의 상위집합이라 `continues`도 함께 끌어옵니다). 기존 항목은 제거·개명·재정렬·덮어쓰기하지 않는 append-only, no-clobber이며, revert는 없고 `--reviewed-by` 게이트를 걸며, 로컬 `types.yml`이 아예 없는 archive에서는 아무것도 쓰지 않는 안전 no-op입니다(이미 base를 상속). 형제 마이그레이션처럼 `safe_dump`로 파일 전체를 정규화한다는 점을 정직하게 밝힙니다.
- Notion child page/database/view 구조를 `contains` edge type으로 다루는 read-only connection planning과, 맞는 edge type이 없을 때 AI가 억지 매핑하지 않고 model gap으로 올리는 안전 가드,
- read-only nested tree recovery planning: 중첩 child page leaf를 세대 root에 귀속하고 `node_kind` 기반 content class를 보수적으로 도출하며, 큰 fixture가 부분 성공으로 위장하지 않도록 차단하고, 추적불능 parent chain과 조상 crawl 요청 큐를 버리지 않고 보고합니다.
- broad workspace 큐를 generation/ref scope filter로 좁힌 뒤 adapter 입력으로 넘길 수 있게 하는 read-only 조상 crawl 요청 계획과, 고정된 recursive fetch adapter execution contract,
- credential approval 뒤에만 동작하는 첫 local Notion ancestor structure fetch adapter: sanitized ancestor fixture와 non-secret receipt만 쓰고, media byte fetch와 page body capture는 별도 future gate로 남겨둡니다.
- 세대가 아직 확인되지 않은 untraceable leaf는 generation-id보다 leaf/root/ancestor ref로 좁히라는 안내,
- reviewed block mirror에서 tree fixture preview를 만들고, sanitized ancestor result를 merge/replan하며, sanitized local fixture bundle로 클라이언트 nested-tree issue를 검증하고, 클라이언트 follow-up용 최소 sanitized fixture request contract를 패키징하는 local recovery tooling,
- Notion nested recovery 인간 단계 가이드, `archive notion-recover`의 local `file:<path>` 토큰 파일 fallback(파일 경로와 토큰 값은 출력하지 않음), `archive notion-connection-plan --dry-run`의 one-click Notion connection product contract, `archive notion-oauth-connection-preflight --dry-run`의 secret-blind local OAuth runtime contract preflight,
- Notion provider failure의 safe action category 분류와, live browser OAuth/callback/token exchange/keyring token storage는 아직 future adapter boundary라는 명확한 표시,

Zettel edge write:

- approval-gated single-edge zettel edge write(reviewed zet-to-zet/zet-to-objet, `zet:notion:<id>` 안전 해소)와, 고신뢰 policy 매치만 게이트로 보내고 나머지는 human review 큐에 남기는 approval-gated policy batch write,
- 원본 receipt를 지우지 않는 receipt 기반 `revert-edge`/`revert-batch` edge 롤백,

Object storage:

- 버킷명·정확한 다음 명령·Cloudflare R2 설정 필드 안내를 곁들인 manifest-aware object-storage 추천, adapter readiness/operation request/execution-contract/presigned URL 계획,
- approval-gated 외부 upload evidence 등록과 read-only upload evidence 감사(라이브 provider adapter 이전 단계),
- 라이브 업로드 어댑터 Stage 2: 단일 네트워킹 seam 뒤에 손으로 구현한 실제 AWS SigV4 R2/S3 전송 계층(새 의존성 없음), (단일 PUT·multipart 모두에 적용되는) bounded 재시도 루프, 하드 누적 PUT 상한, 프로바이더의 체크섬 표면에 의존하지 않고 재다운로드-후-해시로 검증하는 전체 객체 무결성, orphan 정리, tiered tiny-first 게이트. 이제 실제 업로드 능력을 갖췄지만 라이브 `--approve`는 여전히 env 자격 증명·충족된 tiered 게이트·endpoint/bucket 없이는 닫힌 상태로 실패하며, 첫 사람 실행 라이브 객체 전까지 `unproven_against_live_provider` 상태를 유지,
- 선택 가능하고 기록되는 업로드 키 전략(`--key-strategy sha256_content_addressed|prefix`, 기본값 불변)과 안전한 `object-storage-adopt-existing` 명령: 운영자 자신의 키 레이아웃에 이미 저장된 객체는 기록된 키에서 존재+크기 일치를 증명하는 라이브 HEAD가 있을 때만 채택하고, 라이브 전송 계층에서는 실행기가 스킵 전에 항상 그 기록된 키를 다시 HEAD 한다(404면 재업로드하며, 조용한 스킵은 없음); 콘텐츠 주소 템플릿이 객체별 확장자를 복원하지 못할 때는 선택형 `--key-map`(JSONL sha256 -> 정확한 원격 키)으로 운영자의 실제 키에 저장된 객체를 채택하며, 크기는 여전히 매니페스트에서만 가져오고 모든 키는 digest 바인딩과 leak 가드를 통과한다,
- 검증된 adopt(HEAD 전용)는 업로드 5 GiB 티어 증명과 분리된다: adopt는 0바이트만 이동하므로, 검증된 tiny-first adopt 1건이 있으면 임의 크기의 배치 이관이 열린다(잘못된 키 self-limit, declared는 절대 카운트되지 않음, 업로드 티어 사다리 바이트 단위 불변은 모두 그대로 유지된다),
- 라이브 검증용 `--multipart-part-size` 오버라이드(`--allow-tiny-parts` 승인과 함께, `[4096, 64 MiB]` 범위, receipt에 `effective_multipart_part_size_bytes`로 기록): 낮춘 `--multipart-threshold`와 함께 쓰면 작은 객체에도 멀티파트를 강제해 라이브 R2 멀티파트를 증명한다. `handle.read()` 분할만 바뀌고 전체 객체 사전 해시·HEAD-after 전체 객체 검증·orphan 정리·leak 게이트는 바이트 단위로 그대로 유지된다,
- 라이브 검증용 `--force-reupload`: 이미 존재하는 객체를 다시 PUT한다(승인 + 리뷰어 게이트, 비-sha 키에서는 거부, `--dry-run`에서는 무효, 로컬이 손상됐으면 어떤 PUT보다 먼저 거부). 이제 resume ledger만 남은 skip도 우회하고, provider PUT이 0회면 `force_reupload_not_performed`로 닫힌 실패를 반환한다. 강제된 작은 멀티파트로 업로드 tier2를 증명할 수 있고, 이제 실제 멀티파트(`part_count>1`)가 기존 5 GiB 경로와 함께 tier2 증명으로 인정된다,

IMAP:

- read-only IMAP mailbox source 계획, schema 검증 adapter manifest preview, approval-gated local adapter manifest write, mailbox selection/preflight/execution-contract 계획,
- Gmail/Naver/generic 계정 ref에 대한 첫 approval-gated local IMAP header metadata scan과 그 실행 receipt의 오프라인 감사 checkpoint(본문/첨부/파생텍스트 작업은 future gate),

### Credential과 설정 가이드

- mail, OpenAI API, OCR API 등을 위한 read-only beginner setup manual,
- connected accounts bridge, credential reference planning, inventory, external store recommendation, vault onboarding planning, plaintext migration planning, future access broker planning,
- local approval receipt preview/write, credential policy checking, KeePassXC command preflight, CLI-only KeePassXC write execution with non-secret execution receipts,
- adapter readiness planning, adapter manifest preview, adapter audit receipt preview,

### Hygiene과 release tooling

- `archive doctor`는 archive root의 top-level web/app development artifact와 incomplete `.git` marker를 경고하며, `.gitignore` safe default에 `node_modules/`, `.next/`, `.vercel/`을 포함합니다.
- public link, Korean product language, privacy, release readiness, branch-protection planning을 위한 local hygiene tool.

## 아직 없는 것

- production-grade 설치와 platform support,
- broad real OS keyring read/write adapter beyond narrow Tiro Windows Credential Manager read, secret retrieval for other providers, OAuth flow, OpenAI API call, paid OCR API call,
- 첫 approval-gated local IMAP header scan과 첫 approval-gated local Notion ancestor structure fetch를 넘어서는 broad live provider sync,
- production `ZET` transport, sharing service, feed update, mirroring delivery,
- real wallet creation, private-key custody, cryptographic signing, token mechanics, payments, staking, consensus, blockchain integration,
- recommendation fetching, ranking, automatic neighbor feed update, provider-backed recommendation service,
- projection-plan apply/write, projection receipt, WordPress publishing, provider-specific publishing,
- real foreign block import/trust/apply, signed attestation statement, receiver-side acceptance, automatic shared-block renewal,
- complete prompt-injection prevention, full-auto execution, model training, backpropagation, Redis, queues, background workers,
- stable `v1.0.0` protocol guarantee.

## 핵심 모델

기본 WOM archive 모델은 다음과 같습니다.

```text
원본/source 데이터 + 메타데이터 + 민팅된 zets
```

쉽게 말하면:

- source/original data는 증거 레이어입니다.
- metadata는 원본을 찾고 검증할 수 있게 해줍니다.
- minted zet는 사람이 승인한 archive memory입니다.

이 시스템은 social app이 아니라 archive node에서 출발합니다.

현재 명칭 기준은 [Naming And Terminology](wom-kit/docs/concepts/naming-and-terminology.ko.md)를 보세요.

인간 데이터 원형, AX 흐름에서의 의미, Web3-like `ZET` 통신 모델까지 포함한 전체 설계 철학은 다음 문서를 보세요.

- [기초 제품 백서](wom-kit/docs/concepts/foundational-product-whitepaper.ko.md)
- [Product Philosophy](wom-kit/docs/concepts/product-philosophy.md)
- [한국어 Product Philosophy](wom-kit/docs/concepts/product-philosophy.ko.md)
- [WOM Safe HTML Profile](wom-kit/docs/concepts/wom-safe-html-profile.ko.md)
- [한국어 제품 언어 기준선](wom-kit/docs/concepts/korean-product-language-baseline.ko.md)
- [한국어 제품 언어 Hygiene](wom-kit/docs/korean-product-language-hygiene.md)
- [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md)
- [Agent Operator Capabilities Manifest](wom-kit/docs/agent-operator-capabilities.md)
- [Operator Feedback Lifecycle](wom-kit/docs/operator-feedback-lifecycle.md)
- [Approval Handoff Lifecycle](wom-kit/docs/approval-handoff-lifecycle.md)
- [Approval Handoff Audit](wom-kit/docs/approval-handoff-audit.md)
- [Operation Status Taxonomy](wom-kit/docs/operation-status-taxonomy.md)
- [Input Provenance Taxonomy](wom-kit/docs/input-provenance-taxonomy.md)
- [Secret Signal Taxonomy](wom-kit/docs/secret-signal-taxonomy.md)
- [AI Response Contract](wom-kit/docs/ai-response-contract.md)
- [Operator Envelope Classes](wom-kit/docs/operator-envelope-classes.md)
- [Objet Capture Enablement](wom-kit/docs/capture-enablement.md)
- [Archive Status Board](wom-kit/docs/archive-status-board.md)
- [First-Read Readiness](wom-kit/docs/first-read-readiness.md)
- [명시적 초록 데이터 발행 게이트](wom-kit/docs/explicit-abstract-publication.md)
- [초록 데이터 최신성 검진](wom-kit/docs/abstract-freshness.md)
- [정본 zet 3건 초록 데이터 보완 표본 절차](wom-kit/docs/abstract-backfill-pilot.ko.md)
- [Derived Artifact Staleness](wom-kit/docs/derived-artifact-staleness.md)
- [zet Quality Check](wom-kit/docs/zet-quality-check.md)
- [Public Privacy Hygiene](wom-kit/docs/public-privacy-hygiene.md)
- [Release Readiness Gate](wom-kit/docs/release-readiness-gate.md)
- [Main Branch Protection Readiness](wom-kit/docs/main-branch-protection-readiness.md)
- [ZET Shared Update Record Baseline](wom-kit/docs/zet-shared-update-record-baseline.md)
- [ZET Shared Update Record Review Preview](wom-kit/docs/zet-shared-update-record-review-preview.md)
- [ZET Shared Update Record Review Index](wom-kit/docs/zet-shared-update-record-review-index.md)
- [Shared Update Attestation Review Write](wom-kit/docs/shared-update-attestation-review-write.md)
- [Shared Update Route Preview](wom-kit/docs/shared-update-route-preview.ko.md)
- [ZET Transport Threat Model](wom-kit/docs/zet-transport-threat-model.md)
- [v0.2.x Freeze And v0.3.0 Entry Boundary](wom-kit/docs/v02x-freeze-v03-entry-boundary.md)
- [공개 문서 지도](wom-kit/docs/public-documentation-map.ko.md)
- [Credential Store Contract](wom-kit/docs/credential-store-contract.md)
- [Credential Ref Inventory And Onboarding](wom-kit/docs/credential-ref-inventory-and-onboarding.md)
- [Credential Store Recommendations](wom-kit/docs/credential-store-recommendations.md)
- [Credential Vault Onboarding Plan](wom-kit/docs/credential-vault-onboarding-plan.md)
- [Beginner Setup Manual](wom-kit/docs/beginner-setup-manual.md)
- [Notion Connection Plan](wom-kit/docs/notion-connection-plan.md)
- [Notion OAuth Connection Preflight](wom-kit/docs/notion-oauth-connection-preflight.md)
- [Notion Recover](wom-kit/docs/notion-recover.md)
- [Tiro Import Plan](wom-kit/docs/tiro-import-plan.md)
- [Connected Accounts](wom-kit/docs/connected-accounts.md)
- [Credential Plaintext Migration Plan](wom-kit/docs/credential-plaintext-migration-plan.md)
- [Credential Access Broker Plan](wom-kit/docs/credential-access-broker-plan.md)
- [Credential Access Approval Plan](wom-kit/docs/credential-access-approval-plan.md)
- [Credential Policy Check](wom-kit/docs/credential-policy-check.md)
- [Credential KeePassXC Command Plan](wom-kit/docs/credential-keepassxc-command-plan.md)
- [Credential KeePassXC Write](wom-kit/docs/credential-keepassxc-write.md)
- [Credential Adapter Readiness Plan](wom-kit/docs/credential-adapter-readiness-plan.md)
- [Credential Adapter Manifest Plan](wom-kit/docs/credential-adapter-manifest-plan.md)
- [Credential Adapter Audit Plan](wom-kit/docs/credential-adapter-audit-plan.md)
- [Human Artifact Store Contract](wom-kit/docs/human-artifact-store-contract.md)
- [Object Storage Recommendations](wom-kit/docs/object-storage-recommendations.md)
- [IMAP Mailbox Source](wom-kit/docs/imap-mailbox-source.md)
- [Zettel Objet Links](wom-kit/docs/zettel-objet-links.md)
- [Derived Text Coverage And Toolchain](wom-kit/docs/derived-text-coverage-and-toolchain.md)

공개 프로젝트 기록은 의도적으로 다음처럼 분리합니다.

```text
제품 기획안 / 설계 철학
구현을 위한 레퍼런스 조사
구현 계획
작업일지
```

## zet란 무엇인가?

`zet`는 항상 텍스트입니다.

사람이 직접 쓰거나, AI가 초안을 만들고 사람이 감독/승인한 문서입니다. 민팅되면 private archive 안의 공식 기록이 됩니다.

v0.2에서는 authoring/import compatibility를 위해 Markdown 기반 zets를 유지합니다. 장기 canonical/interchange/rendering target은 arbitrary HTML이 아니라 [WOM Safe HTML Profile](wom-kit/docs/concepts/wom-safe-html-profile.ko.md)입니다.

민팅이란:

```text
draft zet -> human review -> canonical private archive record
```

민팅은 공개 게시가 아닙니다. 외부 공유는 별도 행동입니다.

## 왜 중요한가?

대부분의 도구는 사용자를 앱의 구조에 맞추게 합니다.

WOM은 반대로 접근합니다.

```text
사용자의 archive가 중심이고,
AI는 기억을 정리하고 연결하는 조력자이며,
공유는 private memory에서 의도적으로 떼어내는 projection입니다.
```

미래의 `ZET` 통신 계층은 다음 모델을 따릅니다.

```text
1:1 ZET 관계       -> 메신저
1:다수 ZET 관계    -> SNS / feed
다수:다수 ZET 관계 -> 협업 워크스페이스
```

## 저장 모델

오브제 저장소는 사진/영상만 넣는 곳이 아닙니다.

WOM 제품 언어에서 Git 밖에 두는 source/original file은 `objet`/오브제입니다. Cloud provider API에서만 기술 용어 `object storage`를 씁니다.

원본으로 사용되는 문서와 캡처도 source/original objet입니다.

- `.hwp`
- `.hwpx`
- `.docx`
- `.xlsx`
- `.pdf`
- `.txt`
- `.md`
- `.csv`
- 스크린샷
- 오디오/비디오
- provider export

추천 기본 구조:

```text
원본 source 파일 -> local objet store 또는 object storage provider
object identity  -> object manifest
derived text     -> provenance가 있는 derived text record
zets와 metadata  -> Git repository
search text      -> SQLite/search index
```

자세한 내용은 [Source Object Storage Policy](wom-kit/docs/source-object-storage-policy.md)를 보세요.

## 텍스트 provenance

모든 텍스트가 같은 권위를 갖지는 않습니다.

WOM은 텍스트를 다음처럼 구분합니다.

```text
L0 원본 source object
L1 원래부터 편집 가능한 born-digital text
L2 parser로 추출한 text
L3 OCR / 음성인식 / AI 전사 text
L4 사람이 검토한 derived text
L5 minted zet
```

OCR과 AI 전사는 유용하지만, 모델에 따라 달라질 수 있는 derived record입니다. 따라서 source object id, derivation method, tool/model version, confidence, review status를 남겨야 합니다.

자세한 내용은 [Text Provenance Hierarchy](wom-kit/docs/text-provenance-hierarchy.md)를 보세요.

## 버전 관리

WOM, `zettel-kasten`, `zet`, `ZET`는 버전이 있는 protocol family로 관리합니다.

Release tag는 compatibility checkpoint입니다.

```text
v0.3.249 (현재 checkpoint)
```

`v0.2.5` 이후의 공개 릴리스에는 compatibility checkpoint tag가 붙습니다. 전체
릴리스 이력은 [CHANGELOG.md](CHANGELOG.md)와
[GitHub releases 페이지](https://github.com/mow-coding/zettel-kasten/releases)에
있고, [VERSIONING.md](VERSIONING.md)는 버전 관리 정책을 설명합니다.

v0.3.x 라인의 주요 compatibility checkpoint로는
v0.3.137 pre-release, v0.3.134 pre-release, v0.3.133 pre-release,
v0.3.123 pre-release, v0.3.122 pre-release, v0.3.117 pre-release,
v0.3.116 pre-release, edge-write 기준인 v0.3.109 pre-release,
compatibility checkpoint인 v0.3.87 pre-release가 있습니다. v0.2.x 라인은
v0.2.60에서 닫혔고, freeze 직전 checkpoint는 v0.2.57, v0.2.56, v0.2.55,
v0.2.54입니다.

같은 major version은 핵심 규칙을 공유해야 합니다. 다른 major version 사이에는 migration이나 compatibility bridge가 필요할 수 있습니다.

자세한 내용은 [Versioning](VERSIONING.md)과 [업그레이드 가이드](UPGRADE.ko.md)를 보세요.

## 저장소 구조

```text
wom-kit/
  specs/        제품/프로토콜 명세
  docs/         설치, 보안, 온보딩, 릴리스, 운영 문서
  plans/        구현 계획과 공개 가능한 작업일지
  schemas/      JSON Schema
  src/          Python package code
  cli/          local CLI entrypoint
  examples/     fake sample archive data
  templates/    personal, family, company archive template
```

## 공개 문서 지도

공개 문서는 목적에 따라 나뉩니다.

- 제품 기획안 / 설계 철학: [공개 문서 지도](wom-kit/docs/public-documentation-map.ko.md)
- 구현을 위한 레퍼런스 조사: [Implementation Research](wom-kit/specs/zettelkasten-zet-implementation-research.md)
- 구현 계획: [Plans Directory](wom-kit/plans/)
- 작업일지: [Work Logs](wom-kit/plans/)

코드부터 보기 전에 프로젝트를 이해하고 싶다면 [공개 문서 지도](wom-kit/docs/public-documentation-map.ko.md)부터 읽는 것을 추천합니다.

## 빠른 검증

```bash
cd wom-kit
python -m unittest discover -s tests
python cli/archive.py doctor examples/fake-life-archive --strict
```

기대 결과:

```text
tests pass
doctor reports 0 errors and 0 warnings
```

## 공개/비공개 경계

이 공개 저장소는 실제 사용자의 private archive가 아닙니다.

커밋하면 안 되는 것:

- provider token,
- local credential,
- 실제 private zet,
- 실제 source map,
- 실제 receipt,
- private AI conversation,
- 개인 파일이나 미디어,
- 로컬 PC 경로 또는 private filename.

실제 사용은 private archive repository와 별도 오브제 저장소/object storage provider에서 이루어져야 합니다.

자세한 내용은 [Open Source Publication Model](wom-kit/docs/open-source-publication-model.md)을 보세요.

## 저자

Original concept, product philosophy, naming, written design, schemas, reference implementation:

```text
Kim Seong Kyun (김성균)
Department of Urban Sociology, University of Seoul
GitHub: mow-coding
Email: mow.coding@gmail.com
Email: ellie0129@uos.ac.kr
```

이 프로젝트가 도움이 되었다면 GitHub star를 남겨주세요. 협업 및 투자 문의는 이메일로 연락할 수 있습니다.

## 라이선스

MIT License. [LICENSE](LICENSE)를 확인하세요.
