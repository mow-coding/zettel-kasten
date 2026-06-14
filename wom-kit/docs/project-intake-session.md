# Project Intake Session

Status: planning map
Date: 2026-06-06

This document explains how a user should bring one existing project folder into
WOM/MOW with AI help.

The canonical product term is:

```text
project intake session
```

In beginner-facing guidance, explain it as:

```text
one project folder at a time, inspected by the user and AI together
```

## 1. What It Is

A project intake session is a deliberate, conversation-driven workflow:

```text
temporary staged project folder
-> user + AI inspect the folder together
-> decide what each important item is
-> preserve originals as objets / object records
-> draft and mint zets gradually
-> verify preservation, provenance, and receipts
-> remove the temporary staged folder only after the final gate passes
```

It is not a silent bulk importer.

The current safe spine is intentionally step-by-step:

```text
project-intake-staging-guide
-> create the staged folder manually
project-intake-plan
-> project-intake-next-question
-> project-intake-decision-template
-> project-intake-decisions
-> project-intake-status
-> project-intake-next-question
-> project-intake-decision-template
-> project-intake-item-plan
-> source-intake --project-intake-receipt
-> source-intake-record
-> objet-capture --project-intake-receipt
-> derive-text capture when external text already exists
-> create-draft --source-intake-plan
-> mint-zet after explicit approval
-> staged-cleanup-check before any manual deletion
```

Each arrow is a review boundary. The project-intake receipt is session evidence,
not automatic permission to import, capture, draft, mint, upload, or clean.

The AI should not classify a whole folder, mint zets, upload originals, or delete
staged files without explicit review gates.

## 2. Recommended Local Paths

For a first personal WOM setup:

```text
local archive root:       C:\Users\<user>\zettel-kasten-<profile_slug>
local objet store:        C:\Users\<user>\zettel-kasten-<profile_slug>-objets
project intake staging:   C:\Users\<user>\zettel-kasten-<profile_slug>-objets\intake\<project_slug>
```

To ask WOM-kit for the recommended path before creating folders:

```text
archive project-intake-staging-guide <archive-root> --project-slug <project_slug> --dry-run
```

This guide writes nothing. It does not create folders, move files, copy files,
upload, capture, draft, mint, or clean. It is only the "where should I put this
one project before we review it?" answer.

The local archive root is the Git-friendly control plane.

The local objet store is the raw source/original file store.

The project intake staging folder is temporary. It is the place where one project
folder is reviewed before its durable records are created.

Use the artifact hygiene baseline when deciding what can be kept, rebuilt,
deferred, or cleaned:

```text
wom-kit/docs/artifact-hygiene.md
```

## 3. Archive Of Record

The staged folder is not the archive of record.

The durable records should be:

- objets in the local objet store and later optional provider storage,
- `objects/manifests/*.jsonl`,
- `source-maps/*.jsonl`,
- `inbox/` drafts when explicitly approved,
- minted zets under `zettels/`,
- receipts under `receipts/`,
- generated search indexes that can be rebuilt.

If the user uses an AI collaboration harness, the harness workspace is also not
the archive of record. Harness notes can be summarized into zets later, but raw
local collaboration files should remain local unless deliberately reviewed.

## 4. Current Primitives

WOM-kit already has safe primitives that can support parts of this flow:

| Area | Current surface | Current boundary |
| --- | --- | --- |
| Context | `archive runtime-context` | Read-only archive identity and safe-action context. |
| Health | `archive doctor --strict` | Validates the archive; does not migrate private data. |
| Upgrade safety | `archive upgrade-check --dry-run` | Reports upgrade-readiness signals; writes nothing and is not a migration engine. |
| Source registration | `archive add-source` | Can write source binding metadata only after approval. |
| Source scan | `archive scan-source` | Metadata-first; approved mode writes source maps and receipts. |
| Staging guide | `archive project-intake-staging-guide --dry-run` / MCP `project_intake_staging_guide` | Shows the recommended local objet-store staging path for one project slug. It creates no folders and moves no files. |
| Session planning | `archive project-intake-plan --dry-run` / MCP `project_intake_plan` | Plans one staged project folder session with top-level counts, human review checklist, suggested classification labels, and no writes. |
| Next question | `archive project-intake-next-question --dry-run` / MCP `project_intake_next_question` | Returns exactly one next human-review question for a new staged folder or continuing receipt. It includes placeholders only, does not echo decision values, and writes nothing. |
| Decision template | `archive project-intake-decision-template --dry-run` / MCP `project_intake_decision_template` | Builds the JSON shape for the next human-reviewed answer. It leaves `answer` empty, does not echo previous answers, and writes nothing. |
| Decision recording | `archive project-intake-decisions --dry-run|--approve` | Validates a user-reviewed checklist JSON file; approved mode writes a local receipt under `receipts/project-intake/` without running capture, drafting, minting, provider calls, or cleanup. |
| Decision status | `archive project-intake-status --dry-run` / MCP `project_intake_status` | Reviews one approved decisions receipt for checklist coverage and integrity, and returns `next_review_prompts` for missing checklist ids without echoing answer text or authorizing automatic execution. |
| Item plan | `archive project-intake-item-plan --dry-run` / MCP `project_intake_item_plan` | Previews the next `source-intake --dry-run` route for one human-selected local file. It redacts local paths, reads no file body, calculates no content hash, creates no selection manifest, and writes nothing. |
| Source-intake record | `archive source-intake-record --dry-run|--approve` | Validates a reviewed `source-intake --dry-run` JSON file and writes the redacted plan under `receipts/sources/` for later capture evidence. It blocks unredacted local paths, provider URLs, tokens, and secrets. |
| Capture selection | `archive objet-capture-selection --dry-run|--approve` | Hashes one staged file, validates the recorded source-intake plan, and writes only a reviewed selection manifest for later `objet-capture`; it does not capture bytes, append object manifests, draft, mint, upload, or clean. |
| Artifact hygiene | `wom-kit/tools/check_artifact_hygiene.py` | Report-only artifact classification and generated `.gitignore` checks; never cleans files. |
| Per-item intake | `archive source-intake --dry-run` / MCP `source_intake_plan` | Classifies exactly one locator; reads no bodies and writes nothing. Optional `--project-intake-receipt` / `project_intake_receipt` validates a decisions receipt as session context only. |
| Local objet capture | `archive objet-capture --dry-run|--approve` | Captures explicitly approved staged originals into the local content-addressed store for sandbox-marked archives; optional `--project-intake-receipt` or `project_intake_receipt_path` validates a decisions receipt before staged bytes are read; never deletes staged originals. |
| Derived text capture | `archive derive-text capture --dry-run|--approve` | Registers already extracted UTF-8 text for an existing `object_id`; single-file and JSONL batch input are supported. |
| Drafting | `archive create-draft --dry-run` | Previews an inbox draft; can preserve validated source-intake `project_intake_context` as receipt evidence; approved write is separate from minting. |
| Minting | `archive mint-zet --dry-run` / `--approve` | Mints only after explicit approval and writes receipts/snapshots. |
| Cleanup verification | `archive staged-cleanup-check --dry-run` | Reports whether staged files are preserved, deferred, or unsafe to remove; never deletes. |
| Index | `archive index` / `archive search` | Generated SQLite index; rebuildable local search. |

These primitives now include a dry-run staging guide, a session planner with
human review prompts, a one-question-at-a-time prompt surface, a next-answer
decision JSON template, a receipt writer for reviewed answers, a read-only
receipt status check, a one-item source-intake route preview, source-intake
plan recording for later capture evidence, an optional source-intake
session-context link, missing-question prompts for the next human review turn,
and draft/mint metadata preservation for that receipt evidence.
They still do not form a full human-guided intake/capture/draft/mint/cleanup
workflow.

## 5. Planned Surfaces

These surfaces are planned, not currently available:

- an approved project intake session executor after the planner,
- a joined executor that carries reviewed choices across source-intake, objet capture, derived text capture, draft creation, minting, and cleanup verification,
- automatic remote object-storage upload.

Until those exist, docs and agents must describe them as planned capabilities,
not as current WOM-kit commands.

## 6. Safety Gates

### G1 - Local-First Objet Storage

The near-term target is the local objet store.

`archive object-storage` plans provider metadata and manual steps. It does not
create buckets, upload files, sync providers, copy source files, hash files, or
import source content.

Remote object storage remains deferred/manual until a separate capability is
implemented and approved.

### G2 - Staged Folder Deletion

The staged project folder may be removed only after verification that:

- selected originals are preserved as objets or explicitly deferred,
- manifests/source maps/receipts exist for preserved items,
- intended zets are minted or explicitly left as drafts/deferred work,
- provenance links zets back to source refs or object ids,
- report-only artifact hygiene review has no unresolved blockers,
- `archive doctor --strict` passes,
- the user approves cleanup.

Deletion is the last step, not a convenience cleanup.

### G3 - Conversation Is Part Of The Workflow

The user and AI should inspect the folder together.

The session should ask questions such as:

```text
What is this project?
Which files are originals?
Which files are generated or disposable?
Which files must stay private?
Which items should become zets?
Which items should remain only as source objets?
Which items should be ignored?
```

The system should create durable memory gradually, not all at once.

## 7. Optional MOW Harness Layer

MOW should work without MOW Harness.

MOW Harness is an optional operating layer for users who want structured
multi-agent work. It can be useful when a project intake session benefits from:

- Codex + Claude division of labor,
- sealed step files,
- mailbox coordination,
- brakes and status banners,
- review gates,
- local collaboration records.

The public MOW Harness project lives at:

```text
https://github.com/mow-coding/mow-harness
```

WOM-kit does not currently install or bundle MOW Harness. A user who wants it
should follow the separate MOW Harness project. A later companion batch may add
WOM-specific discovery docs or a helper, but that must remain opt-in.

Use it as an operating room, not as the archive itself.

Local harness folders such as `collab/` and `.mow-harness/` should stay
local-only unless a user deliberately summarizes or mints selected outcomes into
zets.

## 8. Batch Roadmap

The agreed safe spine is:

1. **Map/docs**: this document and related setup/upgrade boundary docs.
2. **Upgrade safety**: add and dogfood `archive upgrade-check --dry-run` as a
   read-only upgrade-readiness advisor.
3. **Intake session planner**: dry-run-only planning for one staged folder.
   The first version reports top-level counts only and writes nothing.
4. **Local objet capture**: approved preservation of selected originals into the
   local objet store, manifests, source maps, and receipts.
5. **Conversation-to-zet and cleanup**: integrate source-intake, create-draft,
   mint-zet, and final staged-folder cleanup verification.

The parked onboarding guidance cleanup can resume after this spine is stable.

An optional MOW Harness companion batch can also happen after the spine is
stable. That future batch should improve discoverability or helper setup without
making MOW depend on MOW Harness.
