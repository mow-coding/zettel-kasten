# Fake Life Archive Agent Rules

This is a sample archive for testing WOM-kit v0.1.

## Rules

- Start every archive session with `archive ai-start-here <archive-root> --dry-run --progress --format json`, then follow the returned `action_routing`.
- Treat `zettels/` as canonical.
- Treat `inbox/` as AI draft space.
- Search with `archive search <archive-root> <query> --count-total --format json`; raw grep and raw SQL are not authoritative WOM search results.
- When Doctor reports a possible inbox pipeline bypass, inspect it with `archive inbox-pipeline-audit <archive-root> --dry-run --format json`; its classes are review signals, not proof, and authorize no automatic repair.
- Create drafts only through `archive create-draft` dry-run and its human-reviewed replay; never write Markdown directly into `inbox/`.
- Do not move an inbox draft into `zettels/` without a separate `archive mint-zet` preview and explicit human approval.
- Add relationships and capture source material only through the official `zettel-edge` and source/objet intake routes.
- Use `views/homebase.yml` as the default AI context lens.
- Treat saved-view recommendations as read-only; there is no dedicated persistent saved-view writer yet, so an AI must not edit `views/*.yml` directly.
- Resolve original files through `objects/manifests/files.jsonl`.
- Do not infer provider storage locations from zettels.

## AI Intake Protocol

- BEFORE copying any local file into the archive or an objet store, run `archive source-intake <archive-root> --dry-run --local-path <file>` and follow its `next_safe_actions`.
- Stage capture candidates inside the archive root under `staging/incoming/`, never in a raw in-root `objets/` folder.
- Capture only via `objet-capture-selection` -> `objet-capture` with explicit human approval; real archives also need an owner-approved `objet-capture-enable` record.
- Bulk external stores are not per-file copies: register evidence with `prehashed-objet-ledger` and `object-storage-upload-evidence` instead.

