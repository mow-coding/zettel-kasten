# Real Pilot Preflight

This is the safety step before using real personal or team data.

The goal is simple:

```text
Plan first.
Check safety.
Run a restore drill.
Register one narrow source.
Dry-run the scan.
Only then approve writes.
```

## Why This Exists

The archive is allowed to map folders, SSDs, Notion exports, Google Drive exports, and object manifests. That power is useful, but it can also accidentally map too much.

So the first real pilot uses metadata-first rules:

```text
file body reads: no
AI summaries: no
full file hashes: no
live provider API calls: no
source map writes: only after --approve --reviewed-by
```

## Plan Personal And Team Archives

From inside `ai-archive-kit/`:

```powershell
python cli\archive.py pilot-plan `
  --personal-root .\archives\personal-life `
  --team-root .\archives\team-archive `
  --personal-principal-id person:me `
  --team-principal-id team:founding-team `
  --format json
```

This writes nothing. It checks that the personal and team roots are separate and returns suggested first sources.

Default shape:

```text
personal archive:
  type: personal
  provider profile: object_storage_planned
  suggested sources: local folder, SSD, Notion export, Google Drive export, object manifest

team archive:
  type: company
  principal kind: team
  provider profile: full_provider_plan
  suggested sources: team folder, team Notion export, team Google Drive export, object manifest
```

## Preflight An Existing Archive

After creating an archive, run:

```powershell
python cli\archive.py preflight .\archives\personal-life --strict --check-docker
```

For team/personal separation:

```powershell
python cli\archive.py preflight .\archives\personal-life --peer-archive .\archives\team-archive --strict
```

Preflight checks:

```text
archive doctor diagnostics
secret and local profile safety
source binding status
source map status when --require-source-maps is used
local source roots that are too broad
peer archive root overlap
duplicate archive ids
optional Docker runtime readiness
```

## What Preflight Blocks

Preflight blocks:

```text
filesystem or drive root as a local source
the whole home folder as a local source
system directories
the Archive Kit repository root or its parent as a local source
a source root that contains the archive itself
overlapping personal/team archive roots
doctor errors
Docker unavailable when --check-docker is requested
missing source maps when --require-source-maps is requested
```

Preflight warns about broad but sometimes intentional folders, such as Desktop, Documents, Downloads, OneDrive, or Google Drive roots. For the first pilot, choose a smaller folder inside them.

## Recovery Drill Before Real Sources

Before connecting real sources, verify that the archive control plane can be restored:

```powershell
python cli\archive.py recovery-plan .\archives\personal-life --format json
python cli\archive.py restore-drill .\archives\personal-life --target C:\tmp\personal-life-restore --dry-run --format json
python cli\archive.py restore-drill .\archives\personal-life --target C:\tmp\personal-life-restore --approve --reviewed-by person:me
```

After a successful drill, preflight can require it:

```powershell
python cli\archive.py preflight .\archives\personal-life --strict --require-restore-drill
```

The restore drill copies only the archive control plane. It does not copy every PC, SSD, SaaS, or object-storage original.

## First Safe Real Loop

Use this order:

```powershell
python cli\archive.py onboard --target-root .\archives\personal-life --type personal --archive-id archive:personal:life --principal-id person:me --dry-run
python cli\archive.py onboard --target-root .\archives\personal-life --type personal --archive-id archive:personal:life --principal-id person:me --approve
python cli\archive.py preflight .\archives\personal-life --strict
python cli\archive.py restore-drill .\archives\personal-life --target C:\tmp\personal-life-restore --dry-run
python cli\archive.py add-source .\archives\personal-life --source-id local:first-folder --type local_folder --dry-run
python cli\archive.py scan-source .\archives\personal-life --source local:first-folder --source-root <narrow-folder> --dry-run
```

Only approve a scan after the dry-run item count and source root look right.

## MCP Boundary

MCP exposes:

```text
real_pilot_plan
archive_preflight_check
recovery_plan
restore_drill_plan
```

These are read-only. MCP does not expose a pilot apply tool, restore drill apply tool, source registration apply tool, source scan apply tool, provider mutation tool, or real ownership transfer tool.
