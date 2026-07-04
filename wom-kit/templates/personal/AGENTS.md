# Personal Archive Agent Rules

This archive is a local-first personal memory space.

## Read Order

1. Read `archive.yml`.
2. Read relevant `views/*.yml`.
3. Search `zettels/` for canonical records.
4. Read `objects/manifests/files.jsonl` only when original file metadata is needed.

## Write Policy

- Write AI-generated zettel drafts only to `inbox/`.
- Do not edit `zettels/` unless the user explicitly asks to promote or modify a canonical zettel.
- Do not store provider URLs in zettels.
- Preserve provenance, visibility, and source boundaries.

## AI Intake Protocol

- BEFORE copying any local file into the archive or an objet store, run `archive source-intake <archive-root> --dry-run --local-path <file>` and follow its `next_safe_actions`.
- Stage capture candidates inside the archive root under `staging/incoming/`, never in a raw in-root `objets/` folder.
- Capture only via `objet-capture-selection` -> `objet-capture` with explicit owner approval; real archives also need an owner-approved `objet-capture-enable` record.
- Bulk external stores are not per-file copies: register evidence with `prehashed-objet-ledger` and `object-storage-upload-evidence` instead.

## Plain-Language for Humans

- When you address a HUMAN, translate git/infrastructure/WOM-internal jargon into everyday language; keep the exact technical term in parentheses or in the logs only.
- Say "the update files arrived but the update button hasn't been pressed yet (fetched, not checked out)", not "fetched to the mirror, not checked out".
- Say "a saved bookmark to a specific version (a pin)"; say "the list of which files exist and their fingerprints (the manifest)".
- This governs human-facing prose only. Machine, JSON, and receipt output stays exact and unchanged.

## Privacy

Personal records are private by default. When deriving content for company, family, or shared archives, create a sanitized derivative rather than exposing private sources.

