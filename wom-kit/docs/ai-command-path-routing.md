# AI Command-Path Routing

Status: implemented in v0.3.278, extended through v0.3.283

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
| Inspect installed version truth | `archive version <project-or-archive-root> --format json` | Proves local runtime/source/pin and already-fetched tag state; it does not verify remote release freshness. |
| Inspect saved-view state | `archive view-health <archive-root> --dry-run --format json` | Follow with `view-recommendation-plan`; both are read-only. |
| Inspect possible historical inbox pipeline bypasses | `archive inbox-pipeline-audit <archive-root> --dry-run --format json` | Structural classes are conservative signals, not proof of command execution; no automatic repair exists. |
| Plan one explicit event membership set | `archive activity-group-membership-plan <archive-root> --request .wom-scratch/private/activity-groups/<reviewed>.json --dry-run --progress --format json` | The private request must contain one human-selected event anchor and ordered member ids. The command infers no member and writes nothing. |
| Plan removing one explicit event membership from selected zets | `archive activity-group-membership-removal-plan <archive-root> --request .wom-scratch/private/activity-group-removals/<reviewed>.json --dry-run --progress --format json` | The private request must contain the exact human-selected event anchor and ordered member ids. It writes nothing; the removal writer is not implemented. |
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
| Create a persistent saved-view | `archive view-recommendation-plan <archive-root> --dry-run --format json` | No dedicated writer exists. An AI must not edit `views/*.yml` directly. |
| Add reviewed event memberships | Run `activity-group-membership-plan`, then preview `archive activity-group-membership-write <archive-root> --request <private-reviewed-request> --expected-request-sha256 <sha256> --expected-review-plan-sha256 <sha256> --dry-run --progress --format json` | Approve the same digest-bound writer with `--approve --reviewed-by <human-actor> --affirm-memberships-reviewed`. It writes a journal and receipt; it does not infer or remove memberships. |
| Recover an interrupted event-membership write | `archive activity-group-membership-recovery-plan <archive-root> --expected-request-sha256 <sha256> --dry-run --format json` | First confirm the old writer is no longer running. Approve only the exact recovery-plan digest with `activity-group-membership-recover`; unknown drift remains a manual forensic hold. |
| Remove reviewed event memberships | First run `activity-group-membership-removal-plan`. | No approved removal writer exists in v0.3.283; it is deferred to v0.3.284. Preserve the private request and digest; do not edit canonical zets directly. |

## Safety And Compatibility

- All new runtime routing output is read-only and deterministic.
- It reads no zettel body or objet byte merely to produce the route table.
- It calls no provider, model, network, database, or credential store.
- It writes no archive, host configuration, or existing `AGENTS.md`.
- The routing object has its own schema, so the existing
  `ai-start-here/v0.3` response remains additively compatible.
- v0.3.283 retains `wom-kit/ai-command-path-routing/v0.5` and every existing
  activity-group v0.1 artifact schema.
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
