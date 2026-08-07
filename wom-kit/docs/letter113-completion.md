# Letter 113 completion

Status: v0.3.305 implementation and release evidence guide

Letter 114's publication-completion incident is handled in the same release;
see `docs/letter114-completion.md`.

## Requirement map

| Letter 113 gap | v0.3.305 behavior |
|---|---|
| Ready markup changes trapped behind unrelated blockers | Add `--only-ready` to both `markup-normalization-plan` and `markup-normalization`. The digest binds `ready_only`; blocked zets remain exact and are still reported. |
| File/media reference cannot target a stored objet | `binding_kind: objet` accepts only a full manifested `sha256:<64 hex>` id. File, audio, and video fragments become an opaque `wom-objet:` Markdown link only after exact reviewed binding. |
| Self-closing dates, synced blocks, and numeric table columns remain unknown | Strict ISO dates become text; synced wrappers preserve all inner snapshot content; numeric col width is presentation; explicit row/column header hints become the closest lossless GFM representation. Unsupported attributes still block. |
| Adding account/service coordinates duplicates one locator | One unambiguous same type/ref/occurrence row is enriched in place. Its locator id stays stable; conflicts and ambiguity block; exact before bytes and revert evidence are preserved. |
| Title remap defaults below the implemented limit | Plan and write default to the existing 5,000-row ceiling. |
| One exact short source-export title blocks | A non-generic short exact source name passes only as `source_export_property`, with a warning. `human_written` does not bypass specificity. |

## Operator examples

Ready-only markup:

```powershell
archive markup-normalization-plan <archive-root> --only-ready --dry-run --format json
archive markup-normalization <archive-root> --only-ready --expected-plan-sha256 <digest> --approve --reviewed-by person:<reviewer> --format json
```

Objet binding row:

```json
{"zettel_id":"zet_example","tag_sha256":"<64 lowercase hex>","binding_kind":"objet","binding_id":"sha256:<64 lowercase hex>"}
```

Locator cleanup for rows created before v0.3.305:

1. use the existing successful revert preview/approval for the newer duplicate
   receipt, restoring the original single bare row;
2. rerun the ordinary locator plan with the same ref plus reviewed coordinates;
3. confirm `planned_action: update_locator_coordinates` and approve the exact
   digest; the row count stays one.

No command guesses an objet from a tag, overwrites conflicting coordinates,
silently deletes unresolved markup, or claims live Notion synchronization.
