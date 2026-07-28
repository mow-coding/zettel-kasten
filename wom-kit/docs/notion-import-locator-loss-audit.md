# Notion Import Locator-Loss Audit

Status: v0.3.277 read-only omission-marker census
Date: 2026-07-28

`notion-import-locator-loss-audit` measures what was lost when a historical
Notion import replaced source locators with:

```text
[source locator omitted]
```

This is the first step of recovery, not a restoration command. It answers:

- how many imported zets contain the marker;
- how many markers exist in their bodies;
- whether that number still agrees with the import-time
  `source_locator_omitted_count`;
- whether `source_page_id` survived as a possible source-mirror join key;
- which known Notion import family produced each affected zet.

## Command

```powershell
archive notion-import-locator-loss-audit <archive-root> `
  --dry-run `
  --format json
```

Short alias:

```powershell
archive notion-locator-loss-audit <archive-root> `
  --dry-run `
  --format json
```

Use `--max-items N` to limit returned per-zet summaries. The command still
scans the complete archive so its aggregate counts remain complete.

For a large archive, add `--progress`. Content-free progress is printed to
stderr every 250 zets while the final text or JSON result remains on stdout:

```powershell
archive notion-import-locator-loss-audit <archive-root> `
  --dry-run `
  --progress `
  --format json
```

## Reading The Result

Important summary fields:

- `affected_zettel_count`: imported Notion zets whose body contains at least
  one omission marker;
- `body_marker_count`: total markers currently found in those bodies;
- `frontmatter_omitted_count`: total import-time count recorded on those same
  zets;
- `marker_frontmatter_count_delta`: current markers minus recorded markers;
- `count_mismatch_zettel_count`: zets that require occurrence alignment before
  any restoration proposal;
- `source_page_id_present_count`: affected zets that retained the intended
  source-page join key;
- `source_page_id_missing_count`: affected zets that require a different,
  separately reviewed provenance route.

Each returned item has one count state:

- `exact`;
- `body_marker_count_exceeds_frontmatter`;
- `frontmatter_count_exceeds_body`.

It also has one source-evidence state:

- `source_page_join_key_preserved`;
- `source_page_join_key_missing`.

`source_page_id` values themselves are never returned.

## Why Count Agreement Matters

An omission marker is only a placeholder. It does not identify the original
URL, its source block, or its exact position among several source locators.

If the current marker count differs from the import-time count, a later tool
must not pair markers and source URLs by list position. It must first prove an
occurrence-level alignment from retained source evidence. Otherwise one wrong
match can put a valid URL into the wrong sentence.

Even an exact count is not permission to write. It only makes a later
read-only source-mirror comparison possible.

## Boundary

This command is CLI-only, read-only, and requires `--dry-run`.

It reads non-redacted imported Notion zet bodies only to count the exact
omission marker. It does not return body text, nearby context, provider URLs,
raw frontmatter values, source-page ids, page titles, account data, secrets,
or absolute local paths.

It reads no source mirror, object bytes, source map, or download ledger. It
calls no provider or model. It writes no zet, facet, edge, receipt, index,
diagnostic, or plan file.

Provider-locator reconstruction and retroactive body writing remain
unimplemented in v0.3.277.

## Safe Follow-Up

1. Run this census and retain its aggregate result outside the archive if
   operational evidence is needed.
2. For `source_page_join_key_preserved`, join the private
   `source_page_id` value to one explicitly reviewed source mirror without
   echoing the value.
3. Keep count-mismatch zets out of any automatic proposal.
4. For missing join keys, review provenance and existing derived-from evidence.
   Do not infer a page from similar titles, neighboring ids, or references.
5. Add a separate read-only occurrence-alignment plan before designing any
   approval-gated canonical write.
