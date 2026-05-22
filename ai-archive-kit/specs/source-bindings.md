# Source Bindings Spec v0.1

`source-bindings.yml` registers source worlds that an archive may map without moving the originals.

Supported source types:

```text
local_folder
external_ssd
notion_export
google_drive_export
object_manifest
```

## Boundary

The file may store:

```text
source ids
source type
env/root refs
archive-relative refs such as archive:objects/manifests/files.jsonl
scope policy
visibility policy
```

The file must not store:

```text
API tokens
passwords
database URLs
browser cookies
sensitive absolute local paths
```

Actual local paths are supplied at runtime through CLI arguments or ignored local profiles/env.

The beginner CLI path is:

```text
archive add-source <archive> --dry-run
archive add-source <archive> --approve --reviewed-by <actor>
archive source-mounts <archive>
archive scan-source <archive> --dry-run
```

When `--write-local-profile` is used, actual local paths are written only to:

```text
profiles/local/source-roots.local.yml
```

That file is local-only and ignored by default.

## Source Maps

Approved scans write metadata-only entries under:

```text
source-maps/*.jsonl
```

Each entry records source id, item id, item kind, relative path or external URL, size, modified time, visibility, scan status, and provenance. The v0.1 scan mode does not read file contents, call live provider APIs, summarize with AI, or calculate full file hashes.
