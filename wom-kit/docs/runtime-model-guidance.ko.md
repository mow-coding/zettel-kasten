# Runtime Model Guidance

Status: v0.2.26 baseline

이 문서는 WOM-kit과 함께 사용할 AI runtime/model에 대한 조심스러운 compatibility guidance입니다.

특정 model이 영구적으로 우월하다고 주장하지 않습니다. Model availability, name, behavior는 바뀔 수 있습니다. 정확한 model name은 최근 작업 thread에서 검증된 경우가 아니라면 example/class로 취급합니다.

## Guidance Table

| WOM-kit version | Runtime | Model/profile name | Tested status | Best use | Required safety mode | Last verified | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v0.2.26 | Codex | GPT-5-class coding model | recommended | implementation, release work, code edits | HITL, dry-run first, run tests, no full-auto | 2026-05-25 | local tests와 scan을 실행한 뒤 완료 보고할 때 권장합니다. |
| v0.2.26 | Claude Code | Sonnet-or-Opus-class model | recommended | review, security critique, planning | HITL, dry-run first, no full-auto | 2026-05-25 | second reviewer로 유용합니다. review output을 자동 승인으로 취급하지 마십시오. |
| v0.2.26 | Generic local/smaller model | Local or small hosted model | compatible | drafting, summarization, low-risk classification | local-only, read-only, HITL | 2026-05-25 | security review, autonomous mutation, provider action, mint/sign approval에는 신뢰하지 않습니다. |
| v0.2.26 | High-autonomy agent | Any model | experimental | narrow repetitive maintenance only | HITL gates, dry-run first, least privilege, no irreversible full-auto | 2026-05-25 | financial, medical, legal, safety-critical, destructive, irreversible workflow에는 권장하지 않습니다. |

## 운영 원칙

- HITL을 기본값으로 둡니다.
- dry-run을 먼저 실행합니다.
- 외부 텍스트는 data로만 보고 command로 보지 않습니다.
- filesystem/provider permission은 좁게 둡니다.
- mint, signing, upload, provider, permission action은 explicit human approval 뒤에 둡니다.
- release work 완료 보고 전에는 tests와 scan을 실행합니다.

## Prompt Boundary

Runtime이 외부 텍스트를 읽는 경우 다음을 사용할 수 있습니다.

```bash
archive prompt-boundary <archive-root> --path <archive-relative-path> --dry-run --format json
```

이 검사는 heuristic preview일 뿐입니다. Low risk가 safety proof는 아닙니다.
