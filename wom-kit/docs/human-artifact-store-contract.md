# Human Artifact Store Contract

Status: v0.4.0 provider-neutral private registry implementation; external adapters remain future

WOM-kit separates three storage roles:

1. Raw data store: source/original files and objets.
2. Human artifact store: user-facing notes, reports, handoffs, diagrams, and reviewed readable artifacts.
3. System/AI artifact store: manifests, source maps, receipts, indexes, hashes, version history, and other machine-oriented records.

The same app can play more than one role, but the role must be named explicitly. For example, a Notion export can be a source/original data source, a Notion workspace page can be a human artifact, and a WordPress post can be a projection surface. None of those app records automatically becomes the canonical WOM archive.

## Why This Contract Exists

Users will not all choose the same app. One person may want WordPress posts,
another may keep working notes in Joplin, another may live in Notion, and
another may keep Markdown files in an Obsidian vault. WOM should support those
choices without confusing any app with the WOM core.

This contract is the shared adapter shape for those user-selected surfaces. It
keeps the app-specific part small and keeps the WOM archive responsible for
system records, provenance, receipts, source maps, and minting.

## Role Matrix

| Surface | Typical role | Useful for | Must not become |
| --- | --- | --- | --- |
| WordPress | projection surface | reviewed public or private posts/pages | the mint record or raw data store |
| Joplin | working note store / human artifact store | living notes, diagrams, handoffs, reusable capture actions | the system/AI artifact store |
| Notion | workspace note / source export, depending on context | pages, databases, exported source bundles | an implicit archive authority |
| Obsidian | local Markdown vault / working note store | vault-relative notes, backlinks, human-readable Markdown | a replacement for manifests or receipts |
| Generic Markdown/workspace | local human artifact mirror | portable notes and reviewed reports | a substitute for capture receipts |

The app name is never enough. A future adapter must say which role it is
playing for this archive, this project, and this action.

## CLI Preview

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli human-artifact-store wom-kit\examples\fake-life-archive `
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

## v0.4.0 Private Registry

The provider-planning command above remains read-only. v0.4.0 adds a separate
local registry for human artifacts under one of two explicitly reviewed roots:

- `external_project` scans only `<registered-root>/.wom-scratch`; and
- `external_delivery` scans the registered root itself (`.`), for example an
  exact delivery folder the human selected.

Both are bounded metadata-only scopes. WOM never opens artifact bodies, never
auto-discovers Downloads or a home directory, and never scans an unregistered
root. Registration must complete through exact-human approval before that root
contributes scan coverage or closeout authority.

```powershell
# Bind exactly one project root after native exact-human review.
archive human-artifact-register-root <archive-root> `
  --project-root <project-root> `
  --root-kind external_project `
  --dry-run --format json

archive human-artifact-register-root <archive-root> `
  --project-root <project-root> `
  --root-kind external_project `
  --expected-plan-sha256 <sha256> `
  --reviewed-by <actor> `
  --approve --format json

# Or bind one explicitly reviewed delivery folder itself.
archive human-artifact-register-root <archive-root> `
  --external-root <delivery-root> `
  --root-kind external_delivery `
  --dry-run --format json

# Always read-only, bounded metadata scan. Bodies and path values are not returned.
archive human-artifact-scan <archive-root> --format json

# Append one lifecycle receipt; never change or delete the artifact itself.
archive human-artifact-transition <archive-root> `
  --artifact-id <opaque-id> `
  --target-state <state> `
  --content-sha256 <sha256> `
  --size-bytes <bytes> `
  --dry-run --format json
```

Approved root registration and lifecycle transition use the v0.4.0 exact-human
sequence: native TaskDialog, authenticated durable `started` claim, writer
binding revalidation, and workflow-only finalization. There is no issued
approval token or expiry window. The registry is stored inside the archive's
ignored private profile boundary and exposes only content-free identifiers,
digests, counts, states, and safe relationship kinds.

MCP exposes `human_artifact_root_registration_plan`,
`human_artifact_registry_scan`, and `human_artifact_transition_plan` as
read-only surfaces. The registration plan accepts the same `root_kind` values.
`--project-root` and `--external-root` are CLI aliases for the selected exact
root; neither changes the scan rule encoded by `root_kind`. Any MCP write intent
returns the local-interactive-CLI requirement; the caller cannot provide an
approval claim.

## Adapter Contract Questions

A future external human artifact store adapter must answer these questions before it can
write to a user-facing app:

- What can the adapter list, read, write, update, retire, or delete?
- Does it write text/Markdown only, or can it attach binaries?
- Which stable external references can be stored without secrets, tokens,
  provider URLs, local absolute paths, or private account details?
- What human artifact templates are allowed: note, report, handoff, cover,
  status log, meeting note, or projection draft?
- Which template fields control title, sections, tags, notebooks, folders,
  citation links, source refs, and review status?
- How does a human artifact link back to WOM refs such as `object_id`, `zet`,
  source map entry, manifest entry, project-intake receipt, or capture receipt?
- Which fields are safe to version in Git, and which must stay local/private?
- How does the adapter represent deletion, retirement, or supersession without
  silently destroying archive evidence?
- Which system/AI artifacts are written outside the app after a human artifact
  is created or updated?
- Which future writes require a separate human approval receipt?

## Capture Action Shape

Field use shows that people want a short explicit action for saving an AI
conversation or work result into their chosen human-facing app. WOM should treat
that as a capture action, not as automatic memory.

```text
human talks with AI
        |
        v
human explicitly asks to capture a note/report/handoff
        |
        v
human artifact store writes or updates a readable artifact
        |
        v
system/AI artifact store records refs, source maps, receipts, and hashes
```

The final system/AI record is the part a simple note app usually does not
provide by itself. A readable note can help the human, but it is not
automatically a manifest, source map, receipt, index entry, or trusted memory.

## Boundary

`archive human-artifact-store --dry-run` writes nothing and never calls an external app. MCP exposes the same read-only contract as `human_artifact_store_plan`. Neither surface starts OAuth, creates notes, updates notes, deletes notes, publishes posts, attaches binaries, uploads files, mints zets, cleans source folders, or runs ZET transport.

The v0.4.0 private registry can write only its own root-binding and append-only
lifecycle evidence after local exact-human approval. It never writes, updates,
retires, moves, or deletes the human artifact itself; never follows an
unregistered root; never returns file names, paths, or bodies; and never calls
an external provider. An `external_project` `.wom-scratch` scope or an
`external_delivery` exact-root scope is discovery and closeout coverage only,
not permission to treat its contents as canonical WOM memory. Closeout remains
false while registered scan coverage is incomplete or any observed artifact
lifecycle is unresolved.

The command returns the contract that a future adapter must satisfy before WOM-kit can safely write to a user-facing app:

- what the app can list, read, write, update, or delete,
- how stable app refs are represented without secrets or local absolute paths,
- which human artifact templates are allowed,
- how citation and cited-by links map back to WOM refs,
- which system/AI artifacts stay outside the app,
- which future writes require explicit human approval and receipts.

This is intentionally conservative. A useful human note is not automatically a source map, manifest, receipt, index entry, or trusted system memory. Future app-specific adapters must preserve that separation.

## First Safe External-Adapter Step

The first safe future write adapter should still be narrow:

1. Preview the intended human artifact write.
2. Show the external surface role and safe external ref.
3. Require explicit human approval.
4. Write or update exactly one human artifact.
5. Write a separate local WOM receipt describing what changed.
6. Keep provider credentials, local paths, and private account data out of
   public archive records.

For a concrete Notion source-export example, see
[Notion Source Export Three-Store Example](notion-source-export-three-store-example.md).
