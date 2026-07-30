# v0.3.292 Objet Tie-Count Consistency Directive

Date: 2026-07-30

Status: accepted Letter 105 follow-up; implementation starts only after the
v0.3.291 checkpoint is stable and must later rebase onto the exact public
v0.3.291 commit.

## Why This Release Exists

Letter 105 reports a zettel whose `edges_preview` and read-only
`zettel-objet-links` surface find objet relations while
`tie_summary.referenced_objets_count` remains zero.

The source cause is confirmed without running WOM against the beta archive:

- `zettel-objet-links` intentionally scans valid frontmatter and body;
- overview/catalog tie counts use `collect_referenced_objets(frontmatter)`;
- that collector scans `assets`, `source_refs`, and `source_intake`, but not
  structured edge targets.

This release fixes only the structured tie count. It does not claim that body
search, source provenance, external storage resolution, or negative-search
coverage is complete.

## Required Contract

Add a tie-summary-specific helper equivalent to:

```text
collect_tie_summary_objet_ids(frontmatter) -> list[str]
```

It must:

- include objet IDs already recognized in `assets`, `source_refs`, and
  `source_intake`;
- inspect only the canonical edge target fields `target`, `target_id`, and
  `zettel_id`;
- accept only a complete `sha256:<64 hex>` or
  `objet:sha256:<64 hex>` target string;
- normalize both forms to lowercase `sha256:<64 hex>`;
- deduplicate by normalized object ID, not by source or occurrence; and
- feed only `zettel_first_read_summary()` and `zet_catalog_item()` tie counts.

It must not recursively scan arbitrary edge fields. Values found only in
`ref`, `object_id`, `target_object_id`, `edge_id`, receipts, provenance, URLs,
paths, or nested metadata are not relationship targets.

Do not change `collect_referenced_objets()`. That function also feeds
block-header output, source-map preservation decisions, and cleanup safety
counts; broadening it would create unrelated behavior changes.

## Body And Privacy Boundary

Body-only objet references do not count in
`tie_summary.referenced_objets_count`.

```text
tie_summary.referenced_objets_count
  = distinct structured frontmatter objet relationships

zettel-objet-links.count
  = distinct objet IDs discovered across valid frontmatter and body
```

This distinction preserves the catalog's `body_read: false` contract and
keeps overview/catalog counts consistent. Redacted surfaces must return zero
before inspecting or exposing private relationship existence.

## Required Regressions

1. Edge-only objet targets count and normalize; repeated
   `sha256:`/`objet:sha256:` aliases across assets, source refs, source intake,
   `target`, `target_id`, and `zettel_id` count once per distinct digest.
2. Malformed rows, non-string targets, partial/suffixed digests, zettel
   targets, URL/path-contained hashes, and hashes in non-target edge fields
   do not count or echo private values.
3. Redacted overview and catalog surfaces keep count zero, edges empty, body
   unread, and secret title/body/digest absent from serialized output.
4. One fixture with structured objet A/B and body-only objet C proves:
   overview count 2, catalog count 2 with `body_read: false`, and
   `zettel-objet-links` count 3, without body-canary output.

## Release Boundary

This release adds:

- one private service helper;
- focused service/CLI regressions;
- documentation defining the two count scopes;
- version, changelog, decision log, release note, and deterministic packaged
  resource updates.

It adds no command, MCP tool, writer, migration, index rebuild, provider call,
archive mutation, or beta-archive operation.

## Verification And Release Order

1. implement the helper and four regression groups;
2. update catalog, objet-link, capability, upgrade, and release documentation;
3. run focused tests, documentation contracts, resource sync/check, readiness,
   compile, and diff checks;
4. obtain independent adversarial review;
5. checkpoint locally;
6. after v0.3.291 is public, rebase onto its exact merged commit;
7. run the complete suite and exact clean-wheel lifecycle;
8. use PR, main, tag, GitHub Release, unauthenticated download, digest, and
   fresh-install evidence before calling v0.3.292 public.

Beta semantic confirmation remains a later human real-use validation step.
