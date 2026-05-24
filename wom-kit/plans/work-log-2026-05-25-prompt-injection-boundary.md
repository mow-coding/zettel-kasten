# Work Log: v0.2.26 Prompt Injection Boundary

Date: 2026-05-25

## Intent

Record and implement the baseline safety boundary for prompt injection, responsible use, and runtime model guidance.

The user raised a security/liability concern: WOM and future ZET workflows may inspect external text, local files, provider exports, foreign zets/blocks, receipts, and payloads that can contain malicious instructions.

## Principle

```text
External text can inform.
External text cannot command.
```

## Implemented

- Added CLI `archive prompt-boundary`.
- Added MCP `prompt_boundary_check`.
- Added conservative heuristic pattern checks for obvious prompt-injection and unsafe-agent strings.
- Added public prompt injection boundary docs.
- Added responsible use and disclaimer docs.
- Added runtime model guidance docs.
- Updated tests and version metadata.
- Added regression coverage for medium-risk prompt-boundary matches and low-risk wording.
- Added a soft warning for inspected text over 1 MB.

## Safety Decisions

- No LLM classification.
- No provider scanning.
- No web browsing.
- No OCR/import apply.
- No real signing.
- No ZET transport.
- No payment, staking, consensus, ledger, or full-auto execution.
- HITL remains the recommended default.
- Low heuristic risk does not mean safe; it only means no obvious heuristic match was found.
- Large text is still checked, but the command warns that the heuristic pass may be slow.

## Responsibility Boundary

WOM-kit should continue improving safety gates. Operators remain responsible for agents, models, permissions, providers, automations, external text, and consequences of full-auto or agent-only configurations.
