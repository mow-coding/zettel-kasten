# Decision Log — v0.3.292 Objet Tie-Count Consistency

Date: 2026-07-31

## Context

Letter 105 showed that `zettel-objet-links` and edge previews could recognize
an objet relationship while overview and catalog
`tie_summary.referenced_objets_count` remained zero. The existing tie count
covered `assets`, `source_refs`, and `source_intake`, but not canonical
structured edge targets.

The broader link preview scans valid frontmatter and body. Catalog and
overview privacy contracts must not silently become body-search surfaces.

## Decision

- Count distinct structured frontmatter objet relationships in overview and
  catalog tie summaries.
- Preserve the existing recognized frontmatter sources and add only exact edge
  fields `target`, `target_id`, and `zettel_id`.
- Accept only complete `sha256:<64 hex>` and
  `objet:sha256:<64 hex>` target strings, normalize them to lowercase
  `sha256:<64 hex>`, and deduplicate by digest.
- Do not recursively inspect arbitrary edge fields, nested metadata, receipts,
  provenance, URLs, or paths.
- Replace a direct edge target with the fixed `<redacted-reference>`
  placeholder when it contains an object-ID marker but is not one complete
  accepted canonical ID, or when the target is non-string. A rejected value
  must not leak through the overview or catalog preview.
- Do not change `collect_referenced_objets()`, because its block-header,
  source-map preservation, and cleanup-safety consumers have a different
  compatibility boundary.
- Keep `zettel-objet-links.count` as the broader distinct-ID count across valid
  frontmatter and body. That separate command recursively token-scans valid
  frontmatter, so an exact object-ID token inside nested metadata, URL text, or
  path text can be a link-preview occurrence without becoming a structured tie
  relationship.
- Keep catalog `body_read: false`; body-only references do not affect
  `tie_summary.referenced_objets_count`.
- Return zero ties and empty edges for redacted overview and catalog surfaces
  before private relationship existence is inspected or exposed.

## Consequences

- Edge-only canonical objet targets become visible in the existing structured
  tie count.
- Malformed object-shaped direct targets no longer leak through neighboring
  overview or catalog edge previews.
- A broader link-preview count can honestly exceed an overview or catalog tie
  count.
- Existing archives require no migration or rewrite.
- No command, MCP tool, writer, index, provider call, object resolution, or
  archive-mutation boundary changes.

Chronology and implementation evidence are recorded in
`meeting-minutes/2026-07-31-v03292-objet-tie-count-consistency-implementation.md`.
