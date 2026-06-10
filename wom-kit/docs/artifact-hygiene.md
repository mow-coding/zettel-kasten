# WOM Artifact Hygiene

Status: active baseline
Date: 2026-06-07

This document explains which WOM files are durable, which are generated, which
are local-only, and which must never be cleaned automatically.

The short beginner version is:

```text
Do not delete first and explain later.
Classify first, report first, ask first, then clean only in a future approved flow.
```

## 1. Install And Workspace Paths

For a first personal WOM setup, the recommended local paths are:

```text
local archive root:       C:\Users\<user>\zettel-kasten-<profile_slug>
local objet store:        C:\Users\<user>\zettel-kasten-<profile_slug>-objets
project intake staging:   C:\Users\<user>\zettel-kasten-<profile_slug>-objets\intake\<project_slug>
```

The local archive root is the Git-friendly control plane. It holds zets,
metadata, manifests, source maps, receipts, views, and generated local indexes.

The local objet store is the raw source/original file store. It can contain
private, large, binary, or otherwise non-Git-friendly files. It is real user
data, so tools must not read or clean it by default.

For installation today:

- Docker-first setup scripts are the beginner-friendly route.
- Python CLI usage is the developer route.
- `npx`, `pipx`, and one-shot installer wrappers remain future packaging work.

## 2. Artifact Classes

| Class | Examples | Cleanup rule |
| --- | --- | --- |
| `DURABLE_ARCHIVE_RECORD` | `archive.yml`, `archive-identity.yml`, `AGENTS.md`, `zettels/`, `objects/manifests/*.jsonl`, `source-maps/*.jsonl`, `receipts/`, `views/`, `db/schema.sql`, non-secret `provider-bindings.yml`, non-secret `source-bindings.yml` | Keep. These are archive memory or control records. |
| `DURABLE_UNTIL_RESOLVED` | `inbox/` drafts, active project intake staging decisions | Keep until minted, explicitly deferred, or explicitly abandoned. |
| `DURABLE_WITH_EXPIRY` | `workpacks/` and transfer/export bundles with `expires_at` or a review window | Keep until expiry and explicit cleanup review. |
| `REBUILDABLE_GENERATED` | `db/archive-index.sqlite`, future search indexes and caches | Safe to rebuild later, but do not delete silently in this batch. |
| `DISPOSABLE_AFTER_REVIEW` | `tmp/`, `tmp-*`, dry-run sandboxes, abandoned staging folders, expired workpacks after review | Disposable only after explicit review gates. |
| `LOCAL_ONLY_SECRET_CONFIG` | `.env`, `.env.*`, keys, tokens, `profiles/local/`, `keyrings/local/`, `.archive-local/`, `rclone.conf`, credentials | Must stay local and ignored by git. Never publish. |
| `EXTERNAL_LIVE_NEVER_TOUCH` | a real basoon dogfood archive, any real user archive, any real local `-objets` store | Never read or mutate by default. Require explicit operator approval. |
| `EXTERNAL_MANUAL_OR_DEFERRED` | GitHub repositories, R2/B2/S3 buckets, Neon/Postgres, provider permissions, remote object storage state | Manual or future provider flow. No automatic provider changes. |
| `LOCAL_ONLY_COLLAB_HARNESS` | `collab/`, `.mow-harness/` | Useful operation state, but not WOM archive records. Keep local-only. |

## 3. Report-Only Checker

The local checker is:

```text
wom-kit/tools/check_artifact_hygiene.py
```

Run it against an explicit target:

```powershell
python wom-kit\tools\check_artifact_hygiene.py --target <archive-or-throwaway-path>
```

The checker reports:

- artifact classes by path,
- generated archive `.gitignore` coverage,
- local-only secret/config exposure risks,
- external-live paths that should not be scanned by default.

The checker never deletes, moves, copies, uploads, prunes, rewrites, normalizes,
or cleans files.

If the target looks like a real `-objets` store or a known real user archive, it
blocks by default instead of scanning. That is intentional. A path-name scan can
still reveal private information, so even read-only inspection needs a clear
human decision.

## 4. Generated Archive `.gitignore`

Generated archives should protect local-only state with patterns such as:

```text
.env
.env.*
!.env.example
*.key
*.pem
*.p12
*.pfx
*.kdbx
secrets/
profiles/local/
profiles/*.local.yml
keyrings/local/
keyrings/*.local.yml
.archive-local/
rclone.conf
credentials.json
token.json
tmp/
/collab/
/.mow-harness/
**/db/archive-index.sqlite
```

The checker validates these patterns on throwaway or explicitly approved archive
targets. It does not change `.gitignore` by itself.

## 5. Future Cleanup Guidance

A future cleanup or `gc` flow may report items such as:

- stale `tmp/` folders,
- expired workpacks,
- abandoned project intake staging folders,
- rebuildable SQLite/search indexes,
- orphaned generated reports that are not receipts or source maps.

But a future cleanup flow must still separate "could be cleaned" from "will be
cleaned". Actual cleanup needs explicit approval and evidence that durable
records are preserved.

## 6. Current Gaps

These are not solved yet:

- no systematic `gc` command exists,
- no orphan-objet sweep exists,
- no real local objet capture flow exists in this batch,
- no provider upload/sync cleanup exists,
- no automatic staged-folder deletion verifier exists,
- no `npx`/`pipx` distribution switch is included here.

Current work is prevention, classification, and report-only visibility.
