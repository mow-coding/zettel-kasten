# v0.4.4 인간 의사결정 경계

Date: 2026-08-24

## Decision

WOM은 manifest 해시, 대상 수, 정본 상태, drift와 completeness를 기계적으로
검증한다. 네이티브 승인창은 기술 증거를 사람이 검산하도록 요구하지 않고, 작업의
의미와 영향만 설명한 뒤 지금 실행할지라는 실제 의사결정 하나만 요청한다.

명시적인 작업 버튼이 interactive intent를 구성한다. 해시와 내부 검토 코드는
접힌 기술 세부정보와 durable receipt에 남기고, v0.3의 checkbox+button claim은
authenticated resume 호환을 위해 계속 읽는다.

## Consequences

- v0.4.3은 Letter 138 클라이언트 적용 완료가 아니다.
- v0.4.4가 공통 승인 UX와 검증본 전체 복구 시험을 닫은 뒤 클라이언트 적용을 안내한다.
- 실제 클라이언트 프로젝트의 설치와 데이터 변경은 클라이언트가 직접 승인하거나
  명시적으로 개발진에 위임해야 한다.
- 상세 근거는 숨기지 않지만 progressive disclosure로 분리하며 개인정보는 표시하지 않는다.

Long-form record:
`meeting-minutes/2026-08-24-human-decision-boundary-and-letter138-client-application.md`
