# Zettel Edge Write

Status: v0.3.290 active-registry endpoint type enforcement contract
Previous checkpoint: Status: v0.3.108 approval-gated zettel edge write and revert checkpoint
Rollback checkpoint: Status: v0.3.108 receipt-based edge revert checkpoint
Batch checkpoint: Status: v0.3.102 approval-gated policy batch zettel edge write ergonomics checkpoint
Original checkpoint: Status: v0.3.82 approval-gated zettel edge write checkpoint

`archive zettel-edge` is the first durable typed-edge writer for WOM-kit. It
writes exactly one reviewed edge from one source zet to one existing target zet
or manifested objet.

It is still the single-edge safety gate. `archive zettel-edge-batch` reuses
this gate for policy-approved batches, but the single command here remains the
smallest approval path.

`archive revert-edge` is the matching single-edge rollback gate. It removes one
edge by reading the original `receipts/edges/*.zettel-edge.json` receipt, writes
a new `receipts/edges/reverts/*.zettel-edge-revert.json` receipt, and preserves
the original write receipt.

It does not consume real Notion exports or candidate fixture records
automatically.

## Command

Preview:

```powershell
archive zettel-edge <archive-root> `
  --from-zettel zet_20240504_fake_lunch_thought `
  --target zet_20240505_fake_company_onboarding_insight `
  --edge-type semantic `
  --visibility private `
  --dry-run `
  --format json
```

Approve:

```powershell
archive zettel-edge <archive-root> `
  --from-zettel zet_20240504_fake_lunch_thought `
  --target zet_20240505_fake_company_onboarding_insight `
  --edge-type semantic `
  --visibility private `
  --approve `
  --reviewed-by person:reviewer `
  --format json
```

Aliases:

```text
link-zettel-edge
write-zettel-edge
```

Rollback preview:

```powershell
archive revert-edge <archive-root> `
  --receipt receipts/edges/<edge>.zettel-edge.json `
  --dry-run `
  --format json
```

Rollback approve:

```powershell
archive revert-edge <archive-root> `
  --receipt receipts/edges/<edge>.zettel-edge.json `
  --approve `
  --reviewed-by person:reviewer `
  --format json
```

Rollback alias:

```text
rollback-edge
```

## Inputs

The source must be exactly one of:

```text
--from-zettel <zet_id>
--from-path <archive-relative inbox/*.md or zettels/*.md>
```

The target must already exist as one of:

```text
zet_<id>
zet:notion:<safe-import-id>
sha256:<64 lowercase hex characters>
objet:sha256:<64 lowercase hex characters>
```

`zet_<id>` targets are resolved against the archive zettels and inbox.
`zet:notion:<safe-import-id>` is a local resolver alias for already-imported
Notion zets, such as resolving `zet:notion:ZET637` to
`zet_notion_db3_ZET0637` when exactly one archive-local zet matches. It does not
open Notion or read an export. Object targets are resolved against
`objects/manifests/files.jsonl`.

`--edge-type` must already be defined in `zettel-kasten/types.yml`.

Since v0.3.290, an active ID alone is not enough. The selected record must
declare non-empty `from` and `to` lists of safe entity-type strings. The
writer treats its source as `Zettel`, maps a resolved zet target to `Zettel`,
and maps a resolved manifested objet target to `OriginalObject`. Both endpoint
types must be permitted by the selected record before either the source file
or edge receipt can be written.

For example:

```text
continues: Zettel -> Zettel
embed: Zettel -> OriginalObject
format_variant: Zettel -> Zettel | OriginalObject
```

Therefore `continues` cannot target an objet, `embed` cannot target a zet, and
`format_variant` still accepts either reviewed target kind. Missing, malformed,
or empty endpoint lists fail closed. When an archive has its own
`zettel-kasten/types.yml`, that registry remains authoritative; the packaged
base is used only when the archive-local file is absent.

## `format_variant` Manual-Only Contract

Since v0.3.286 the base type vocabulary includes `format_variant` from
`Zettel` to `Zettel | OriginalObject`.

Use it only when a human has reviewed the two records and decided that the
target is an alternate rendition of the same intellectual content as the
source anchor. The stored source is simply the review anchor. It does not mean
that the source is older, original, or canonical.

```powershell
archive zettel-edge <archive-root> `
  --from-zettel <review-anchor-zet> `
  --target <alternate-zet-or-objet> `
  --edge-type format_variant `
  --dry-run `
  --format json
```

After checking the preview, repeat with `--approve --reviewed-by <actor>`.
Store one reviewed assertion per pair. Do not write a second reciprocal edge
automatically. WOM does not infer this relation from titles, filenames, node
categories, or existing `references` edges, and v0.3.286 performs no corpus
migration.

The policy batch writer is not an alternate approval path for this type.
`zettel-edge-batch` always places a `format_variant` row in
`human_review_queue` with `manual_single_edge_review_required`, even when the
plan lists it under `policy.auto_write_edge_types`, gives it high confidence,
and omits a human-review flag. Dry-run and approve both leave that row
unwritten. Use the single-edge command above for the reviewed pair.

If a stale archive has its own local `zettel-kasten/types.yml`, first preview
and approve `archive migrate <archive-root> --target base-link-types`.
That sync appends missing base types but never overwrites a custom same-id
record. It has no automatic revert, so review `present_not_overwritten` before
using the local definition.

## Writes

With `--approve --reviewed-by <safe-id>`, the command writes:

```text
zettels/*.md or inbox/*.md frontmatter edges +1
receipts/edges/*.zettel-edge.json
```

The source zettel `updated_at` field is also updated. The edge stores only safe
metadata:

```text
type
target
visibility
edge_id
receipt
provenance.reviewed_by
provenance.reviewed_at
```

Duplicate `type + target` edges are blocked.

## Reverts

With `archive revert-edge --approve --reviewed-by <safe-id>`, WOM-kit:

```text
zettels/*.md or inbox/*.md frontmatter edges -1
zettels/*.md or inbox/*.md frontmatter updated_at
receipts/edges/reverts/*.zettel-edge-revert.json
```

The command matches the edge by the original receipt's `edge_id` first and only
falls back to the receipt path plus `type + target` tuple for older-compatible
records. It does not delete or rewrite the original edge write receipt.

## Closed Actions

This command does not:

- parse real Notion exports,
- read comments,
- read mail,
- call providers,
- start OAuth,
- download media,
- write candidate edge records,
- update object manifests,
- delete original edge receipts,
- upload objects,
- create provider URLs,
- echo zettel body text,
- echo zettel titles,
- echo local absolute paths,
- echo page titles, comment bodies, account ids, emails, tokens, or secret
  values.

MCP does not expose a write or revert tool for this surface in v0.3.108.

For policy-level batch approval, see
[Zettel Edge Batch](zettel-edge-batch.md).
