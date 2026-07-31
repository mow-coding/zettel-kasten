# Decision Log - v0.3.293 Runtime Guidance Readiness

Date: 2026-07-31

## Context

An archive can ship correct runtime guidance while an AI host lacks the Skill,
the repository lacks the exact versioned `AGENTS.md` routing contract, or
both. Conversely, the presence of files cannot prove that a particular host
consumed them.
Automatically performing host checks during every archive entry would mix a
portable archive read with host-specific machine inspection.

Operator feedback also had commands and storage, but the runtime entry map did
not express the complete plan-to-approval sequence and its human gate.

## Decision

- Add the explicit read-only command
  `archive runtime-guidance-readiness <archive-root> --host codex --scope repo
  --repo-root <repo-root> --format json`.
- Support only the explicit Codex/repository combination in v0.3.293.
- Inspect actual runtime Skill state and one bounded, sentinel-delimited,
  byte-exact repository `AGENTS.md` routing contract.
- Distinguish `runtime_skill_absent`, `agents_routing_contract_absent`,
  `agents_routing_contract_not_current`, unreadable evidence, and unsupported
  scope.
- Redact local paths and document bodies, expose archive identity only through
  an exact safe projection, report actual archive-configuration/AGENTS read
  observations separately from credential-store access, and perform no
  writes, network calls, provider calls, or credential-store access.
- Never auto-install a Skill or modify `AGENTS.md`; suggest only the exact
  `runtime-skill-install --dry-run` preview when applicable.
- Keep `host_guidance_consumption: not_proven` even when file readiness passes.
- Keep ordinary `runtime-context` and `ai-start-here` host-neutral:
  `runtime_guidance_readiness.status` is `not_checked` and includes the exact
  explicit command.
- Extend action routing to
  `wom-kit/ai-command-path-routing/v0.7` with this feedback order: plan
  dry-run, ledger dry-run, required human review, record dry-run, and explicit
  approval with `--reviewed-by`.
- Do not treat user knowledge objets as feedback metadata and do not claim
  external submission, human receipt, or inferred approval.

The command-bearing sequence is:

```text
archive operator-feedback-plan <archive-root> --dry-run --format json
archive operator-feedback-ledger <archive-root> --dry-run --format json
required human review
archive operator-feedback-record <archive-root> ... --dry-run --format json
archive operator-feedback-record <archive-root> ... --approve --reviewed-by <human-actor> --format json
```

## Consequences

Operators can diagnose two different installation/routing gaps without
confusing either with host behavior proof. Portable entry commands remain
fast and free of implicit machine inspection. Feedback guidance no longer
stops after discovery and cannot honestly skip the human review boundary.

This decision authorizes no public release by itself. Exact public v0.3.292
predecessor rebase, full verification, clean-wheel checks, and public artifact
evidence remain required before v0.3.293 is called release-ready.

Implementation evidence is recorded in
`meeting-minutes/2026-07-31-v03293-runtime-guidance-readiness-implementation.md`.

## Independent Review Correction

Two P1 findings were corrected before handoff:

- Ownership-manifest `package_version` is an untrusted local scalar. The
  runtime Skill parser and readiness projection now reuse the same exact
  stable-version validator as public project-version results. Invalid values
  are never echoed, become `null` with `invalid_or_untrusted`, and classify
  the managed target as invalid.
- A directory that exists but is not a readable WOM archive now returns the
  content-free `invalid_archive` blocked result. CLI dispatch also normalizes
  expected local inspection failures, so no traceback or absolute path crosses
  the command boundary.
- The same boundary covers malformed YAML, invalid text decoding, expected
  local read errors, missing/null/list identities, and empty or
  whitespace-only string identities. All are rejected before target
  resolution, runtime Skill inspection, or `AGENTS.md` inspection; a normal
  non-empty string identity is preserved.

These corrections preserve read-only behavior and add no write, install,
`AGENTS.md` rewrite, network, provider, model, or credential action.

## Exact-Final P1 Corrections

The final pre-push review found three additional P1 gaps. They are part of the
normative decision:

- A readable `archive_id` is not automatically shareable. WOM exposes it only
  when the existing safe projection equals the original string exactly.
  Otherwise fixed diagnostic `archive_identity_unshareable` is returned after
  one archive configuration read and before any host Skill or AGENTS
  inspection. The blocked constructor is pure and performs no retry I/O.
- Four phrases anywhere in `AGENTS.md` are not positive routing evidence. New
  personal, family, and company templates contain exactly one v0.3.293
  sentinel block. Readiness compares the inclusive block after CRLF-to-LF
  normalization only. The fixed current-authority sentence is inside the
  canonical unit; missing or internally negated/historical authority,
  quoted/fenced context, duplicate sentinels, reordering, truncation, or any
  other byte edit is rejected. Prose outside the sentinels is not parsed as a
  natural-language override, so examples and historical copies must be
  structurally quoted/fenced or byte-distinct. Legacy anchors are a human
  migration hint only.
- Stable manifest versions use ASCII digits, the exact
  `v?MAJOR.MINOR.PATCH` shape, and a 64-character raw-input ceiling.
  Unicode-digit and oversized inputs become `managed_invalid`, project
  `installed_version: null`, and are never echoed.

The exact public v0.3.292 merge
`4130c9ef4c68ce1445446f0964d5edc89745b0d9` became the implementation base
before these corrections were applied.
