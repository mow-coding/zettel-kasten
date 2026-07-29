# Decision Log: v0.3.285 Notion Manifest Index-Title Fallback

Date: 2026-07-30

## Context

The v0.3.262-v0.3.276 title work can diagnose and repair existing canonical
zettels whose titles are provider identifiers. Beta feedback showed a
different recurrence point: a new Notion JSON/YAML manifest item can carry an
identifier-shaped primary title even when that same item also carries one
human-readable lowercase top-level `index` string.

This release addresses only that new-import boundary. It is not another
archive-wide title repair, a provider-mirror join, or a generated-index
feature.

## Decision

1. Resolve the existing primary import title first.
2. Keep a normal human-readable primary title. A human title always wins.
3. Consider a fallback only when:
   - `source_system` is `notion`;
   - the input is one JSON/YAML manifest item object;
   - the resolved primary title is identifier-shaped; and
   - that same object has the exact lowercase top-level key `index`.
4. Use the existing identifier comparison: after removing spaces, dots,
   underscores, and hyphens, the title is a hexadecimal run of 16 or more
   characters.
5. Require the fallback to be a string.
6. Pass the candidate through the shared title normalization, whitespace,
   specificity, identifier, 500-character, local-path, provider-locator, and
   secret-like metadata boundaries.
7. If an exact `index` key is present but its value is unsafe, block that item
   with a fixed content-free code. Do not copy the rejected value into the
   item-derived CLI projection, item warning/error text, draft, or receipt
   item projection.
8. Use the same resolver for file-backed and inline-content manifest items.
9. Preserve legacy title selection when the exact `index` key is absent.
10. Freeze one external-import discovery projection inside an approved
    `import_external_archive()` call and use it for both planning and writes.
11. Keep the existing CLI approval model. Do not claim that a later,
    separately approved invocation is digest-bound to an earlier dry-run.
12. Leave `facets.source_page_id` on the existing safe-facet path. Do not use
    it to find or select a fallback title.
13. Add no provider call, mirror read, database join, generated-index update,
    or existing-zet rewrite.
14. When a fallback is rejected, replace every user-derived public item
    identity field in the preview and receipt preview with one content-free
    placeholder. Compare the candidate with the effective string form of
    `external_id` plus the raw `external_id` and `id` fields, so numeric and
    other scalar ids cannot bypass the match gate.
15. Treat `facets.source_page_id` as private across aliases. Withhold any
    public preview or receipt field that would repeat it. If it would become
    either an explicit or deterministic generated zettel id and public target
    filename, block the Notion item
    with `source_page_id_aliases_public_target_path` instead of producing an
    untruthful receipt or exposing the private value.
16. For path-backed Notion manifest items with an explicit identifier-shaped
    primary title, run the metadata-only `index` fallback gate before
    resolving or reading the item path. Keep item-path resolution errors
    content-free so an unsafe fallback/path alias cannot be disclosed by an
    earlier I/O branch.
17. Define privacy aliasing at the item projection boundary: the seven item
    identity fields plus generated target-path safety. Do not recursively
    scrub independently supplied operational/provenance metadata such as the
    `--export` path, target archive id, or `--reviewed-by` value merely because
    an operator supplied coincident text. Those values keep their existing
    truthful result and receipt semantics.
18. Keep manifest item file-discovery failures content-free. Unsupported,
    missing/unsafe, unreadable/undecodable, and empty file branches must not
    include the item path or filename because a private `source_page_id` alias
    can reach those branches before an item projection exists.
19. Treat manifest item paths as export-relative on every platform. Reject
    POSIX absolute, UNC, Windows drive-absolute, Windows drive-relative, and
    parent-traversing forms before joining. Wrap both root and candidate
    resolution failures, including symlink-loop `RuntimeError`, in one
    content-free error.
20. Resolve each item file and export root inside one guarded discovery block,
    derive the relative path from that pair, and catch late
    containment/relative-path resolver failures before reading or projecting.
21. When `target_path` is already private/withheld on a blocked item, skip the
    target-existence filesystem probe. It cannot change apply authority and can
    only expose protected text through a corrupted/reparse path exception.

## Explicitly Excluded Inputs

The resolver does not interpret:

```text
Index
properties.index
properties.Index
rich-text arrays
pages.index.jsonl
```

It does not apply to Google Drive manifest items or directory-only Markdown
imports.

## Rationale

Title precedence must preserve human authorship. A normal title already
contains stronger same-record evidence than a fallback field, so it cannot be
silently replaced.

The exact lowercase top-level key is narrow enough to use without guessing a
provider schema. Reading nested or differently cased fields, rich-text
objects, `pages.index.jsonl`, or a source mirror would introduce a separate
join and provenance contract that this release has not reviewed.

Reusing the existing title and privacy gates prevents `index` from becoming a
side door around normalization, identifier rejection, path/locator blocking,
or secret-like metadata handling.

One frozen projection closes a same-call time-of-check/time-of-use gap. It
does not expand approval authority across two CLI processes. Cross-invocation
dry-run digest binding would require a separate public plan/approval contract.

## Consequences

- New Notion manifest items can avoid identifier-shaped draft titles when
  safe same-item human title evidence already exists.
- Human-readable primary titles are unchanged.
- File-backed and inline-content items make the same title decision.
- An unsafe present fallback fails closed without disclosing its value.
- A path-backed item cannot bypass that fail-closed result through an earlier
  path-resolution, file-suffix, missing-file, or empty-file branch.
- Early file-discovery warnings identify the reason but omit item filenames
  and paths, including read/decode failures.
- A drive-qualified path cannot be reinterpreted as a colliding relative file
  under the export root, and resolver failures cannot escape as tracebacks.
- Late item-path resolution and blocked private-target probes cannot reopen a
  path-based disclosure after the initial manifest gate.
- A rejected fallback cannot reappear through another preview field, and a
  private source-page id cannot reappear through an aliased public field.
- A source-page id that would become a target filename blocks before any
  draft or receipt write.
- Existing inbox drafts and canonical zettels remain byte-for-byte untouched.
- No `facets.index`, `source_index_path`, title-repair receipt, or new schema
  is introduced.
- `pages.index.jsonl`, provider mirrors, Notion API records,
  `source_page_id` joins, facet projection, and generated-index improvements
  remain separate future work.
- A separately approved import invocation must still be reviewed against its
  current inputs; an earlier dry-run does not authorize it by digest.
