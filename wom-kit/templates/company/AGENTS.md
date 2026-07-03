# Company Archive Agent Rules

This archive is a scoped company memory space.

## Read Order

1. Read `archive.yml`.
2. Read relevant `views/*.yml`.
3. Search `zettels/` for canonical company records.
4. Read object manifests only when file metadata is needed.

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

## Confidentiality

Company records must stay within authorized company, team, project, or handover archives.

The company can own an archive while founders, employees, or roles operate it. Business-unit exit, spin-out, or ownership transfer must be recorded with explicit receipts.
