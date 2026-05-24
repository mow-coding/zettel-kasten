# Responsible Use

Status: v0.2.27 baseline

WOM-kit is open-source tooling for local-first archives and AI-runtime workflows.

## Recommended Default

Use human-in-the-loop operation by default:

- run dry-runs first,
- review blockers and warnings,
- approve writes explicitly,
- keep minting separate from drafting,
- treat prompt-boundary low risk as heuristic context, not proof of safety,
- keep provider, signing, upload, and permission actions behind independent approval.

## Operator Responsibility

Operators are responsible for:

- selected AI runtimes and models,
- filesystem permissions,
- provider permissions,
- automation rules,
- secrets and credentials,
- imported external text,
- agent-only or full-auto configuration,
- consequences of deployment choices.

## Full-Auto Boundary

Full-auto / agent-only operation is advanced and experimental.

Do not use full-auto operation for financial, medical, legal, safety-critical, destructive, or irreversible workflows without independent controls, logs, reviews, and professional advice.

## Maintainer Boundary

Project maintainers cannot guarantee prevention of prompt injection, malicious external content, unsafe automation, model failures, provider compromise, or operator misconfiguration.

Prompt-boundary reports and draft `prompt_boundary` metadata are audit/context hints. They are not an LLM classifier, provider scanner, malware scanner, legal review, or guarantee that external text is safe.

WOM-kit should keep improving safety gates, but safety also depends on how operators configure agents and permissions.

## Production Use

Production and commercial deployments should receive independent legal and security review.
