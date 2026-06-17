# Notion Objet Link Convert

Status: v0.3.101 approval-gated embed edge conversion checkpoint
Date: 2026-06-17

`notion-objet-link-convert` is the first approved write after
`notion-objet-link-rewrite-plan`.

It does not rewrite zettel body text. In v0.3.101 it supports only
`target_mode=embed_edge`: after a human has reviewed one Notion locator
fingerprint and one manifested object id, WOM-kit can write one `embed` edge
from the zettel to that object and write a conversion receipt.

## Commands

CLI:

```text
archive notion-objet-link-convert <archive-root> --path inbox/example.md --locator-fingerprint sha256:<hex> --object-id sha256:<hex> --target-mode embed_edge --expected-occurrence-count 1 --dry-run
```

```powershell
python wom-kit\cli\archive.py notion-objet-link-convert <archive-root> `
  --path inbox/example.md `
  --locator-fingerprint sha256:<64 lowercase hex characters> `
  --object-id sha256:<64 lowercase hex characters> `
  --target-mode embed_edge `
  --expected-occurrence-count 1 `
  --approve `
  --reviewed-by person:reviewer `
  --format json
```

There is no MCP write tool for this surface.

## Required Review Inputs

The command requires:

- one zettel target, by `--path` or `--zettel-id`,
- one selected `--locator-fingerprint`,
- one selected manifested `--object-id`,
- `--target-mode embed_edge`,
- either `--dry-run` or `--approve`,
- `--reviewed-by` when approving,
- `--expected-occurrence-count` when approving.

The occurrence count is a drift guard. It must be copied from the reviewed
`notion-objet-link-rewrite-plan` output so the write blocks if the zettel
changed after review.

## What It Writes

Approved mode writes:

- one `embed` edge in the source zettel frontmatter,
- one normal `receipts/edges/*.zettel-edge.json` receipt through the existing
  `zettel-edge` gate,
- one conversion receipt under
  `receipts/objects/notion-link-conversions/`.

If any write fails partway, WOM-kit restores the touched zettel and receipt
paths.

## Privacy And Safety Boundaries

The command re-runs the read-only rewrite plan before writing and uses the
same single-edge validation path as `zettel-edge`.

It does not:

- rewrite zettel body text,
- replace provider locator text,
- call Notion or any provider API,
- start OAuth,
- read real source exports,
- read object bytes,
- create presigned URLs,
- write candidate records,
- update object manifests,
- expose an MCP write tool,
- echo provider URLs,
- echo provider locator text,
- echo zettel body text,
- echo zettel titles,
- echo frontmatter values,
- echo page titles,
- echo absolute local paths,
- echo account ids, emails, tokens, or secret values.

`target_mode=objet_ref_rewrite` remains blocked in this command. Body rewrite
needs a separate, narrower replacement guard before it should exist.

## Relationship To Other Notion Objet Tools

Use the tools in this order:

1. `notion-objet-link-index` for an archive-wide map.
2. `notion-objet-link-plan` for one zettel.
3. `notion-objet-manifest-locator-label` if the object manifest lacks the
   reviewed locator fingerprint.
4. `notion-objet-link-rewrite-plan` to validate one selected locator/object
   pair and occurrence count.
5. `notion-objet-link-convert` to approve one `embed` edge write.
6. `zettel-objet-links` after the edge exists, to inspect safe object link
   candidates.
