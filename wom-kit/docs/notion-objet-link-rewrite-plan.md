# Notion Objet Link Rewrite Plan

Status: v0.3.98 read-only conversion checkpoint
Date: 2026-06-17

`notion-objet-link-rewrite-plan` is the review checkpoint after
`notion-objet-link-plan`.

Use it only after a human or AI reviewer has selected:

- one `locator_fingerprint`,
- one manifested `object_id`,
- one target mode.

It validates that the selected locator still exists in the current zettel and
that the selected object is still a reviewed manifest candidate for that
locator. It does not rewrite the zettel.

## Commands

CLI:

Command shape:

```text
archive notion-objet-link-rewrite-plan <archive-root> --path inbox/example.md --locator-fingerprint sha256:<hex> --object-id sha256:<hex> --dry-run
```

```powershell
python wom-kit\cli\archive.py notion-objet-link-rewrite-plan <archive-root> `
  --path inbox/example.md `
  --locator-fingerprint sha256:<64 lowercase hex characters> `
  --object-id sha256:<64 lowercase hex characters> `
  --expected-occurrence-count 1 `
  --target-mode objet_ref_rewrite `
  --dry-run `
  --format json
```

MCP:

```text
notion_objet_link_rewrite_plan
```

Inputs:

- `archive_root`
- `path` or `zettel_id`
- `locator_fingerprint`
- `object_id`
- `target_mode`, either `objet_ref_rewrite` or `embed_edge`
- optional `expected_occurrence_count`
- `dry_run`, which must be true

## What It Checks

The planner re-runs the one-zettel Notion locator plan and then verifies the
reviewer's selection against the current archive state:

- the selected locator fingerprint is still present,
- the selected object id is still one of that locator's manifest candidates,
- the optional expected occurrence count still matches,
- the selected candidate has no object-id blockers,
- the future target mode is known.

The `expected_occurrence_count` option is a drift guard. It lets a future
approval command detect that the zettel changed after the human reviewed the
plan.

## Output Shape

The output includes:

- `target_mode`,
- safe zettel path and id summary,
- selected `locator_fingerprint`,
- selected `object_id`,
- selected `objet:sha256:<hex>` ref,
- selected locator occurrence count and safe line/field hints,
- selected manifest candidate metadata,
- an approval checklist,
- `would_change` with the future approved write shape.

The output does not include the provider locator itself.

## Privacy And Safety Boundaries

`notion-objet-link-rewrite-plan` is read-only.

It does not:

- write zettels,
- rewrite provider locators,
- write `embed` edges,
- echo provider URLs,
- echo zettel body text,
- echo frontmatter values,
- echo page titles,
- print absolute local paths,
- create presigned URLs,
- call provider APIs,
- download objects,
- upload objects,
- read object bytes,
- hash object bytes during planning,
- prove remote availability.

Redacted zettels remain blocked through the underlying one-zettel planner.

## Relationship To Other Notion Objet Tools

Use `notion-objet-link-index` first when the archive is large.

Use `notion-objet-link-plan` next on one matched zettel.

Use `notion-objet-link-rewrite-plan` only after selecting one locator/object
pair from the one-zettel plan.

If the one-zettel plan cannot find a manifest candidate because the manifest
lacks the reviewed locator fingerprint, use
`notion-objet-manifest-locator-label` first.

After a future approved conversion writes stable refs or edges, use
`zettel-objet-links` to inspect safe local-client objet link candidates.

## Future Work

A later approval-gated command can perform the actual reviewed conversion. It
should require `--approve`, `--reviewed-by`, this dry-run plan shape, and a
fresh re-run of the same checks before writing.

This release does not perform that body rewrite or edge write. The approved
manifest locator label write is a separate earlier step.
