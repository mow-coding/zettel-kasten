# Archive Infra Decision Log - v0.3.256 Fail-Closed Zettel Boundary

Date: 2026-07-17
Status: accepted for v0.3.256 implementation and verification

## Context

The post-v0.3.255 Fable5 audit found that the tolerant zettel parser could turn
an invalid frontmatter boundary into empty metadata plus the complete file as
body text. That behavior is useful at a foreign import/capture boundary, but it
is unsafe at an existing-archive read boundary. A malformed file that visibly
contained `status: redacted` could therefore be read, indexed, searched, or
analyzed as ordinary body text because the status itself was no longer trusted.

The same audit found that `index-health` silently skipped a newly unreadable
UTF-8 file. Its live set could then equal the generated-index set and report
`current` even though a physical zettel path was absent from both counts.

Independent reproduction confirmed both defects and also found related bypasses
through common catalog, link-analysis, cleanup, edge, reconcile, migration,
Safe HTML, and foreign-block surfaces. A separate deep audit of approval-heavy
revision, restore, retire-reconcile, abstract-backfill, and target-workpack
flows found additional fingerprint-first paths; those are explicitly assigned
to v0.3.257 rather than silently broadening this core integrity release.

## Decision

1. Keep `split_zettel_text()` tolerant for explicitly foreign/imported caller
   input. Add a separate fail-closed content boundary for existing archive
   zettels.
2. The fail-closed boundary accepts only the exact supported frontmatter
   delimiter grammar, a YAML object, and one lifecycle status from `draft`,
   `canonical`, `archived`, or `redacted`.
3. Invalid delimiter, YAML, object shape, encoding, I/O, missing status, and
   unknown status states never expose a parsed frontmatter value or body. They
   return fixed issue codes only.
4. A valid `redacted` zettel exposes only its existing small redaction envelope
   where a surface already needs existence metadata. Its title, body, facets,
   visibility, links, hashes, counts, and derived analysis remain suppressed.
5. The direct read, query, indexing, health, and adjacent analysis/mutation
   surfaces changed in this release either return a content-free blocked result
   or raise a static sanitized error before analysis or writes. Batch scans skip
   or count unreadable/redacted entries without deriving content.
6. Search, views, facet reports, and related-zets use an allowlist of readable
   lifecycle statuses. This protects an existing v0.3.255 database row with
   null or unknown status even before a rebuild.
7. A full index rebuild does not roll back merely because one zettel is
   unreadable. It commits a path/stat-only row with status `unreadable`, clears
   title/id/kind/body/frontmatter/hash content, and creates no outgoing edge or
   facet rows for that zettel.
8. Such a rebuild is safe but incomplete. Its result is
   `completed_with_quarantined_zettels`, `index_rebuilt: true`,
   `index_complete: false`, `ok: false`, with CLI exit code 1 and fixed
   path/code samples. A captured result remains a completed nonzero result, not
   an exception artifact.
9. `index-health` includes every safely enumerated physical path in the live
   count. It separately reports readable-metadata count and fixed inspection
   issues, sets `live_zettel_frontmatter_unreadable_or_invalid`, and gives a
   repair-first next action. It never recommends rebuilding an invalid source
   file as if rebuilding could repair the source.

## Security And Evidence Boundary

- The generated SQLite index is logically sanitized: WOM query/API surfaces no
  longer return the quarantined row's former logical content.
- This release does not claim forensic secure deletion from SQLite free pages,
  WAL files, filesystem snapshots, backups, or storage media. The source zettel
  itself also still exists. Secure erasure is a different operator/storage
  policy.
- Relative zettel paths and file stat values were already part of archive/index
  operation. Quarantine results expose no absolute path, raw parser exception,
  YAML excerpt, title, body, provider locator, or secret value.
- A malformed delimiter may require reading bytes past the intended
  frontmatter boundary to establish that no valid closing delimiter exists.
  `index-health` reports this honestly through `zettel_body_text_read`; it still
  never echoes those bytes.

## Consequences

- One bad zettel can no longer preserve an older unsafe index by aborting the
  entire rebuild, nor can it be silently omitted from health accounting.
- A nonzero index command can now mean “a safe generated index was installed,
  but source repair is still required.” The result fields distinguish this from
  an exception/rollback failure.
- Older automation that treated every completed index invocation as success
  must honor `ok`, `index_complete`, and the process exit code.
- The stricter boundary can surface previously tolerated malformed or
  status-less archive files as repair work. That is intentional; ambiguous
  lifecycle metadata is not readable content authority.
- This release does not claim that every legacy approval workflow already uses
  the new ordering. v0.3.257 must move strict lifecycle/identity validation
  ahead of hashes, byte counts, equality checks, derived reports, and writes in
  revision/restore, retire-reconcile, abstract-backfill, and target-workpack
  operations.

## Verification Contract

- Supported LF, CRLF, BOM, and delimiter-trailing-space forms remain readable.
- Missing/indented/EOF delimiters, invalid YAML, non-object YAML, missing status,
  invalid status, invalid UTF-8, and I/O failure produce fixed content-free
  issues.
- A malformed redacted canary is absent from list/read/catalog/header/projection,
  objet/Notion analysis, staged cleanup, quality/Safe HTML, ordinary edge,
  remint-reconcile, frontmatter-migration, SQLite logical rows, edges/facets,
  search, view, and related-zets results.
- A legacy unknown-status SQLite row is filtered before rebuild.
- Health counts unreadable physical paths, reports stale/incomplete, and stores
  a completed exit-code-1 diagnostic result without raw content.
- Normal redacted and ordinary draft/canonical/archived behavior remains covered
  by the pre-existing regression suite.
