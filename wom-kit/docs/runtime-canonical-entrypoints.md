# Runtime Canonical Entry Points

Status: v0.3.106 read-only AI guide handoff and material-route discovery checkpoint

When an AI runtime enters a WOM archive, it needs a small, explicit "start
here" map. The archive may contain zets, source bindings, provider metadata,
object manifests, receipts, local instructions, and generated indexes. Without a
canonical entrypoint summary, an agent can mistake a partial export, mirror, or
secondary folder for the archive source of truth.

v0.3.58 adds that map to:

```powershell
archive runtime-context <archive-root> --format json
```

The result includes `canonical_entrypoints`. From v0.3.106, that object also
includes machine-readable `ai_runtime_order`, `recommended_first_commands`, and
`material_link_routes` so a terminal-capable AI can discover the guide handoff
without waiting for the human to mention it.

## AI Runtime Order

When an AI enters an archive, use this order before interpreting or writing
anything:

1. Run `archive runtime-context <archive-root> --format json`.
2. Read `canonical_entrypoints`, especially `archive.yml` and `AGENTS.md`.
3. Run `archive ai-response-concept-guide <archive-root> --topic all --dry-run`
   when the human is asking what to do next.
4. For Notion material links, choose the route from that guide:
   `notion-objet-import-clue-audit` to check omitted-locator imports,
   `notion-objet-source-map-link-plan` when source maps or ledgers can recover
   a candidate, or `notion-objet-link-index` / `notion-objet-link-plan` when
   body locators still exist.

This order keeps archive identity, local instructions, beginner-facing wording,
and material-link safety gates aligned before any later approval-gated write.

The same order is returned in JSON:

```text
canonical_entrypoints.ai_runtime_order
canonical_entrypoints.recommended_first_commands
canonical_entrypoints.material_link_routes
```

The route list includes `notion-objet-import-clue-audit`,
`notion-objet-source-map-link-plan`, `notion-objet-link-index`, and
`notion-objet-link-plan`, with each route marked as read-only and provider-free.

## Start Here

The first authoritative file is:

```text
archive.yml
```

It identifies the archive, type, principal, root policy, and write policy. The
runtime entrypoint summary then lists other archive-relative files/directories
and their roles:

- `AGENTS.md`: local agent instructions,
- `archive-identity.yml`: owner and principal identity context,
- `source-bindings.yml`: source catalog,
- `provider-bindings.yml`: provider setup metadata,
- `zettels/`: canonical zets,
- `inbox/`: draft inbox,
- `objects/manifests/files.jsonl`: objet manifest,
- `objects/manifests/derived-text.jsonl`: derived-text manifest,
- `views/`: saved views,
- `db/schema.sql`: SQLite schema context.

Each item reports only a role, expected kind, required flag, status, and
archive-relative path. Missing optional files remain optional. Missing required
files should make the human or AI stop and repair the archive before treating
the workspace as authoritative.

## Privacy Boundary

The entrypoint check is a map, not an import:

- it reads no file bodies,
- it writes no files,
- it calls no providers,
- it reads no secrets, keyrings, vaults, browser stores, mailboxes, or source
  documents,
- it echoes no local absolute paths by default.

Use `runtime-context --no-redact-local-paths` only for trusted local debugging.

## Not Implemented

v0.3.106 does not enforce migration, auto-upgrade project folders, scan file
contents, choose between competing exports, synchronize providers, write
material links, or run IMAP adapters. It only gives AI runtimes a deterministic
archive-relative map of what to consult first and which read-only guide command
or material-link route to run next.
