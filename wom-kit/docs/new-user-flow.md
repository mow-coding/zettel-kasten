# New User Flow

This document explains the normal safe workflow for a beginner using WOM-kit.

Think of the archive as durable memory. The CLI is the control panel. The AI can help, but it should not silently rewrite canonical memory.

## Flow 0: One-Line Docker Setup

The beginner path is Docker-first. That means Windows and Mac users do not need to set up Python directly. Run the setup dry-run from inside `wom-kit/`; it checks Docker and tells you exactly what will happen.

Windows:

```powershell
.\scripts\setup-windows.ps1 -DryRun
```

macOS/Linux:

```bash
sh scripts/setup-unix.sh --dry-run
```

If the plan looks right, run the same command without the dry-run flag. The script checks Docker, Docker Compose, Docker daemon state, the mounted archive folder, and `.env`. It does not ask for real secrets.

If you run setup directly in a terminal without archive values, it can ask simple questions such as archive id, owner id, and display name. If an AI or script runs setup non-interactively, pass the values as flags so setup does not need to guess.

With onboarding values:

```powershell
.\scripts\setup-windows.ps1 `
  -ArchiveId archive:personal:me `
  -PrincipalId person:me `
  -PrincipalName "Me" `
  -ProviderProfile local_only `
  -Yes
```

The normal Docker command shape is:

```bash
docker compose run --rm archive-cli doctor examples/fake-life-archive --strict
```

## Flow 1: Start With Health Checks

Run this before and after substantial work:

```powershell
python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict
```

Use JSON when an AI or script needs structured output:

```powershell
python wom-kit\cli\archive.py validate wom-kit\examples\fake-life-archive --format json
```

`doctor` checks:

```text
required files and folders
archive.yml
zettel frontmatter
object manifests
source bindings and source maps
views
workpacks
zettel-kasten rule files
unsafe local/provider paths in zettels
secret-like files and values
```

Host-native developer fallback:

```powershell
python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict
```

## Flow 1B: Plan A Real Personal/Team Pilot

Before connecting real files, plan the first pilot. This command writes nothing.

```powershell
python wom-kit\cli\archive.py pilot-plan `
  --personal-root .\archives\personal-life `
  --team-root .\archives\team-archive `
  --personal-principal-id person:me `
  --team-principal-id team:founding-team
```

The plan checks that the personal archive and team archive are not the same folder, not nested inside each other, and not using the same archive id. It also suggests first sources for local folders, SSDs, Notion exports, Google Drive exports, and object manifests.

After an archive exists, run preflight before connecting real data:

```powershell
python wom-kit\cli\archive.py preflight .\archives\personal-life --strict --check-docker
```

Run a restore drill before the first real source scan:

```powershell
python wom-kit\cli\archive.py recovery-plan .\archives\personal-life --format json
python wom-kit\cli\archive.py restore-drill .\archives\personal-life --target C:\tmp\personal-life-restore --dry-run --format json
python wom-kit\cli\archive.py restore-drill .\archives\personal-life --target C:\tmp\personal-life-restore --approve --reviewed-by person:me
```

Then preflight can require a successful restore receipt:

```powershell
python wom-kit\cli\archive.py preflight .\archives\personal-life --strict --require-restore-drill
```

For separation between personal and team archives:

```powershell
python wom-kit\cli\archive.py preflight .\archives\personal-life --peer-archive .\archives\team-archive --strict
```

Preflight blocks drive roots, whole home folders, system folders, source roots that contain the archive itself, and overlapping personal/team archive roots.

## Flow 2: Onboard A New Archive

Start with an onboarding dry-run. Think of it as letting the AI and CLI show the setup plan before anything is created.

Docker:

```bash
docker compose run --rm archive-cli onboard \
  --target-root /archives/personal \
  --type personal \
  --archive-id archive:personal:me \
  --principal-id person:me \
  --principal-name "Me" \
  --provider-profile local_only \
  --dry-run
```

Host-native developer fallback:

```powershell
python wom-kit\cli\archive.py onboard `
  --target-root .\tmp-my-archive `
  --type personal `
  --archive-id archive:personal:me `
  --principal-id person:me `
  --principal-name "Me" `
  --provider-profile local_only `
  --dry-run
```

When the plan is correct, approve it:

Docker:

```bash
docker compose run --rm archive-cli onboard \
  --target-root /archives/personal \
  --type personal \
  --archive-id archive:personal:me \
  --principal-id person:me \
  --principal-name "Me" \
  --provider-profile local_only \
  --approve
```

Host-native developer fallback:

```powershell
python wom-kit\cli\archive.py onboard `
  --target-root .\tmp-my-archive `
  --type personal `
  --archive-id archive:personal:me `
  --principal-id person:me `
  --principal-name "Me" `
  --provider-profile local_only `
  --approve
```

The new archive starts with:

```text
inbox/
zettels/
views/
objects/manifests/files.jsonl
source-bindings.yml
source-maps/
db/schema.sql
zettel-kasten/
workbench/
receipts/
.gitignore
provider-bindings.yml
```

The `.gitignore` protects local-only profiles, secrets, and generated search indexes. `provider-bindings.yml` stores references such as env var names and KeePassXC entry names. `source-bindings.yml` stores source refs such as env var names or archive-relative refs. Neither file should store token, password, database URL, or sensitive absolute path values.

## Flow 2B: Map Existing Source Worlds

Source maps let the archive draw a metadata-first map of files that remain where they already are.

List registered sources:

```powershell
python wom-kit\cli\archive.py sources .\tmp-my-archive --format json
```

Register another source without hand-editing YAML:

```powershell
python wom-kit\cli\archive.py add-source .\tmp-my-archive `
  --source-id local:desktop `
  --type local_folder `
  --local-root $env:ARCHIVE_SOURCE_DESKTOP_ROOT `
  --write-local-profile `
  --dry-run `
  --format json
```

When the plan looks right:

```powershell
python wom-kit\cli\archive.py add-source .\tmp-my-archive `
  --source-id local:desktop `
  --type local_folder `
  --local-root $env:ARCHIVE_SOURCE_DESKTOP_ROOT `
  --write-local-profile `
  --approve `
  --reviewed-by person:me
```

The safe source record goes into `source-bindings.yml`. The real local path goes only into ignored `profiles/local/source-roots.local.yml`.

For Docker, check how sources should be mounted read-only:

```powershell
python wom-kit\cli\archive.py source-mounts .\tmp-my-archive
```

Preview a local folder scan:

```powershell
python wom-kit\cli\archive.py scan-source .\tmp-my-archive `
  --source local:personal-documents `
  --source-root $env:ARCHIVE_SOURCE_DOCUMENTS_ROOT `
  --dry-run `
  --format json
```

Apply only after review:

```powershell
python wom-kit\cli\archive.py scan-source .\tmp-my-archive `
  --source local:personal-documents `
  --source-root $env:ARCHIVE_SOURCE_DOCUMENTS_ROOT `
  --approve `
  --reviewed-by person:me
```

The scan writes `source-maps/*.jsonl` and `receipts/sources/*.source-scan.json`. It records file names, relative paths, sizes, modified times, visibility, and provenance. It does not read file bodies, summarize content with AI, call provider APIs, or calculate full hashes.

## Flow 2C: Plan A GitHub Repository For A WOM Profile

Use profile resolution before assuming the current archive is the target. Then plan the GitHub repository with dry-run:

```powershell
python wom-kit\cli\archive.py github-repo .\tmp-my-archive `
  --dry-run `
  --profile-id profile:personal:HongGilDong `
  --profile-slug HongGilDong `
  --github-owner example-user `
  --github-account-ref github:account:honggildong `
  --format json
```

The default proposed repository name is:

```text
zettel-kasten-HongGilDong
```

Dry-run writes nothing. Approved mode writes only local `provider-bindings.yml` metadata and a setup receipt:

```powershell
python wom-kit\cli\archive.py github-repo .\tmp-my-archive `
  --approve `
  --reviewed-by person:me `
  --profile-id profile:personal:HongGilDong `
  --profile-slug HongGilDong `
  --github-owner example-user `
  --github-account-ref github:account:honggildong `
  --format json
```

This flow does not create a GitHub repository, start OAuth, call GitHub APIs, run `gh`, configure git remotes, push, or sync. Those are separate manual steps.

## Flow 2D: Plan Objet Storage For A WOM Profile

Use profile resolution before assuming the current archive is the target. Then plan where source/original objets should live:

```powershell
python wom-kit\cli\archive.py object-storage .\tmp-my-archive `
  --dry-run `
  --provider cloudflare-r2 `
  --profile-id profile:personal:HongGilDong `
  --profile-slug HongGilDong `
  --storage-account-ref storage:account:honggildong `
  --format json
```

The default proposed bucket/container name is:

```text
zettel-kasten-honggildong-objets
```

The default proposed prefix is:

```text
archives/<archive_id>/objets/
```

Dry-run writes nothing. Approved mode writes only local `provider-bindings.yml` metadata and a setup receipt:

```powershell
python wom-kit\cli\archive.py object-storage .\tmp-my-archive `
  --approve `
  --reviewed-by person:me `
  --provider cloudflare-r2 `
  --profile-id profile:personal:HongGilDong `
  --profile-slug HongGilDong `
  --storage-account-ref storage:account:honggildong `
  --format json
```

This flow does not create a bucket/container, start OAuth, call provider APIs, upload, sync, copy source files, calculate file hashes, or import source content. Those are separate future/manual steps.

## Flow 3: AI Creates Drafts

AI should create draft zettels in `inbox/`.

For AI-assisted profile-bound work, preview first:

```powershell
python wom-kit\cli\archive.py create-draft .\tmp-my-archive `
  --title "Draft from conversation" `
  --body "# Draft from conversation`n`nThis is a rough note. It is not canonical memory yet." `
  --dry-run `
  --expected-archive-id archive:personal:me `
  --expected-type personal `
  --profile-id profile:personal:me `
  --creation-mode ai_assisted `
  --created-by ai_runtime:codex `
  --format json
```

The dry-run writes nothing. It returns the proposed `inbox/` path, frontmatter preview, body hash, blockers, warnings, and approval replay values. After human draft approval, replay with the same `draft_id`, `created_at`, expected archive id/type, profile id, and `expected_body_sha256`, plus `draft-approved-by`.

The older direct command remains compatible for simple local use:

```powershell
python wom-kit\cli\archive.py create-draft .\tmp-my-archive `
  --title "Draft from conversation" `
  --body "# Draft from conversation`n`nThis is a rough note. It is not canonical memory yet."
```

Drafts may be rough. That is allowed.

Drafts must still avoid:

```text
provider URLs such as s3:// or b2://
local absolute paths such as `<local-absolute-path>`
long-lived secrets
private source leakage
fake certainty about sources
```

Natural-language requests such as "올려줘" should mean "preview or create an inbox draft zet." They do not mean mint canonical memory.

## Flow 4: Human Reviews Minting

Always start with dry-run. Think of it as a rehearsal that tells you whether a draft is safe to make canonical.

```powershell
python wom-kit\cli\archive.py mint-zettel .\tmp-my-archive `
  --path inbox\PUT-THE-DRAFT-FILENAME-HERE.md `
  --dry-run `
  --format json
```

The dry-run checks `zettel-kasten/zettel-rules.yml`.

It returns:

```text
ok
blockers
warnings
checklist
near_duplicates
proposed_canonical_path
proposed_mint_receipt_path
proposed_draft_snapshot_path
receipt_preview
would_change
```

If `ok` is false, the draft needs more human review or editing.

If `ok` is true and you intentionally reviewed the draft, real minting is available through the CLI:

```powershell
python wom-kit\cli\archive.py mint-zettel .\tmp-my-archive `
  --path inbox\PUT-THE-DRAFT-FILENAME-HERE.md `
  --approve `
  --reviewed-by person:me
```

Real minting writes a canonical zettel under `zettels/`, a mint receipt under `receipts/mint/`, and a draft snapshot under `receipts/mint/drafts/`. It leaves the original inbox draft in place.

If dry-run reports warnings, real minting stops unless you add `--allow-warnings`. Use that flag only when you have read and accepted the warnings.

## Flow 5: Search Existing Memory

Build the generated index:

```powershell
python wom-kit\cli\archive.py index wom-kit\examples\fake-life-archive
```

Search:

```powershell
python wom-kit\cli\archive.py search wom-kit\examples\fake-life-archive "onboarding"
```

The index is disposable. Rebuild it whenever needed. It includes zettels, object manifests, views, and source map entries.

## Flow 6: Share A Slice With Workpacks

Pack from a saved view:

```powershell
python wom-kit\cli\archive.py pack .\tmp-fake-life-archive `
  --view view.fake.education.gilwon `
  --purpose "Share a small education context." `
  --mode reference
```

The workpack includes selected zettels and object manifest metadata.

Preview import:

```powershell
python wom-kit\cli\archive.py import .\tmp-my-archive `
  .\tmp-fake-life-archive\workpacks\PUT-THE-WORKPACK-FOLDER-HERE `
  --dry-run `
  --format json
```

Real workpack import is not implemented yet.

## Flow 6B: Import From Notion Or Google Drive

For Notion, export pages as Markdown and preview the import:

```powershell
python wom-kit\cli\archive.py import-external .\tmp-my-archive `
  --source notion `
  --export .\notion-export `
  --dry-run `
  --format json
```

For Google Drive, export documents as Markdown/text and optionally make a manifest that keeps Drive ids and URLs. Preview:

```powershell
python wom-kit\cli\archive.py import-external .\tmp-my-archive `
  --source google_drive `
  --export .\google-drive-export\manifest.json `
  --dry-run `
  --format json
```

Apply only after review:

```powershell
python wom-kit\cli\archive.py import-external .\tmp-my-archive `
  --source notion `
  --export .\notion-export `
  --approve `
  --reviewed-by person:me
```

This writes imported records as inbox drafts and records a receipt under `receipts/import/`. It does not call Notion or Google Drive APIs and it does not store OAuth tokens.

Before sharing a view with another archive, run the scope and trust dry-run:

```powershell
python wom-kit\cli\archive.py share .\tmp-fake-life-archive `
  --view view.fake.company.derived `
  --target-archive archive:company:fake-blue `
  --counterparty-id archive:company:fake-blue `
  --counterparty-fingerprint SHA256:fake-company-blue `
  --dry-run `
  --format json
```

This shows what would be included, what would be excluded, and whether the counterparty fingerprint matches `archive-identity.yml`.

`archive-identity.yml` also separates ownership from operation. A family or company can own an archive while named people or roles operate it.

Ownership transfer is real CLI-only functionality now. Always preview it first:

```powershell
python wom-kit\cli\archive.py transfer-ownership .\tmp-fake-life-archive `
  --new-owner person:child `
  --new-owner-kind person `
  --new-owner-archive archive:personal:child `
  --counterparty-fingerprint SHA256:fake-child-owner `
  --operator-after person:child `
  --approved-by owner:current `
  --approved-by operator:current `
  --dry-run `
  --format json
```

The real command requires `--approve --reviewed-by <actor>` and reuses the dry-run gates. It updates only archive-internal ownership files and receipts. GitHub, Cloudflare R2, Backblaze B2, Neon, rclone, restic, KeePassXC, and other external provider changes stay manual and are listed in `provider_change_plan`.

## Flow 7: Use MCP With An AI Client

Run from `wom-kit/`:

```powershell
$env:PYTHONPATH = "src"
python -m wom_kit.mcp_server
```

Current MCP tools:

```text
wom_profile_list
wom_profile_resolve
archive_doctor
archive_runtime_context
github_repository_setup_plan
object_storage_setup_plan
zet_shared_update_record_review_preview
archive_init
list_zettels
read_zettel
create_draft_zettel
list_views
archive_index
archive_search
archive_onboarding_plan
external_import_plan
list_sources
source_scan_plan
source_registration_plan
source_mount_plan
promotion_check
mint_zettel_check
share_check
delegate_zet_check
attest_zet_check
anchor_zet_check
ownership_transfer_check
```

For AI clients, the first safe call should be `wom_profile_resolve` when the user names a target profile or archive. After that, call `archive_runtime_context` with the resolved archive id and type, then use `create_draft_zettel` with `dry_run: true` before any profile-bound draft write. This prevents the AI from assuming the current/default archive is the target.

MCP can dry-run draft creation, create approved inbox drafts, inspect archives, search, plan onboarding, preview GitHub repository setup, preview object storage setup for WOM objets, preview shared update record review, preview external imports, list sources, preview source registration, preview source mount plans, preview source scans, preview minting, preview legacy promotion, preview archive sharing, preview delegate/attest/anchor lifecycle checks, check ownership transfer, read runtime context, and resolve profile registry entries. It cannot perform real onboarding apply, profile registration, token registration, source registration apply, source scan apply, canonical minting, real share, real delegate, real attest, real anchor, shared update write/apply/transport/import/trust/attest/sign/anchor, merge, fork, ownership transfer, runtime context apply, GitHub create/connect/push/sync, or object storage apply/create/connect/upload/sync. Use the CLI for explicit human-approved minting steps.

## Flow 8: Keep Secrets Out

Local profile files are ignored by default:

```text
profiles/local/
profiles/*.local.yml
keyrings/local/
keyrings/*.local.yml
.archive-local/
```

Profiles may list required environment variable names:

```yaml
env:
  required:
    - ARCHIVE_ROOT
```

Profiles should not contain values:

```yaml
token: "do-not-store-this-here"
password: "do-not-store-this-here"
api_key: "do-not-store-this-here"
```

## Beginner Checklist

Before changing anything important:

```text
1. Run doctor.
2. Use onboarding dry-run before creating a new archive.
3. Create drafts in inbox.
4. Use dry-run before real minting, transfer, sharing, or import.
5. Read blockers and warnings.
6. Record substantial decisions in meeting minutes and decision logs.
7. Run tests after implementation work.
```

The archive should feel boringly safe. That is the point.
