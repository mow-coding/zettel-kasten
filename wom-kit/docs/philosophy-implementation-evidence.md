# WOM Philosophy Implementation Evidence

Status: v0.4.45 candidate review of the v0.3.252 public traceability checkpoint
Date: 2026-09-17

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
| Writes require human review, provenance, and an explicit approval boundary. | The supported exact workflows use a native TaskDialog, an authenticated durable `started` claim, writer-side revalidation, and workflow finalization. v0.4.14 may show a bounded filename, title, gist, role, or relation endpoint derived from the current SHA-bound plan so the person can recognize the target. v0.4.15 restores an interrupted update's exact context from its live lock and authenticated sealed plan, accepts exactly one checkpoint-valid claim without caller-supplied identifiers or a second decision, and keeps ordinary writers blocked until convergence. The sole locked-state exception is separately exact-approved, create-only operator feedback body preservation; it cannot revise metadata or change `version-update.lock`. Unsafe optional clues are omitted and never become durable authority. Routes without a complete operation-specific binding remain dry-run/plan/audit-only or unavailable and fail before sensitive reads or writes. | Exact-human workflow tests, authenticated update-resume and emergency-feedback guard tests, privacy-filtered target-preview tests, and the CLI/help and service fail-closed suites. | WOM can verify the command boundary; it cannot infer that a person understood every semantic consequence. Resume reuses only the already-approved exact context; it does not grant authority to a new target. A preview clue and a historical approval receipt grant no current write authority. |
| AI-generated documents and conversation-derived work must not evaporate. | `ai-artifact-inventory` classifies local AI artifacts, operational context records unfinished work, and `session-handoff-checkpoint` blocks a clean handoff when durable capture evidence is missing or stale. | AI artifact inventory and session-handoff CLI tests. | The tool does not ingest chat automatically or decide which generated artifact deserves preservation. Human/AI review remains necessary. |
| AI operation should use progressive disclosure and plain human language. | The packaged Agent Skill has a compact root, goal-focused references, a machine-readable capabilities manifest, and a human-language response contract and terminology guide. Approval surfaces let WOM verify counts, hashes, and target state while the person decides only whether to perform the plainly described effect; safe local-only clues help identify the target without entering receipts or public output. | Runtime-skill package validation, capability tests, approval-preview privacy tests, and documentation contract tests. | Plain-language quality and good judgment are guidance-level behavior; WOM cannot deterministically validate every model response, and an omitted unsafe clue must never be replaced by leaked private context. |

v0.4.36 keeps a promise made to a person: the switch the user designed on
2026-09-17 means what he said it means, a writer that stops says why, and a
letter that has been delivered may leave the archive it never belonged to.

v0.4.35 keeps a promise made to a mirror: when the public record had to
change its past to protect a person, the updater learned to say so in
plain codes and to move only when a person affirmed it.

v0.4.34 gives a granted trust a face and a clock: the permission a person
gave one conversation now knows which conversation is using it and when it
ends, and the archive says so in the claim rather than hoping nobody else
found the keys.

v0.4.33 reopens a door with the same hand that closed it: the upload the
person has waited for is not a new mechanism but the composition of two the
archive already trusted — the preservation PUT and the adoption projection —
under one dialog, so what the archive learns from it is exactly what it
already knew how to verify.

v0.4.32 makes silence speak: a session start says how much of the person's
work Git does not yet hold, a blocked close says which file it could not read,
a lost snapshot says which probe failed and why, and a permission request can
be checked before a window asks for a decision. What the tool cannot prove it
now says plainly, in numbers, without reading anything it should not.

v0.4.31 makes a refusal teach: a blocked draft names the option it lacks, a
warning says which lines it read, a failed update names its family and the
shape of what stands in the way, and a write that would touch a stale index
says so before anyone is asked to approve it. The person learns the next
step from the refusal itself, never from a search through the code.

v0.4.30 keeps a refusal honest at the moment it happens: a mint that cannot
proceed says so before it takes a one-use claim, a failure names its fixed
cause instead of a generic word, and the claims that earlier failures left
open can be seen and closed by the person who reviewed them, with the
receipts saying exactly what was checked. Evidence of what did not happen is
never asserted beyond what was scanned.

v0.4.29 lets the local authority let go on its own terms: a local copy is
removed only after the remote copy has been re-read in full and proven, the
local bytes have been proven twice, no unfinished thought still depends on
them, and the manifest keeps a named, receipted, reversible mark in their
place. Freeing disk is a decision the person makes with the way back already
open, never a silent loss.

v0.4.28 makes the backup layer answer to the local authority: a remote copy
counts only when a complete download reproduces the object id, verified bytes
return to the local objet store as new files, never over an existing one, and
the remote object is never deleted. Local is canonical; the cloud is the way
back, and the way back now exists before any way out.

v0.4.27 keeps refusals informative without becoming leaks: a refused input
is named by its position and by the fixed vocabulary it should have used,
never by echoing what was typed, and a usage mistake is a fixed code rather
than a silent exit.

v0.4.26 keeps the human's reading step honest: the target list the person
asked to see now opens, and a page the dialog has not yet confirmed can be
read but never approved, so looking closer never costs the person the
decision they were about to make.

v0.4.25 keeps a recorded fact readable by the code that must act on it: the
locations an update preflight wrote were true relative to the root the person
named, and every consumer now reads them that way instead of guessing a
different root, so an approval given from the archive root is honoured and a
stuck transaction can be released without inventing a new decision.

v0.4.24 lets the person decide the boundary once per session instead of once
per write. A permission mode is a human decision recorded on the claimed
session; a write it permits still leaves its own one-use claim, and that claim
says it was minted by the session's mode rather than by a live dialog, so the
record never presents a dialogless write as a human-presence proof.

v0.4.23 extends the same boundary to two more cases. A binary original can
back a summary or derivative draft by its byte identity without any claim of
mechanical comparison, and a draft can be attributed to the claimed work
session by freezing content-free ownership facts into the very plan the
person approves, so the receipt says which session wrote it without echoing
any label or path.

v0.4.22 keeps the same boundary honest on its own failure path. A project
update that fails after the person approved it now names the fixed gate that
refused and the stage it stopped in, without carrying any text, path or
message; a claim that stayed `started` because nothing was written can be
closed by the operator only while the journal proves exactly that, and the
ordinary claimless cancellation releases the reservation. A slow disk is no
longer reported as a misconfigured origin.

v0.4.21 keeps the approval boundary honest while giving back the writers
that the v0.4.0 compound closure had taken away. Draft discard and restore,
the edge, mint, retire and revert batches, and the semantic revision pair
are reopened through the same operation-specific exact human approval as
every other v0.4 writer: a fresh private preflight, a content-free binding
of the exact plan, one native dialog, one authenticated one-use claim that
is re-verified before the first byte changes. A batch is one dialog over
every item's own binding, and each item write proves its fresh binding is
an approved item rather than assuming the batch approval covers it. The
three-step objet intake runs under one approval by planning every step from
the bytes the earlier steps will write; a failure after an earlier write is
reported as partial with the written paths instead of being hidden or
rolled back into a false clean state.

v0.4.20 extends honesty to WOM's own earlier writes. A draft that an older
`zettel-edge` rewrite left without its separator line is normalized and
reported as a warning, not refused as if the person had damaged it, and a
declared fidelity source linked as an asset is not reported as private
authority exposure. A blocked draft promotion says why instead of returning
replayable approval values. Archive writes may carry a work-session identity,
and the session's Git backup commits only what it can attribute to that
session with head, index and worktree proof; everything else stays
`ownership_unverified` rather than being claimed. The writer-session coverage
gate prints the exact count of integrated, pending and exempt approval paths
so that no document can claim all-writer coverage before the parser does.

v0.4.19 applies the same honesty rule to machine observation. An unreadable or
unreached check is not presented as a confirmed mismatch, absence, or success.
Updater preparation is revalidated by fixed privacy-safe dimension, and one
capability decision is shared from parser-facing guidance through actual
dispatch. This lets an AI explain whether work failed, was not attempted, or
could not be verified without asking a person to interpret hashes, paths, or
private machine state.

v0.4.18 keeps the human boundary operational instead of merely defensive.
Fresh preview and approval use the same machine classification, and exact
terminal control history, including a completed original the project has
moved past, routes to identifier-free recovery. WOM verifies the
private file set, identities, hashes, archive identity, and cleanup authority;
the person does not perform filesystem forensics or reproduce machine counts.
Only exact WOM-produced control history may converge to canonical proof
history, without a project-domain write or new approval authority. Weak,
changed, mixed, or unsafe evidence still stops. Safety therefore means both
refusing unsupported effects and completing a deterministic, evidence-bound
recovery when the evidence is sufficient.

v0.4.16 preserves authenticated update truth in a private durable terminal
handoff before cleanup and reauthenticates the exact succeeded claim and
postimage before reusing the exact bound output. The immutable journal and
`active` -> `display-pending` -> `consumed` handoff keep cleanup, independent
resource closes, and durable output truth separate; consumed state is history
and acknowledgement does not prove human or model observation. Exact complete
legacy residue may be recovered, but cleanup proof alone never attributes past
success or grants cleanup, handoff, or automatic retry authority. This makes
durable evidence survive a reporting failure without claiming that every
follow-up control step succeeded.

## Current Engineering Conclusion

The public v0.4.36 implementation contains concrete, regression-checked
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
