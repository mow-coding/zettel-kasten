# Notion Import Locator Evidence Plan

Status: v0.3.287 read-only occurrence-alignment checkpoint

## Purpose

Historical Notion imports can contain the fixed body marker:

```text
[source locator omitted]
```

The v0.3.277 locator-loss audit counts those markers and checks whether a
private `source_page_id` join key survived. That census does not read a source
mirror and cannot tell which original URL occurrence belongs at which marker.

`notion-import-locator-evidence-plan` is the next safety rung. It checks a
human-reviewed, private JSONL evidence file against the exact current bytes of
the matching canonical zets. It does not restore a URL.

## Command

Place the reviewed evidence under the archive's private scratch boundary:

```text
.wom-scratch/notion-locator-evidence/<private>.jsonl
```

Then run:

```powershell
archive notion-import-locator-evidence-plan <archive-root> `
  --evidence ".wom-scratch/notion-locator-evidence/<private>.jsonl" `
  --dry-run `
  --format json
```

The command is CLI-only. There is no MCP tool for this surface.

## Evidence Row

One JSON object appears on each line:

```json
{
  "schema": "wom-kit/notion-locator-occurrence-evidence/v0.1",
  "source_page_id": "<private-source-page-id>",
  "basis": "reviewed_local_mirror",
  "source_snapshot_sha256": "sha256:<64-lowercase-hex>",
  "expected_canonical_sha256": "sha256:<64-lowercase-hex>",
  "occurrences": [
    {
      "source_occurrence_ordinal": 1,
      "marker_ordinal": 1,
      "locator": "https://example.invalid/private-source-location"
    }
  ]
}
```

The file is private working evidence. Do not commit it. The public schema is
[`../schemas/notion-locator-occurrence-evidence.schema.json`](../schemas/notion-locator-occurrence-evidence.schema.json).

## What Establishes A Match

The only join authority is the exact nested frontmatter key
`facets.source_page_id`.

The planner does not join by:

- zet id or path;
- title or filename;
- `index`, `external_id`, or another page-reference facet;
- a provider URL;
- nearby body text; or
- a guessed relationship between records.

Dashed and compact UUID forms can identify the same Notion page. Other
identifiers remain case-sensitive; the planner does not lowercase arbitrary
private identifiers.

If one source page produced multiple canonical zets, the reviewed
`expected_canonical_sha256` must select exactly one current byte snapshot. A
missing match, changed file, or multiple exact matches blocks the row.

## What Establishes Occurrence Alignment

A row is `aligned_for_human_review` only when:

1. one current canonical Notion-import zet matches the private join key and
   expected file hash;
2. the body marker count, the import-time omitted count, and the number of
   evidence occurrences are the same positive number;
3. source occurrence ordinals are exactly `1..N`, once each;
4. marker ordinals are exactly `1..N`, once each; and
5. every locator is a bounded absolute HTTP(S) locator.

The explicit source-to-marker ordinal pairs come from human review. Equal
counts alone are not occurrence proof.

Repeated identical locator strings are allowed when they represent different
source occurrences. Locator strings stay private and are not normalized,
fingerprinted, or returned.

## Safe Output

The result contains:

- safe row numbers and fixed status/blocker codes;
- marker, declared-omission, and occurrence counts;
- aggregate aligned, blocked, covered, and uncovered counts;
- whether the supplied batch covers every currently affected canonical zet;
- the whole evidence-file SHA-256; and
- one `plan_digest` that binds the evidence snapshot and exact reviewed
  alignment inputs.

The result does not contain:

- source page ids or fingerprints;
- locators or locator fingerprints;
- zet ids, filenames, or local paths;
- titles, body text, or surrounding context;
- tokens, account ids, or secret values.

`--max-items` limits only the returned safe row summaries. Every accepted
evidence row still contributes to validation and complete aggregate counts.

`coverage_complete: false` means only that this evidence batch does not cover
every affected canonical zet. It does not mean the uncovered locators are
permanently lost.

## Input Safety

The planner:

- accepts only an archive-relative `.jsonl` file under the private scratch
  folder;
- rejects traversal, drive-qualified, UNC, symlink, junction, and reparse
  paths;
- reads one bounded evidence snapshot;
- enforces a 64 MiB file limit, 1 MiB line limit, and 5,000-row limit;
- detects duplicate JSON keys and unsupported fields;
- catches invalid UTF-8, JSON, excessive nesting, and I/O failures without
  printing private input;
- reads matched canonical files with per-file and total byte ceilings; and
- decodes canonical UTF-8 BOMs from the same bytes that were hashed.

## Read-Only Boundary

This command:

- writes no canonical zet;
- inserts no locator;
- writes no receipt, edge, facet, index, or diagnostic;
- calls no Notion API, provider, model, or MCP tool;
- parses no raw `recordMap`, `pages.index.jsonl`, or `properties['비고']`
  export; and
- does not handle the separate 77 coordinate variants reported by the beta
  tester.

There is intentionally no restoration writer in v0.3.287. A later release can
design one only after reviewed evidence plans demonstrate deterministic
occurrence alignment and the write/recovery boundary receives its own tests
and approval protocol.

## Recommended Review Loop

1. Run `notion-import-locator-loss-audit` to refresh the current census.
2. Build a private evidence batch from a locally reviewed source snapshot.
3. Record the exact source snapshot and canonical file hashes.
4. Run this planner and fix only rows reported as blocked.
5. Have a human compare every aligned row with the source snapshot again.
6. Preserve the evidence SHA and `plan_digest` for the future writer design.
7. Do not edit canonical zets by hand to make a blocked row pass.
