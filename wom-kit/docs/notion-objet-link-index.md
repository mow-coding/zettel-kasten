# Notion Objet Link Index

Status: v0.3.96 read-only bulk locator index
Date: 2026-06-17

`notion-objet-link-index` is the archive-wide companion to
`notion-objet-link-plan`.

Use it when a large Notion import may contain many provider locators in zet
bodies, but you are not ready to rewrite zets or write durable `embed` edges.

It answers:

```text
How many non-redacted zets still contain Notion locator fingerprints?
How many of those locator rows already have manifested objet candidates?
Which zets should be reviewed one by one before any conversion?
```

## Commands

CLI:

Command shape:

```text
archive notion-objet-link-index <archive-root> --dry-run
```

```powershell
python wom-kit\cli\archive.py notion-objet-link-index <archive-root> `
  --dry-run `
  --format json
```

Optional limits:

```powershell
python wom-kit\cli\archive.py notion-objet-link-index <archive-root> `
  --dry-run `
  --max-zettels 100 `
  --max-locators-per-zettel 20 `
  --max-candidates 5
```

MCP:

```text
notion_objet_link_index
```

Inputs:

- `archive_root`
- `dry_run`, which must be true
- optional `max_zettels`
- optional `max_locators_per_zettel`
- optional `max_candidates`

## What It Scans

The index scans non-redacted zets under `zettels/` and `inbox/` for Notion
provider locators in frontmatter and body text. It groups each locator by an
opaque `sha256:` fingerprint.

It then checks `objects/manifests/files.jsonl` for reviewed manifest metadata
that can connect a locator fingerprint to a manifested object candidate.

This is still only a map. It does not decide that a locator should be replaced.

## Output Shape

The output includes:

- archive-wide counts for scanned zets, redacted zets, locator rows, and
  distinct locator fingerprints,
- counts for locator rows with and without manifest candidates,
- safe zettel summaries with archive-relative path, zet id, locator counts, and
  candidate counts,
- safe object ids and suggested `objet:sha256:<hex>` refs for later human
  review,
- next safe actions that point back to `notion-objet-link-plan` for one-zettel
  review.

The provider locator itself is not included in output.

## Privacy And Safety Boundaries

`notion-objet-link-index` is read-only.

It does not:

- write zettels,
- rewrite provider locators,
- write edges,
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

Redacted zettels are counted, but their body and frontmatter locator content is
not scanned or exposed.

## Relationship To `notion-objet-link-plan`

Use `notion-objet-link-index` first when the archive is large.

Use `notion-objet-link-plan` next on one matched zettel before any reviewed
rewrite or edge write.

This keeps the bulk discovery step separate from the high-trust conversion
step.

If the index finds locator rows but 0 manifest candidates even though Notion
source-export objects exist, use
`notion-objet-manifest-locator-label` after human review to add the missing
non-secret locator fingerprint to the chosen object manifest record.

## Current Write Path And Future Work

Approval-gated manifest locator labels now exist through
`notion-objet-manifest-locator-label`.

Approval-gated reviewed `embed` edge conversion now exists through
`notion-objet-link-convert --target-mode embed_edge`.

Body replacement remains future work. A later command can still replace
reviewed Notion provider locators with `objet:sha256:<hex>` refs after a
separate replacement guard exists.
