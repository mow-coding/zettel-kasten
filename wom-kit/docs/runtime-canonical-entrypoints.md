# Runtime Canonical Entry Points

Status: v0.3.58 read-only runtime canonical entrypoint checkpoint

When an AI runtime enters a WOM archive, it needs a small, explicit "start
here" map. The archive may contain zets, source bindings, provider metadata,
object manifests, receipts, local instructions, and generated indexes. Without a
canonical entrypoint summary, an agent can mistake a partial export, mirror, or
secondary folder for the archive source of truth.

v0.3.58 adds that map to:

```powershell
archive runtime-context <archive-root> --format json
```

The result includes `canonical_entrypoints`.

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

v0.3.58 does not enforce migration, auto-upgrade project folders, scan file
contents, choose between competing exports, synchronize providers, or run IMAP
adapters. It only gives AI runtimes a deterministic archive-relative map of what
to consult first.
