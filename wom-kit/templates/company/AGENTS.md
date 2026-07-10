# Company Archive Agent Rules

This archive is a scoped company memory space.

## Read Order

1. Read `archive.yml`.
2. Read relevant `views/*.yml`.
3. For archive-wide understanding, run `archive zet-catalog <archive-root> --status canonical --projection reading --coverage-mode strict --cursor 0 --dry-run --format json`.
4. Follow every `next_cursor` with the same snapshot id and continuation token until `archive_wide_coverage_claim_ready: true`; this proves node visitation only, and a changed catalog restarts at cursor 0.
5. Check `archive_wide_abstract_reading_claim_ready` before saying every required abstract was available and read. Report `abstract_coverage` gaps without inventing or auto-writing replacements.
6. Check `archive_wide_followup_resolution_ready` before relying on id-only body reads; duplicate or unreadable ids require repair or an explicitly reviewed path.
7. Inspect `workload_estimate`; use `max_estimated_tokens` to fit the host context, but never replace complete coverage with top-k search.
8. If the host goal already provides verified zet ids, use `--order seeded_connection_walk` with repeated `--start-zettel-id`; never invent a seed, and still read every disconnected component.
9. Keep `projection=reading` for compact coverage. Use `routed_reading` with seeded order only when the human or host needs each item's seed/tie/component reason and can afford the larger payload.
10. Use the returned abstracts, ties, and edges to choose a useful body-reading order. A search result or one truncated page is never full coverage.
11. Read selected zet bodies with `read-zettel --section overview` first, then `--section document|body` when the host task needs the body.
12. Read object manifests only when file metadata is needed.

## Write Policy

- Write AI-generated zettel drafts only to `inbox/`.
- Do not import private personal sources unless the workpack explicitly permits it.
- Prefer sanitized derivative records when personal insight informs company work.
- Preserve handover, provenance, and visibility fields.

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

## Confidentiality

Company records must stay within authorized company, team, project, or handover archives.

The company can own an archive while founders, employees, or roles operate it. Business-unit exit, spin-out, or ownership transfer must be recorded with explicit receipts.
