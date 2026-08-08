# WOM Artifact Hygiene

Status: active baseline with web/app boundary guard and intake layout ruling (D2)
Date: 2026-07-03

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
capture intake staging:   <archive-root>\staging\incoming\<YYYY-MM-DD>\<project_slug>  [canonical, in-archive]
bulk external staging:    C:\Users\<user>\zettel-kasten-<profile_slug>-objets\intake\<project_slug>
```

The intake layout ruling (D2, 2026-07-03) is one consistent statement:

- **Canonical capture intake stages INSIDE the archive root**, recommended
  under `staging/incoming/<YYYY-MM-DD>/` (the date layer is recommended, not
  required). Capture requires archive-relative staged paths, and the v0.3.158
  enablement record makes this the real-archive path.
- **The sibling `-objets` store is for bulk external originals** that must
  never enter git: it stays under the never-touch protection and is
  represented in the archive through `prehashed-objet-ledger` plus
  `object-storage-upload-evidence` evidence, not by copying bytes in.
- **A raw in-root `objets/` folder is NON-canonical** for long-term originals:
  originals belong in the content-addressed `objects/sha256/` store via
  capture. Doctor reports `archive_objets_layout_noncanonical` for it; see the
  migration guide in section 5.

The local archive root is the Git-friendly control plane. It holds zets,
metadata, manifests, source maps, receipts, views, and generated local indexes.

External report apps, Next.js/Vercel projects, and other general development
projects should live outside the WOM archive root by default. A report app can
cite or depend on zets, but its `package.json`, `node_modules/`, `.next/`,
`.vercel/`, `.env.local`, `src/`, and `public/` state should not become archive
knowledge candidates.

The local objet store is the raw source/original file store. It can contain
private, large, binary, or otherwise non-Git-friendly files. It is real user
data, so tools must not read or clean it by default.

For installation today:

- The exact tagged GitHub release provides a verified self-contained Python
  wheel from v0.3.242.
- `uv tool install` is the recommended isolated CLI route; plain `pip` belongs
  in a dedicated virtual environment.
- Docker-first setup remains available for the containerized runtime path.
- PyPI publication, `pip install wom-kit`, and one-shot AI-host skill installers
  remain future packaging work.

## 2. Artifact Classes

| Class | Examples | Cleanup rule |
| --- | --- | --- |
| `DURABLE_ARCHIVE_RECORD` | `archive.yml`, `archive-identity.yml`, `AGENTS.md`, `zettels/`, `objects/manifests/*.jsonl`, `source-maps/*.jsonl`, `receipts/`, `views/`, `db/schema.sql`, non-secret `provider-bindings.yml`, non-secret `source-bindings.yml` | Keep. These are archive memory or control records. |
| `DURABLE_UNTIL_RESOLVED` | `inbox/` drafts, active project intake staging decisions | Keep until minted, explicitly deferred, or explicitly abandoned. |
| `DURABLE_WITH_EXPIRY` | `workpacks/` and transfer/export bundles with `expires_at` or a review window | Keep until expiry and explicit cleanup review. |
| `REBUILDABLE_GENERATED` | `db/archive-index.sqlite`, `db/archive-index.sqlite-wal`, `db/archive-index.sqlite-shm`, `db/archive-index.sqlite-journal`, `node_modules/`, `.next/`, future search indexes and caches | Safe to rebuild later, but do not delete silently in this batch. |
| `DISPOSABLE_AFTER_REVIEW` | `tmp/`, `.wom-scratch/`, `workbench/ai-scratch/`, `tmp-*`, dry-run sandboxes, abandoned staging folders, expired workpacks after review | Disposable only after explicit review gates. |
| `LOCAL_ONLY_SECRET_CONFIG` | `.env`, `.env.*`, keys, tokens, `.vercel/`, `profiles/local/`, `keyrings/local/`, `.archive-local/`, `rclone.conf`, credentials | Must stay local and ignored by git. Never publish. |
| `EXTERNAL_LIVE_NEVER_TOUCH` | private dogfood archives, any real user archive, any real local `-objets` store | Never read or mutate by default. Require explicit operator approval. |
| `EXTERNAL_MANUAL_OR_DEFERRED` | GitHub repositories, R2/B2/S3 buckets, Neon/Postgres, provider permissions, remote object storage state | Manual or future provider flow. No automatic provider changes. |
| `LOCAL_ONLY_COLLAB_HARNESS` (generic source alias: `LOCAL_ONLY_COORDINATION_STATE`) | `collab/`, legacy `.mow-harness/` | Local coordination or retired-tool state, not WOM archive records. The historical machine label remains compatible; keep these paths quarantined and local-only. |

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

For one archive's fixed local lifecycle surfaces, v0.3.303 also provides:

```powershell
archive artifact-lifecycle-inventory <archive-root> --dry-run --format json
```

This bounded inventory covers declared scratch, staging, draft, workpack,
generated-index, local content-addressed object, and non-canonical in-root
objet surfaces. It hides child paths by default, refuses incomplete coverage,
does not enumerate a possible original-bearing `objets/` root, and never turns
an age or classification into deletion authority. See
[Artifact Lifecycle Inventory](artifact-lifecycle-inventory.md).

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
.wom-scratch/
workbench/ai-scratch/
node_modules/
.next/
.vercel/
/collab/
/.mow-harness/
**/db/archive-index.sqlite
**/db/archive-index.sqlite-wal
**/db/archive-index.sqlite-shm
**/db/archive-index.sqlite-journal
objects/sha256/
objects/derived-text/sha256/
/objets/
```

The checker validates these patterns on throwaway or explicitly approved archive
targets. It does not change `.gitignore` by itself.

Use the approval-gated repair command to append missing safe defaults while
preserving existing entries:

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli repair-gitignore <archive-root> --dry-run --format json
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli repair-gitignore <archive-root> --approve --reviewed-by person:me --format json
```

`repair-gitignore` does not delete existing `.gitignore` lines, inspect source
file bodies, clean files, upload, sync, or call provider APIs.

Some safe defaults, such as `/collab/` and the retired-tool path
`/.mow-harness/`, are defensive workspace-root quarantine rules. They keep
local collaboration mailboxes, prompts, runtime state, installer residue, and
possible secret-bearing coordination files out of version control even when an
archive is operated from a larger workspace. WOM does not install, invoke, or
update the retired tool. Default archive-root Doctor checks, archive-root
source discovery, restore drills, and this repository checker exclude those
roots; this checker also refuses either root as its direct target. Explicit
file-capture or staged-folder commands retain their own narrowly reviewed path
authority and must not be pointed at these quarantine roots. These ignore
rules do not advertise an integration.

v0.3.307 adds one separate, destructive opt-in exception for a workspace owner
who already knows an exact absolute workspace root:

```powershell
archive legacy-coordination-cleanup <absolute-workspace-root> --dry-run --format json
```

This is not part of Doctor, archive discovery, restore, installation, project
update, upgrade, or this repository checker. It considers only the exact direct
child `.mow-harness/`; `collab/` is never traversed or changed. Approval requires the
unchanged `plan_sha256`, reviewer, workspace-owner authority, external-writer
quiescence, and explicit retired-state disposal. A true
`summary.backups_or_receipts_present` requires a separate affirmation. Unknown,
case-drifted, tracked, linked/reparse, special,
unreadable, over-limit, or changed state blocks. The command emits only counts
and hashes, creates no backup or receipt, and reports partial removal as
`partial_cleanup_pending`, not success. See
[Legacy Coordination Cleanup](legacy-coordination-cleanup.md).

`/objets/` (v0.3.160) is anchored on purpose: it excludes only a raw IN-ROOT
`objets/` folder, not nested folders such as `staging/incoming/<date>/objets/`
that appear when a client tree is copied into staging. Two honest caveats:

- gitignore does not untrack files that were already committed; use
  `git rm --cached` after human review when that has happened,
- once `/objets/` is ignored, NEW files dropped there silently stop being
  versioned. That is why the doctor layout warning
  `archive_objets_layout_noncanonical` stays active even when the folder is
  gitignored: unmigrated originals in an ignored folder are excluded from the
  git-push backup path until the migration in section 5 completes.

For the workspace-root risk above an archive (a `git init` at a folder that
contains the archive and/or a sibling `-objets` store), doctor additionally
reports `workspace_objet_store_git_exposure` when an objet byte store may be
tracked by an enclosing git working tree. The fix message names the store's
actual directory name, because the `objets/` pattern does not match a sibling
`<root-name>-objets` store: when the store is a direct child of the git root
the hint is the anchored `/<root-name>-objets/` line in that root
`.gitignore`; when the store sits deeper, the hint is the unanchored
`<root-name>-objets/` form there (or the anchored form in the store's own
parent directory `.gitignore`) — an anchored repo-root line would not match a
nested store in git. A store whose own `.git` marker is broken (empty `.git`
dir, dangling `gitdir:` pointer) still warns: real git ignores the invalid
marker and the enclosing repository tracks the raw originals anyway.

## 5. In-Root `objets/` Migration And Future Cleanup Guidance

AI scratch files belong in `.wom-scratch/` or `workbench/ai-scratch/`, never in
an objet location. Human-selected original material such as meeting audio,
transcripts, photos, exports, or other source files that should remain
recoverable belongs in the content-addressed `objects/sha256/` store through
the reviewed capture chain (or, for bulk external stores, in the sibling
`-objets` store under never-touch protection with `prehashed-objet-ledger`
evidence). A raw in-root `objets/` folder is a non-canonical layout: it is
neither hashed, nor manifested, nor protected, and once gitignored its contents
silently drop out of the git-push backup path. AI research notes, intermediate
reports, prompt drafts, and temporary composition files are scratch unless a
human explicitly preserves them as an objet through capture.

### Migrating an existing in-root `objets/` folder

Archives that already hold originals in an in-root `objets/` folder (doctor
warning `archive_objets_layout_noncanonical`) migrate with the normal reviewed
spine. In-root `objets/` files are ALREADY archive-relative, so selections can
run in place; no preparatory move into `staging/incoming/` is needed.

Prerequisite (BEFORE step 2, not just before capture): real (non-sandbox)
archives must approve capture enablement once —
`archive objet-capture-enable <archive-root> --approve --reviewed-by person:me`.
Without the enablement record, `objet-capture-selection` in step 2 already
blocks with `resolved_path_never_touch` on a real archive following the
recommended naming; it is not only step 3 that refuses. When the archive root
or a parent folder matches the never-touch naming pattern (`zettel-kasten-*` /
`*-objets` — true for every archive following the recommended naming), the
approval additionally requires `--acknowledge-never-touch-name`, otherwise the
enablement refuses.

```powershell
# 1. Classify one file (metadata-only, no copy):
archive source-intake <archive-root> --dry-run --local-path <archive-root>\objets\<file> --format json
archive source-intake-record <archive-root> --source-intake-plan <plan.json> --approve --reviewed-by person:me --format json

# 2. Prepare ONE reviewed selection per file (archive-relative staged path):
archive objet-capture-selection <archive-root> --staged-path objets/<file> --source-intake-receipt <receipt> --approve --reviewed-by person:me --format json

# 3. Capture through the enablement-gated write path. A relative --selection is
#    resolved from the archive root, never the process current directory.
#    Absolute selection paths remain compatible.
archive objet-capture <archive-root> --selection <archive-relative-selection.json> --dry-run --format json
archive objet-capture <archive-root> --selection <archive-relative-selection.json> --approve --reviewed-by person:me --format json

# 4. Verify preservation evidence BEFORE any manual deletion:
archive staged-cleanup-check <archive-root> --staged objets --dry-run --format json
```

For bulk stores (hundreds of GB, thousands of files), do not run per-file
capture: register the external content-addressed store with
`archive prehashed-objet-ledger` and record storage evidence with
`archive object-storage-upload-evidence` instead, then promote only the small
human-selected subset through the capture spine above. Only
`staged-cleanup-check` evidence — never this document — can say a migrated
folder is safe to remove, and WOM-kit still never deletes it for you.

The current local cleanup flow is:

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli artifact-lifecycle-inventory <archive-root> --dry-run --format json
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli zet-self-contained-check <archive-root> --path inbox/example.md --dry-run --format json
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli ai-scratch-gc <archive-root> --path inbox/example.md --dry-run --format json
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli ai-scratch-gc <archive-root> --path inbox/example.md --approve --reviewed-by person:me --format json
```

When `mint-zet --approve` sees explicit `.wom-scratch/` or
`workbench/ai-scratch/` source refs, the minted canonical zet removes those
scratch refs and the approved mint runs the same scratch cleanup gate for those
explicit files. External citation URLs such as public articles or videos may
remain inside the zet body or `source_refs`; private provider locators and local
file paths still need durable WOM refs.

A broader future cleanup or `gc` flow may report items such as:

- stale `tmp/` folders,
- explicit AI scratch files not tied to an active draft,
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
- no unconstrained whole-archive scratch sweep exists; v0.3.303 instead scans
  fixed declared lifecycle roots with explicit incomplete-coverage evidence,
- no byte-verifying orphan-objet sweep exists; v0.3.303 reports only
  content-free unmanifested local object candidates against valid complete
  manifest authority,
- local objet capture runs on sandbox-marked archives, or on real archives after owner approval via `archive objet-capture-enable` (v0.3.158); the enablement record is a consent marker in the same write-trust domain, not a security boundary,
- no provider upload/sync cleanup exists,
- no automatic staged-folder deletion executor exists; the existing
  `staged-cleanup-check` remains a report-only preservation verifier,
- no `npx`/`pipx` distribution switch is included here.

Current work is prevention, classification, and report-only visibility.
