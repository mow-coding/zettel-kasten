# Human Artifact Store Contract

Status: Unreleased planning-preview command

WOM-kit separates three storage roles:

1. Raw data store: source/original files and objets.
2. Human artifact store: user-facing notes, reports, handoffs, diagrams, and reviewed readable artifacts.
3. System/AI artifact store: manifests, source maps, receipts, indexes, hashes, version history, and other machine-oriented records.

The same app can play more than one role, but the role must be named explicitly. For example, a Notion export can be a source/original data source, a Notion workspace page can be a human artifact, and a WordPress post can be a projection surface. None of those app records automatically becomes the canonical WOM archive.

## CLI Preview

```powershell
python wom-kit\cli\archive.py human-artifact-store wom-kit\examples\fake-life-archive `
  --dry-run `
  --surface-kind joplin `
  --surface-ref joplin:notebook:work `
  --role working_note_store `
  --format json
```

Supported surface kinds:

- `wordpress`
- `joplin`
- `notion`
- `obsidian`
- `evernote`
- `generic_markdown`
- `generic_workspace`

Supported roles:

- `human_artifact_store`
- `projection_surface`
- `source_export`
- `working_note_store`

## Boundary

`archive human-artifact-store --dry-run` writes nothing and never calls an external app. MCP exposes the same read-only contract as `human_artifact_store_plan`. Neither surface starts OAuth, creates notes, updates notes, deletes notes, publishes posts, attaches binaries, uploads files, mints zets, cleans source folders, or runs ZET transport.

The command returns the contract that a future adapter must satisfy before WOM-kit can safely write to a user-facing app:

- what the app can list, read, write, update, or delete,
- how stable app refs are represented without secrets or local absolute paths,
- which human artifact templates are allowed,
- how citation and cited-by links map back to WOM refs,
- which system/AI artifacts stay outside the app,
- which future writes require explicit human approval and receipts.

This is intentionally conservative. A useful human note is not automatically a source map, manifest, receipt, index entry, or trusted system memory. Future app-specific adapters must preserve that separation.
