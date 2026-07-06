# Decision Log - v0.3.180 Adopt Plan and Doctor Receipt Cache

Date: 2026-07-06
Batch: v0.3.180.
Anchor: v0.3.179 public release.

## Problem

The basoon v0.3.179 revalidation confirmed that the new progress output exposed real bottlenecks:

- `object-storage-adopt-existing --key-map` was slow in `adopt-plan`, before provider HEADs.
- `doctor --strict --progress` was slow in `mint-receipts`.

## Decisions

- **DEC-1 - Add a manifest index for adopt planning.** Batch adopt planning now builds one
  per-run `object_id -> manifest record` index instead of scanning the manifest once per object.
  First record wins, matching the old `find_manifest_record` behavior.
- **DEC-2 - Keep `find_manifest_record` unchanged.** The single-object helper remains simple for
  existing callers; only the large batch surface opts into the indexed path.
- **DEC-3 - Cache doctor file evidence per run.** `Doctor` now caches file SHA-256,
  parsed zettel frontmatter, and BOM checks during one run.
- **DEC-4 - Preserve diagnostics and outputs.** The patch changes lookup strategy only. Command
  arguments, progress lines, JSON fields, receipt formats, and diagnostic codes remain
  unchanged.
- **DEC-5 - Add regression tests for the performance shape.** Tests fail if adopt planning calls
  `find_manifest_record` per object or if doctor rehashes/re-reads the same evidence within one
  run.

## Consequences

The next basoon revalidation should rerun:

```bash
archive object-storage-adopt-existing <archive-root> ... --key-map <map.jsonl> --approve --progress --format json
archive doctor <archive-root> --strict --progress --format json
```

If either stage is still slow, the last progress lines should now point to a remaining bottleneck
other than the pre-v0.3.180 manifest lookup pattern or same-run receipt evidence re-read pattern.
