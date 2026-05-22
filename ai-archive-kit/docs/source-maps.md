# Source Maps

Source maps are the first real bridge between GitHub-style versioning and the broader ontology map the archive wants to draw.

Think of the roles this way:

```text
GitHub = versioned map and review history
Object storage = large media/object warehouse
Local PC / SSD / Notion / Google Drive = source worlds
SQLite = rebuildable search index
Archive Kit = control plane that connects and verifies the above
```

## Files

`source-bindings.yml` says which source worlds are registered:

```text
local_folder
external_ssd
notion_export
google_drive_export
object_manifest
```

It stores refs such as `ARCHIVE_PERSONAL_DOCUMENTS_ROOT` or `archive:objects/manifests/files.jsonl`. It must not store real API tokens, database URLs, passwords, or sensitive absolute local paths.

`source-maps/*.jsonl` stores one metadata item per line. These files are safe to version when they avoid private absolute paths and secrets:

```json
{"source_id":"local:docs","item_kind":"file","relative_path":"notes/plan.txt","size_bytes":1200,"scan_status":"seen"}
```

## Metadata-First Scan

The first scan mode is intentionally boring:

```text
file name / relative path
size
modified time
mime guess
provider id or external URL when supplied by an export manifest
visibility
provenance
```

It does not read file bodies, summarize content with AI, call live provider APIs, or calculate full file hashes.

## CLI

List registered sources:

```powershell
python cli\archive.py sources examples\fake-life-archive --format json
```

Register a source without hand-editing YAML:

```powershell
python cli\archive.py add-source .\my-archive `
  --source-id local:desktop `
  --type local_folder `
  --local-root C:\Users\me\Desktop `
  --write-local-profile `
  --dry-run `
  --format json
```

Apply after review:

```powershell
python cli\archive.py add-source .\my-archive `
  --source-id local:desktop `
  --type local_folder `
  --local-root C:\Users\me\Desktop `
  --write-local-profile `
  --approve `
  --reviewed-by person:me
```

This writes the safe source binding to `source-bindings.yml`. The real local path goes only to ignored `profiles/local/source-roots.local.yml` when `--write-local-profile` is used.

Show Docker mount guidance:

```powershell
python cli\archive.py source-mounts .\my-archive
```

Docker scans need explicit read-only source mounts, usually under `/sources/<source-id>`. Host-native CLI can use ignored local profiles or `--source-root` directly.

Preview a scan:

```powershell
python cli\archive.py scan-source .\my-archive `
  --source local:personal-documents `
  --source-root C:\Users\me\Documents `
  --dry-run `
  --format json
```

Apply after review:

```powershell
python cli\archive.py scan-source .\my-archive `
  --source local:personal-documents `
  --source-root C:\Users\me\Documents `
  --approve `
  --reviewed-by person:me
```

Approved scans write:

```text
source-maps/<source_id>.jsonl
receipts/sources/*.source-scan.json
```

The real source root is used only at runtime. The receipt records how it was resolved, not the sensitive absolute path itself.

## MCP Boundary

MCP exposes:

```text
list_sources
source_scan_plan
```

It does not expose a real source scan apply tool. Human-approved writes stay in the CLI.

## Indexing

`archive index` includes source map entries in `db/archive-index.sqlite`. The database is still disposable: rebuild it from zettels, manifests, views, and source maps whenever needed.
