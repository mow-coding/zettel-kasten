# Fake Life Archive Agent Rules

This is a sample archive for testing WOM-kit v0.1.

## Rules

- Treat `zettels/` as canonical.
- Treat `inbox/` as AI draft space.
- Do not move an inbox draft into `zettels/` without explicit human promotion.
- Use `views/homebase.yml` as the default AI context lens.
- Resolve original files through `objects/manifests/files.jsonl`.
- Do not infer provider storage locations from zettels.

## AI Intake Protocol

- BEFORE copying any local file into the archive or an objet store, run `archive source-intake <archive-root> --dry-run --local-path <file>` and follow its `next_safe_actions`.
- Stage capture candidates inside the archive root under `staging/incoming/`, never in a raw in-root `objets/` folder.
- Capture only via `objet-capture-selection` -> `objet-capture` with explicit human approval; real archives also need an owner-approved `objet-capture-enable` record.
- Bulk external stores are not per-file copies: register evidence with `prehashed-objet-ledger` and `object-storage-upload-evidence` instead.

