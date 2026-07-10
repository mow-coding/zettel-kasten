# Personal Archive Agent Rules

This archive is a local-first personal memory space.

## Read Order

1. Read `archive.yml`.
2. Read relevant `views/*.yml`.
3. For archive-wide understanding, run `archive zet-catalog <archive-root> --status canonical --cursor 0 --dry-run --format json`.
4. Follow every `next_cursor` with the same snapshot id until `complete: true`; restart at cursor 0 if the catalog changed.
5. Use the returned abstracts, ties, and edges to choose a useful body-reading order. A search result or one truncated page is never full coverage.
6. Read selected zet bodies with `read-zettel --section overview` first, then `--section document|body` when the host task needs the body.
7. Read `objects/manifests/files.jsonl` only when original file metadata is needed.

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

## AI-Operator Discipline

- PROVENANCE FIDELITY: record the source the human ACTUALLY encountered — the exact video, edition, translation, or language they saw. Never silently swap it for a "more authoritative" or "original" source. If a better source exists, ASK; if it is recorded, keep it as a SEPARATE ref, not a replacement of the encountered one. The archive preserves the provenance of the user's own thought, not the canonical work behind it.
- ENUMERATE TOOLS BEFORE DECLARING IMPOSSIBLE: before you say a task cannot be done or degrade it (e.g. "verbatim capture is not possible, I will summarize"), systematically check the installed and available tools — local CLIs, MCP servers, and the derive-text tool-readiness surface. Do not conclude "impossible" from one or two probes.
- CARRY ESTABLISHED STATE: carry forward what has already been set up or approved in this session or recorded in operational-context (credentials configured, permissions granted, resources present). Do NOT re-ask for or re-confirm already-established state as if first-time. When unsure, CHECK the recorded context (operational-context, receipts) before asking again.

## Plain-Language for Humans

- When you address a HUMAN, translate git/infrastructure/WOM-internal jargon into everyday language; keep the exact technical term in parentheses or in the logs only.
- Say "the update files arrived but the update button hasn't been pressed yet (fetched, not checked out)", not "fetched to the mirror, not checked out".
- Say "a saved bookmark to a specific version (a pin)"; say "the list of which files exist and their fingerprints (the manifest)".
- This governs human-facing prose only. Machine, JSON, and receipt output stays exact and unchanged.

## Privacy

Personal records are private by default. When deriving content for company, family, or shared archives, create a sanitized derivative rather than exposing private sources.

