# AI Command-Path Routing

Status: implemented in v0.3.278, extended in v0.3.279

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
| Create a persistent saved-view | `archive view-recommendation-plan <archive-root> --dry-run --format json` | No dedicated writer exists in v0.3.278. An AI must not edit `views/*.yml` directly. |

## Safety And Compatibility

- All new runtime routing output is read-only and deterministic.
- It reads no zettel body or objet byte merely to produce the route table.
- It calls no provider, model, network, database, or credential store.
- It writes no archive, host configuration, or existing `AGENTS.md`.
- The routing object has its own schema, so the existing
  `ai-start-here/v0.3` response remains additively compatible.
- Human approval is still required for every listed write route.

## v0.3.279 Detection Boundary

v0.3.279 adds the separate conservative signal described in
[Inbox Pipeline Audit](inbox-pipeline-audit.md). It can distinguish current
`pipeline_shape_consistent`, `possible_out_of_pipeline_draft`, and
`insufficient_evidence` states.
It still does not prove which process created a file and does not
automatically rewrite, rename, delete, mint, promote, or repair any draft.
