# Next Thread Prompt: Ownership Lineage Implementation

Use this prompt to start the next implementation thread.

```text
우리는 공개 예시 경로 C:\Users\example\dev\zettel-kasten 프로젝트에서 wom-kit을 만들고 있다.

나는 초보 바이브코더이지만 프로 개발자처럼 계획 -> 구현 -> 검증 -> 기록의 루프로 작업하고 싶다.
설명은 쉬운 말로 해주고, 중요한 결정은 meeting-minutes와 decision log에 남겨라.

이번 쓰레드의 목표:

Archive Lineage + Trust 설계를 다음 단계로 밀고 간다.
특히 owner/operator/subject/ownership transfer 모델을 기준으로 Phase 5 또는 Phase 7 작업을 시작한다.

핵심 설계원칙:

나는 남녀가 만나 사랑을 하고 가정을 이루고, 새로운 생명이 태어나고, 그 아이가 나중에 독립하는 과정과
사람들이 일을 하다가 서로 공유하고, 사업체를 만들고, 사업체가 커져서 인수합병되거나 분사되는 과정을
archive 관점에서는 같은 계보 모델로 본다.

감정적/법적 의미는 다르지만 archive 시스템의 기본 동작은 같다:

- identity
- owner
- operator
- subject
- scope gate
- trust gate
- ownership gate
- receipt
- fork
- merge
- exit/spin-out
- ownership transfer

중요한 구분:

- owner: archive의 실제 소유 주체. person, family, household, company, business_unit 같은 집단도 가능하다.
- operator: archive를 실제로 기록/정리/승인하는 사람 또는 역할.
- subject: archive 기록의 대상. 예를 들어 아이 archive에서는 아이가 subject이고, 처음 owner는 family일 수 있다.

예시:

아이 archive 초기 상태:

- owner: family:example-household
- operators: person:father, person:mother
- subject: person:child

아이 archive 이후 상태:

- owner: person:child
- operators: person:child, optional trusted helpers
- receipt: transfer_archive_ownership

회사/사업체 archive도 같은 모델을 사용한다:

- owner: company:parent-company
- operators: role:admin, person:founder
- business_unit이 exit/spin-out되면 owner가 바뀌고 receipt가 남는다.

현재 이미 구현된 것:

- archive-identity.yml
- archive-identity.schema.json
- ownership 블록: owner_id, owner_kind, operators, subjects, transfer_policy
- archive share --dry-run
- MCP share_check dry-run
- workpack scope_gate/trust_gate/ownership_gate/lineage metadata
- sensitive categories 기본 공유 차단
- counterparty fingerprint 검증
- Phase 4 lineage/trust 문서
- Phase 7 ownership transfer 계획 문서

다음 구현 후보:

1. transfer-ownership dry-run CLI를 만든다.
2. ownership_gate preview와 receipt preview를 만든다.
3. real transfer는 아직 하지 않는다.
4. MCP에는 ownership_transfer_check만 제공하고, 실제 transfer tool은 만들지 않는다.
5. family -> child ownership transfer 예제를 fake archive나 template에 추가한다.
6. company -> business_unit exit/spin-out ownership transfer 예제를 문서화한다.

안전 원칙:

- private by default
- 공유/합침/소유권 이전은 전체 archive가 아니라 view/workpack/manifest 단위로 시작한다.
- AI/MCP는 민감한 실제 이전을 실행하지 않고 dry-run/check만 한다.
- 실제 transfer는 나중에 CLI에서만, --approve와 --reviewed-by 같은 명시 승인 후에 가능하게 한다.
- 모든 중요한 변화는 receipt로 남긴다.
- 모든 archive-relative path는 / 기반으로 안정화한다.

작업 시작 시 먼저 확인할 파일:

- wom-kit/specs/archive-identity.md
- wom-kit/specs/archive-lineage.md
- wom-kit/plans/phase-7-ownership-transfer-plan.md
- wom-kit/schemas/archive-identity.schema.json
- wom-kit/src/wom_kit/archive_services.py
- wom-kit/src/wom_kit/archive_cli.py
- wom-kit/tests/test_cli.py
- meeting-minutes/2026-05-21-web3-ai-native-archive-framing.md
- archive-infra-decision-log-2026-05-21.md

검증:

- cd wom-kit
- python -m unittest discover -s tests
- python ../wom-kit/cli/archive.py doctor ../wom-kit/examples/fake-life-archive --strict

주의:

현재 폴더는 git repo가 아닐 수 있다. git status가 실패해도 이상한 것은 아니다.
테스트가 만든 __pycache__와 fake archive 부산물은 끝나고 정리해라.
```

