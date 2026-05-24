# Responsible Use

Status: v0.2.26 baseline

WOM-kit은 local-first archive와 AI-runtime workflow를 위한 open-source tooling입니다.

## 기본 권장값

기본값은 human-in-the-loop입니다.

- dry-run을 먼저 실행합니다.
- blockers와 warnings를 확인합니다.
- write는 명시적으로 승인합니다.
- draft와 mint를 분리합니다.
- provider, signing, upload, permission action은 별도 승인을 둡니다.

## Operator 책임

Operator는 다음을 책임집니다.

- 선택한 AI runtime과 model,
- filesystem permission,
- provider permission,
- automation rule,
- secret과 credential,
- 외부 텍스트 import,
- agent-only 또는 full-auto 설정,
- 배포 선택의 결과.

## Full-Auto 경계

Full-auto / agent-only 운용은 고급/실험적 설정입니다.

financial, medical, legal, safety-critical, destructive, irreversible workflow에는 독립적인 통제, 로그, 리뷰, 전문 조언 없이 full-auto를 사용하지 마십시오.

## Maintainer 경계

Project maintainer는 prompt injection, malicious external content, unsafe automation, model failure, provider compromise, operator misconfiguration을 완전히 방지한다고 보장할 수 없습니다.

WOM-kit은 safety gate를 계속 개선해야 하지만, 실제 안전성은 operator가 agent와 permission을 어떻게 설정하는지에도 달려 있습니다.

## Production 사용

Production 또는 commercial deployment에는 독립적인 legal/security review를 권장합니다.
