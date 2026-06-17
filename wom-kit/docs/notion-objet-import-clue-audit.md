# Notion Objet Import Clue Audit

Status: v0.3.104 read-only import material-clue audit
Date: 2026-06-17

`notion-objet-import-clue-audit` checks whether imported Notion zettels still
have a safe material clue after provider locators were omitted from body text.

It is the companion to `notion-objet-source-map-link-plan`: the audit answers
"which imported zets are safe, recoverable, or missing a clue?", while the
source-map planner proposes candidate `embed` edges for the recoverable rows.

## Command

```bash
archive notion-objet-import-clue-audit <archive-root> --dry-run --format json
```

Optional explicit inputs:

```bash
archive notion-objet-import-clue-audit <archive-root> \
  --source-map source-maps/notion-export.jsonl \
  --ledger receipts/import/notion-download-ledger.jsonl \
  --dry-run \
  --format json
```

MCP:

```text
notion_objet_import_clue_audit
```

## What It Checks

For each non-redacted imported Notion zettel, the audit reports one
`material_clue_state`:

- `preserved_object_ref_or_edge`: the zettel already has a safe object ref or
  object edge in frontmatter.
- `source_map_join_available`: the zettel has no object ref yet, but source
  maps and optional ledgers can propose a material candidate.
- `missing_material_clue_after_locator_omission`: the zettel says provider
  locators were omitted, but no object ref, edge, or source-map candidate is
  available.
- `no_omission_signal_or_body_locator_path_needed`: the audit did not see an
  omission signal or material clue, so older body-locator tools may still be the
  right check if body locators remain.

The output gives counts and archive-relative zettel ids/paths only. It does not
return page titles, source-map values, provider locators, provider URLs, or body
text.

## Boundary

`notion-objet-import-clue-audit` is read-only and dry-run only.

It writes nothing, rewrites no zettel body text, writes no edges, writes no
receipts, reads no zettel body text, reads no object bytes, calls no providers,
and creates no presigned URLs.

It echoes no provider URLs, provider locator text, page titles, zettel body
text, frontmatter values, absolute local paths, account ids, emails, tokens, or
secret values.

## Relationship To Other Notion Objet Tools

Use this order:

1. `runtime-context` to confirm the archive and local instructions.
2. `ai-response-concept-guide` for current safe routing.
3. `notion-objet-import-clue-audit` to see whether imported Notion zettels kept
   or can recover a material clue after locator omission.
4. `notion-objet-source-map-link-plan` for zettels with
   `source_map_join_available`.
5. `notion-objet-link-index` and `notion-objet-link-plan` when body locators
   still exist.
6. Approval-gated `zettel-edge` or `zettel-edge-batch` only after human review.

## Import-Time Contract

An import that removes provider locators from bodies must preserve at least one
safe material clue outside the body:

- a `source_refs` object id,
- a reviewed or planned `embed` candidate,
- a source-map/ledger row that can join page -> file -> `sha256`.

If an imported zettel only records `source_locator_omitted_count`, this audit
will classify it as missing a material clue unless the source-map/ledger trail
can recover one.
