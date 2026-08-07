# AI Command-Path Routing

Status: implemented in v0.3.278, extended through v0.3.304

## Purpose

WOM must tell an AI not only where archive data lives, but which official
command performs each archive action.

A location-only instruction such as "drafts go in `inbox/`" is incomplete.
An AI may interpret it as permission to write Markdown directly, bypassing
frontmatter validation, provenance, deterministic replay, approval, and
receipts. Likewise, raw grep or raw SQLite may be useful diagnostics but do
not carry WOM search completeness and truncation semantics.

v0.3.278 added the first read-only routing contract:

```text
wom-kit/ai-command-path-routing/v0.1
```

v0.3.279 extends it additively with the official inbox pipeline audit route:

```text
wom-kit/ai-command-path-routing/v0.2
```

v0.3.280 extends it again with the official read-only event-membership
planning route:

```text
wom-kit/ai-command-path-routing/v0.3
```

v0.3.281 completes the matching approved-add and interruption-recovery route:

```text
wom-kit/ai-command-path-routing/v0.4
```

v0.3.282 adds the separate read-only event-membership removal-plan route:

```text
wom-kit/ai-command-path-routing/v0.5
```

v0.3.283 hardens the retained-journal and recovery-evidence boundary beneath
those same commands. It deliberately keeps routing at v0.5: no route, command,
alias, schema version, or MCP surface is added.

v0.3.284 adds the separate approval-gated removal writer and its read-only
recovery-plan/separately approved recovery routes:

```text
wom-kit/ai-command-path-routing/v0.6
```

v0.3.293 adds explicit operator-feedback sequencing and runtime-guidance
readiness discovery:

```text
wom-kit/ai-command-path-routing/v0.7
```

v0.3.294 adds the checked-layer rediscovery route that must precede any
global objet/source absence claim:

```text
wom-kit/ai-command-path-routing/v0.8
action: plan_objet_rediscovery_before_negative_claim
```

v0.3.298 adds the bounded private generated-index lookup command. This is an
official read route, not a global absence route:

```text
archive find-objet <archive-root> --audience private_archive \
  --query-profile literal_unicode --query-stdin --format json
```

v0.3.299 advances the routing envelope to:

```text
wom-kit/ai-command-path-routing/v0.9
action: inspect_observed_source_coverage_and_recorded_storage_evidence
```

The exact route is:

```text
python -B -m wom_kit.archive_cli source-reference-coverage-audit \
  <archive-root> --dry-run --format json
```

It is authoritative only for safely traversed current canonical `source_refs`,
exact Notion omission markers, and separately recorded local storage evidence.
It does not supply an archive-wide source population or a live storage check.

v0.3.302 advances the routing envelope to:

```text
wom-kit/ai-command-path-routing/v0.11
```

v0.3.303 adds the bounded read-only local artifact lifecycle checkpoint and
advances the routing envelope to:

```text
wom-kit/ai-command-path-routing/v0.12
action: inspect_artifact_lifecycle
```

The additive routes cover:

- provider-neutral locator plan, record, recovery, and exact revert;
- frontmatter-only relation candidates and separately approved human
  judgments;
- third-party Principal registration, privacy-safe listing, in-use-guarded
  unregistration, and Principal edge targeting;
- selected base link-type adoption and receipt-bound revert, including the
  manual-only `sequence` rule;
- markup style/plan, approved normalization, interruption resume/rollback,
  and exact-byte revert;
- whole-request batch Objet capture with per-item convergence; and
- verified untracked project-bytecode cleanup.

These routes do not convert a candidate into an edge, a locator into remote
availability proof, or a batch into an all-or-nothing transaction.

The feedback route is ordered and an AI must not skip the human gate:

```text
operator-feedback-plan --dry-run
operator-feedback-ledger --dry-run
required human review
operator-feedback-record --intent create|update --dry-run
operator-feedback-record --intent create --approve --reviewed-by <human-actor>
operator-feedback-record --intent update --expected-record-sha256 <sha256> --approve --reviewed-by <human-actor>
```

This is guidance, not proof that the earlier steps or human review occurred.
The record command requires an attributed reviewer for approval but does not
technically verify plan, ledger, preview, or independent human-review
evidence. The route therefore reports `approval_inferred: false`; operators
and AI hosts remain responsible for following and reviewing the full sequence.

It is returned by:

- `archive runtime-context <archive-root> --format json`;
- `archive ai-start-here <archive-root> --dry-run --format json`;
- `archive operational-context <archive-root> --dry-run --format json`;
- `canonical_entrypoints.action_routing`.

## Session Entry

Every generated archive `AGENTS.md` now starts with:

```text
archive ai-start-here <archive-root> --dry-run --progress --format json
```

The AI reads `action_routing` before searching, reading broadly, or proposing
a write. This closes the old one-way guidance loop in which `ai-start-here`
could point to `AGENTS.md` but `AGENTS.md` did not point back to
`ai-start-here`.

Existing archives are not silently rewritten. Their current `AGENTS.md`
remains under local owner control. v0.3.278 updates new-archive templates, the
packaged runtime skill, the fake archive, and live read-only command output.

## Official Read Routes

| Goal | Official command | Boundary |
| --- | --- | --- |
| Enter or resume an archive | `archive ai-start-here <archive-root> --dry-run --progress --format json` | Quick mode is not a full archive health claim. |
| Search archive records | `archive search <archive-root> <query> --count-total --format json` | Inspect complete/truncated metadata. Raw grep and raw SQL are not authoritative WOM search results. |
| Find an objet by a reviewed private-name alias | `archive find-objet <archive-root> --audience private_archive --query-profile literal_unicode --query-stdin --format json` | Exact generated-index equality only. `not_found_in_index` means no match in the complete current private index, not global absence. |
| Plan checked-layer rediscovery before a global absence claim | `archive objet-rediscovery-plan <archive-root> <query> --dry-run --count-total --format json` | Preserves index completeness as snapshot-only evidence, lists all ten fixed layers, echoes no private query/results, and supports no global absence claim while any applicable or unknown layer is incomplete. |
| Inspect observed source-reference coverage separately from recorded storage evidence | `python -B -m wom_kit.archive_cli source-reference-coverage-audit <archive-root> --dry-run --format json` | Covers only current canonical `source_refs` and exact Notion omission markers. It has no archive-wide denominator and performs no live byte/storage check. |
| Inspect installed version truth | `archive version <project-or-archive-root> --format json` | Proves local runtime/source/pin and already-fetched tag state; it does not verify remote release freshness. |
| Inspect saved-view state | `archive view-health <archive-root> --dry-run --format json` | Follow with `view-recommendation-plan`; both are read-only. |
| Inspect declared local artifact lifecycle state | `archive artifact-lifecycle-inventory <archive-root> --dry-run --format json` | Covers only fixed archive-owned lifecycle roots and exact generated-index files. It reports incomplete coverage, grants no deletion authority, reads no ordinary artifact body or object byte, and checks no provider or sibling object store. |
| Inspect possible historical inbox pipeline bypasses | `archive inbox-pipeline-audit <archive-root> --dry-run --format json` | Structural classes are conservative signals, not proof of command execution; no automatic repair exists. |
| Plan one explicit event membership set | `archive activity-group-membership-plan <archive-root> --request .wom-scratch/private/activity-groups/<reviewed>.json --dry-run --progress --format json` | The private request must contain one human-selected event anchor and ordered member ids. The command infers no member and writes nothing. |
| Plan removing one explicit event membership from selected zets | `archive activity-group-membership-removal-plan <archive-root> --request .wom-scratch/private/activity-group-removals/<reviewed>.json --dry-run --progress --format json` | The private request must contain the exact human-selected event anchor and ordered member ids. It writes nothing; continue only through the exact request/review digests and dedicated removal writer. |
| Discover installed commands | `archive capabilities --machine --format json` | Use the installed inventory before declaring that WOM lacks a command. |

## Official Write Routes

Every write remains preview-first and human-reviewed.

| Goal | Preview | Approved route or boundary |
| --- | --- | --- |
| Create an AI-assisted draft | `archive create-draft <archive-root> --title <title> --body-file <private-body-file> --creation-mode ai_assisted --created-by <ai-actor> --dry-run --format json` | Replay the preview's `draft_id`, `created_at`, and `expected_body_sha256` with `--draft-approved-by <human-actor>`. Never write Markdown directly into `inbox/`. |
| Mint a reviewed draft | `archive mint-zet <archive-root> --zettel-id <draft-id> --dry-run --format json` | Use the separate `--approve --reviewed-by <human-actor>` path. Draft approval is not mint approval. |
| Add a typed edge | `archive zettel-edge <archive-root> --from-zettel <id> --target <ref> --edge-type <type> --dry-run --format json` | Use the separate `--approve --reviewed-by <human-actor>` path and retain its receipt. |
| Capture source material | `archive source-intake <archive-root> --dry-run --local-path <file> --format json` | Continue through `source-intake-record`, `objet-capture-selection`, and `objet-capture`; a source-intake preview alone grants no copy/upload authority. |
| Update operating context | `archive operational-context <archive-root> --record workbench/operational-context.next.yml --dry-run --format json` | Use the separate `--approve --reviewed-by <human-actor>` path and retain its receipt. |
| Create a persistent saved-view | Run `view-recommendation-plan`, then preview `archive saved-view-write <archive-root> --request .wom-scratch/private/saved-views/<reviewed>.json --dry-run --format json` | Approve only the exact fresh plan using `--expected-plan-sha256`, `--approve`, `--reviewed-by`, and `--affirm-view-reviewed`. Never edit `views/*.yml` directly. |
| Revert a WOM-written saved-view | `archive saved-view-revert <archive-root> --receipt receipts/views/<receipt>.saved-view-write.json --dry-run --format json` | Approve only the exact fresh revert plan. It refuses changed bytes and never removes a human-authored view. |
| Add reviewed event memberships | Run `activity-group-membership-plan`, then preview `archive activity-group-membership-write <archive-root> --request <private-reviewed-request> --expected-request-sha256 <sha256> --expected-review-plan-sha256 <sha256> --dry-run --progress --format json` | Approve the same digest-bound writer with `--approve --reviewed-by <human-actor> --affirm-memberships-reviewed`. It writes a journal and receipt; it does not infer or remove memberships. |
| Recover an interrupted event-membership write | `archive activity-group-membership-recovery-plan <archive-root> --expected-request-sha256 <sha256> --dry-run --format json` | First confirm the old writer is no longer running. Approve only the exact recovery-plan digest with `activity-group-membership-recover`; unknown drift remains a manual forensic hold. |
| Remove reviewed event memberships | Run `activity-group-membership-removal-plan`, then preview `archive activity-group-membership-removal-write <archive-root> --request <private-reviewed-request> --expected-request-sha256 <sha256> --expected-review-plan-sha256 <sha256> --dry-run --progress --format json`. | Approve the unchanged digest-bound writer with `--approve --reviewed-by <human-actor> --affirm-removals-reviewed`. It removes only explicitly reviewed anchors, writes a separate removal journal and receipt, and performs no inference. |
| Recover an interrupted event-membership removal | `archive activity-group-membership-removal-recovery-plan <archive-root> --expected-request-sha256 <sha256> --dry-run --format json` | First confirm the old removal writer is no longer running. Approve only the exact recovery-plan digest with `activity-group-membership-removal-recover`; unknown drift remains `manual_forensic_hold`. |

## Safety And Compatibility

- All new runtime routing output is read-only and deterministic.
- It reads no zettel body or objet byte merely to produce the route table.
- It calls no provider, model, network, database, or credential store.
- It writes no archive, host configuration, or existing `AGENTS.md`.
- The routing object has its own schema, so the existing
  `ai-start-here/v0.3` response remains additively compatible.
- v0.3.302 advances routing to
  `wom-kit/ai-command-path-routing/v0.11` and adds the separate digest-bound
  saved-view write and exact-revert routes.
- v0.3.303 advances routing to
  `wom-kit/ai-command-path-routing/v0.12` and adds the read-only
  `inspect_artifact_lifecycle` route without adding a cleanup route.
- v0.3.293 advances routing to
  `wom-kit/ai-command-path-routing/v0.7` and adds the complete
  operator-feedback sequence without changing existing action contracts.
- v0.3.294 advances routing to
  `wom-kit/ai-command-path-routing/v0.8`, adds checked-layer rediscovery before
  a negative claim, and preserves v0.3.293 readiness and feedback semantics.
- Human approval is still required for every listed write route.

## v0.3.279 Detection Boundary

v0.3.279 adds the separate conservative signal described in
[Inbox Pipeline Audit](inbox-pipeline-audit.md). It can distinguish current
`pipeline_shape_consistent`, `possible_out_of_pipeline_draft`, and
`insufficient_evidence` states.
It still does not prove which process created a file and does not
automatically rewrite, rename, delete, mint, promote, or repair any draft.

## v0.3.280 Event-Membership Boundary

v0.3.280 adds the read-only
[Activity-Group Membership Plan](activity-group-membership-plan.md). It
validates only the event anchor and ordered member ids already selected by a
human in one bounded private request. Search results, titles, dates, nearby
files, and existing edges never become membership automatically. The plan
returns content-free row states and exact hashes without ids, paths, titles,
facet values, or body text. It has no writer or removal mode.

## v0.3.281 Event-Membership Write Boundary

v0.3.281 adds the separate
[Activity-Group Membership Write And Recovery](activity-group-membership-write.md).
The writer accepts additions only after exact request/review hashes and human
approval. It revalidates under a lock, preserves before-state snapshots,
publishes a journal before mutation, and publishes a receipt last. Recovery is
a second digest-bound human approval and never guesses through unknown drift.
Membership discovery, membership removal writing, direct canonical editing,
and an MCP writer remain unavailable.

## v0.3.282 Event-Membership Removal-Plan Boundary

v0.3.282 adds the read-only
[Activity-Group Membership Removal Plan](activity-group-membership-removal-plan.md).
It validates only one explicit private removal request, exact live canonical
bytes, and the existing event-anchor contract. It classifies
`ready_to_remove`, `already_absent`, and `blocked` rows, computes exact
current/proposed hashes, and infers no removal from search, title, time,
proximity, edges, or the generated index.

The route reports removal planning as implemented and removal writing as
unimplemented. It grants no approval, receipt, direct edit, or MCP write
authority.

## v0.3.283 Retained-Journal Isolation Boundary

v0.3.283 changes no route name or routing version. The existing approved-add
writer now performs a bounded, content-free direct-child scan of both
activity-group private roots before attempting the writer lock and again under
that shared lock. A retained add journal or reserved future-removal journal
blocks a new add.

Recovery now accepts completed evidence only when the immutable receipt exactly
matches the retained journal or lock on their shared fields and ordered items.
The raw receipt SHA-256 and transaction-binding SHA-256 are part of the
recovery-plan digest and are verified again immediately before cleanup.
Foreign, malformed, mismatched, or changed evidence stays in a non-executable
forensic hold. This hardening does not implement removal; the removal writer is
deferred to v0.3.284.

## v0.3.284 Event-Membership Removal Write Boundary

v0.3.284 adds the separate
[Activity-Group Membership Removal Write And Recovery](activity-group-membership-removal-write.md)
route. It continues only from the exact private removal request and read-only
review-plan digest, requires an attributed reviewer plus explicit
removal-review affirmation, and rebuilds the plan under the shared
activity-group writer lock before mutation.

Addition and removal share one global lock and one bounded two-root
transaction-evidence inventory. Their requests, journals, receipts, and
recovery contracts remain separate. `already_absent` review rows enter no
snapshot, journal participant, canonical write attempt, or receipt
participant.

Hard interruption routes through the separate read-only removal recovery plan
and exact digest-bound approved removal recovery command. Unknown drift is not
executable. No route infers membership, authorizes direct canonical editing,
exposes an MCP writer, or supplies a removal revert operation.
