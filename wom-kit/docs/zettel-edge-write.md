# Zettel Edge Write

Status: v0.3.88 approval-gated zettel edge write checkpoint
Original checkpoint: Status: v0.3.82 approval-gated zettel edge write checkpoint

`archive zettel-edge` is the first durable typed-edge writer for WOM-kit. It
writes exactly one reviewed edge from one source zet to one existing target zet
or manifested objet.

It is not a bulk connection importer and it does not consume real Notion
exports or candidate fixture records automatically.

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
- upload objects,
- create provider URLs,
- echo zettel body text,
- echo zettel titles,
- echo local absolute paths,
- echo page titles, comment bodies, account ids, emails, tokens, or secret
  values.

MCP does not expose a write tool for this surface in v0.3.88.
