# Family Archive Agent Rules

This archive is a shared household or family memory space.

## Read Order

1. Read `archive.yml`.
2. Read relevant `views/*.yml`.
3. Search `zettels/` for canonical family records.
4. Read object manifests only when file metadata is needed.

## Write Policy

- Write AI-generated zettel drafts only to `inbox/`.
- Preserve each person's private archive boundary.
- Child-related records should name the child/dependent as a subject when appropriate.
- Do not expose private source notes from a member's personal archive unless explicitly shared.

## AI Intake Protocol

- BEFORE copying any local file into the archive or an objet store, run `archive source-intake <archive-root> --dry-run --local-path <file>` and follow its `next_safe_actions`.
- Stage capture candidates inside the archive root under `staging/incoming/`, never in a raw in-root `objets/` folder.
- Capture only via `objet-capture-selection` -> `objet-capture` with explicit owner approval; real archives also need an owner-approved `objet-capture-enable` record.
- Bulk external stores are not per-file copies: register evidence with `prehashed-objet-ledger` and `object-storage-upload-evidence` instead.

## Succession

Family records about a child should be modeled so they can later be transferred or copied into that child's own archive with provenance.

The family or household may be the owner while parents or guardians are operators. When a child becomes the owner of their own archive later, that change must be represented as an ownership-transfer receipt rather than an invisible folder rename.
