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

통합된 v0.4.3 소스로 전체 Basoon mirror를 두 번 읽었다. 첫 번째 pass는
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
apply, native approval, rollback drill, Basoon project update, Git backup과 feedback
resolved 상태 갱신은 이 기록 시점에는 아직 수행하지 않았다.
