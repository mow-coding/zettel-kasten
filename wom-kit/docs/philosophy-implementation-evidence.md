# WOM Philosophy Implementation Evidence

Status: v0.4.14 review of the v0.3.252 public traceability checkpoint
Date: 2026-08-29

## Purpose

WOM's philosophy must be more than persuasive prose. This document maps each
core claim to the runtime surface that applies it, the regression evidence that
protects it, and the boundary that WOM still cannot honestly prove.

The evidence is deliberately split into three layers:

1. **Engineering implementation**: a command, schema, receipt, runtime rule, or
   deterministic check exists in the public release.
2. **Real-use validation**: a human and an operating AI still need to test
   whether that mechanism preserves useful meaning in a real archive.
3. **Provider-specific future work**: a remote system needs a separate contract
   before WOM can claim that operation or completion state.

Passing an engineering check does not automatically satisfy the other two
layers.

## Traceability Matrix

| Philosophy claim | Implemented surface | Regression evidence | Honest boundary |
| --- | --- | --- | --- |
| The archive is durable memory; chat is temporary working memory. | The packaged Agent Skill starts every archive session from `ai-start-here`. `ops/operational-context.yml`, `ai-artifact-inventory`, and `session-handoff-checkpoint` create a receipt-backed handoff boundary. | `test_runtime_skill.py`, `test_runtime_skill_install.py`, and the session-handoff cases in `test_cli.py`. | WOM cannot read a host chat or prove semantic completeness. A human or host AI must explicitly review the conversation and capture what matters. |
| Original files and exports remain objets; a zet is the human-readable knowledge layer built with provenance above them. | Source intake, objet capture, object manifests, derived-text records, and mint provenance keep original bytes, extracted text, and reviewed zet meaning in separate layers. A reviewed conversation export or JSONL may enter the normal objet capture path instead of being pasted wholesale into a zet. | Objet capture, derived-text, manifest, source-link, and mint provenance cases in `test_cli.py`. | Registering an objet does not create a semantic zet. A human and AI must still decide what deserves interpretation, publication, or later retirement. |
| Time-situated artifacts and chronology outrank entity certainty. | Product philosophy, runtime guidance, revision receipts, exact prior-byte snapshots, revision audit, and snapshot-to-restore-proposal flow preserve evidence instead of silently normalizing it. | Documentation phrase checks in `test_artifact_primacy_docs.py`, plus behavioral revision/snapshot/restore cases in `test_cli.py`. | Guidance can block silent merges in WOM-operated workflows, but no structural check can prove a human interpretation or identity claim is true. |
| `canonical` means the current human-reviewed archive state, not objective truth. | Runtime instructions and revision workflows require review, exact hashes, approval, receipts, and recoverable prior bytes. | Artifact-primacy documentation tests plus canonical revision plan/write/audit/restore tests. | A receipt proves the bounded action and evidence, not timeless truth or universal agreement. |
| Reading accounts for every zet in the declared scope and uses abstracts only to order that reading. | `first-read-readiness`, strict paged `zet-catalog`, snapshot and continuation checks, token budgets, MCP continuation, and `zet-catalog-pass` account for every selected zet without making a generated map canonical. | Catalog and first-read cases in `test_cli.py`, `test_mcp_server.py`, and `test_zet_catalog_benchmark.py`. | Structural coverage does not prove abstract quality. Abstracts order reading; complete zet bodies and source evidence are still required when the human's goal needs them. Public language reserves `node` for the subject/archive participant, while graph code may use `zet vertex` internally. |
| Goal and loop belong to the host AI application's task UX, not to WOM's archive ontology. | `ai-start-here`, catalog continuation evidence, and the Agent Skill give Codex, Claude, or another host bounded memory and safe next actions without persisting one canonical WOM-owned goal or loop. | Runtime entrypoint, catalog continuation, and runtime-skill tests. | The host decides task branching, continuation, and completion. WOM records durable context and evidence but does not claim control of the host's session lifecycle. |
| Ties, edges, indexes, embeddings, and graphs are routes or reviewable claims, not authority. | Runtime guidance forbids silent identity merges; strict catalog traversal remains live-node based; the complete catalog artifact is private scratch with a SHA-bound read and approval-gated cleanup lifecycle. Receipt-bound locator recovery trusts a reference only when its historical operation, binding manifest, current target identity, and exact evidence all agree; disagreement removes that target from automatic resolution. | Runtime-skill and artifact-primacy documentation checks, behavioral catalog pass/read/cleanup tests, and v0.4.14 verified-reference conflict tests. | WOM has no global entity resolver. A verified historical reference accounts for a bounded locator-loss occurrence; it does not establish universal identity or prove a provider locator still exists. |
| Local reviewed state is authoritative; remote systems are backup or replica layers. | `local-sovereignty` declares the authority model. `backup-evidence` reports GitHub, object-storage, and external-database lanes without turning configuration into completion. The exact emergency preservation path can prove one manifest-bound remote object's bytes at execution time without calling it formal adoption. | Local-sovereignty and backup-evidence cases in `test_cli.py`, plus exact object-storage setup/preservation and capability/documentation checks. | There is no generic GitHub or external-database completion receipt. One HEAD plus complete GET rehash and its receipt prove only that exact object at the recorded operation; they do not prove current whole-archive backup completion. |
| Writes require human review, provenance, and an explicit approval boundary. | The supported exact workflows use a native TaskDialog, an authenticated durable `started` claim, writer-side revalidation, and workflow finalization. v0.4.14 may show a bounded filename, title, gist, role, or relation endpoint derived from the current SHA-bound plan so the person can recognize the target. Unsafe optional clues are omitted and never become durable authority. Routes without a complete operation-specific binding remain dry-run/plan/audit-only or unavailable and fail before sensitive reads or writes. | Exact-human workflow tests, privacy-filtered target-preview tests, and the CLI/help and service fail-closed suites. | WOM can verify the command boundary; it cannot infer that a person understood every semantic consequence. A preview clue and a historical approval receipt grant no current write authority. |
| AI-generated documents and conversation-derived work must not evaporate. | `ai-artifact-inventory` classifies local AI artifacts, operational context records unfinished work, and `session-handoff-checkpoint` blocks a clean handoff when durable capture evidence is missing or stale. | AI artifact inventory and session-handoff CLI tests. | The tool does not ingest chat automatically or decide which generated artifact deserves preservation. Human/AI review remains necessary. |
| AI operation should use progressive disclosure and plain human language. | The packaged Agent Skill has a compact root, goal-focused references, a machine-readable capabilities manifest, and a human-language response contract and terminology guide. Approval surfaces let WOM verify counts, hashes, and target state while the person decides only whether to perform the plainly described effect; safe local-only clues help identify the target without entering receipts or public output. | Runtime-skill package validation, capability tests, approval-preview privacy tests, and documentation contract tests. | Plain-language quality and good judgment are guidance-level behavior; WOM cannot deterministically validate every model response, and an omitted unsafe clue must never be replaced by leaked private context. |

## Current Engineering Conclusion

The public v0.4.14 implementation contains concrete, regression-checked
mechanisms for the Memento Problem: first-read reconstruction, artifact-first
reasoning, reviewed revision and recovery, durable session handoff, and honest
local backup evidence. These mechanisms are not merely roadmap prose.

The implementation is not proof that WOM is complete. The remaining boundary
is now mostly empirical or provider-specific:

- real archives must test whether abstracts remain semantically useful as the
  corpus changes;
- humans must test whether session handoffs preserve the decisions they
  actually care about;
- revision and restore workflows need continued real-use observation;
- GitHub and external-database completion need provider-specific evidence
  contracts before WOM can claim them;
- current remote object availability requires a live provider verification,
  not only local receipts.
- publishing or installing WOM does not apply a recovery to a client archive;
  that archive still needs its own approved execution, durable receipt, and
  independent post-write verification.

Those are explicit validation boundaries, not hidden implementation claims.
