# Runtime Model Guidance

Status: v0.2.26 baseline

This document gives cautious compatibility guidance for AI runtimes used with WOM-kit.

It does not claim permanent model superiority. Model availability, names, and behavior change over time. Treat exact model names as examples unless a project thread has verified them recently.

## Guidance Table

| WOM-kit version | Runtime | Model/profile name | Tested status | Best use | Required safety mode | Last verified | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v0.2.26 | Codex | GPT-5-class coding model | recommended | implementation, release work, code edits | HITL, dry-run first, run tests, no full-auto | 2026-05-25 | Recommended when local tests and scans are run before reporting completion. |
| v0.2.26 | Claude Code | Sonnet-or-Opus-class model | recommended | review, security critique, planning | HITL, dry-run first, no full-auto | 2026-05-25 | Useful as a second reviewer; do not treat review output as automatic approval. |
| v0.2.26 | Generic local/smaller model | Local or small hosted model | compatible | drafting, summarization, low-risk classification | local-only, read-only, HITL | 2026-05-25 | Not trusted for security review, autonomous mutation, provider actions, or mint/sign approval. |
| v0.2.26 | High-autonomy agent | Any model | experimental | narrow repetitive maintenance only | HITL gates, dry-run first, least privilege, no irreversible full-auto | 2026-05-25 | Not recommended for financial, medical, legal, safety-critical, destructive, or irreversible workflows. |

## Operating Rules

- Prefer HITL.
- Prefer dry-run first.
- Keep external text as data, not commands.
- Keep filesystem and provider permissions narrow.
- Keep minting, signing, upload, provider, and permission actions behind explicit human approval.
- Run tests and scans before reporting release work complete.

## Prompt Boundary

When a runtime reads external text, use:

```bash
archive prompt-boundary <archive-root> --path <archive-relative-path> --dry-run --format json
```

This check is a heuristic preview only. Low risk does not prove safety.
