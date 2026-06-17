# Notion Objet Link Plan

Status: v0.3.89 read-only locator bridge
Date: 2026-06-17

`notion-objet-link-plan` is the safe bridge before converting Notion provider
locators inside a zet into manifested objet references.

It exists because imported Notion text can contain provider locators such as
page mentions or embeds while `zettel-objet-links` only resolves stable content
references:

```text
sha256:<64 hex characters>
objet:sha256:<64 hex characters>
```

This command does not convert the body. It first answers:

```text
This zettel contains Notion provider locator fingerprints.
The current manifest has these reviewed object candidates for those locators.
```

## Commands

CLI:

Command shape:

```text
archive notion-objet-link-plan <archive-root> --path inbox/example.md --dry-run
```

```powershell
python wom-kit\cli\archive.py notion-objet-link-plan <archive-root> `
  --path inbox/example.md `
  --dry-run `
  --format json
```

or:

```powershell
python wom-kit\cli\archive.py notion-objet-link-plan <archive-root> `
  --zettel-id zet_20260617_example `
  --dry-run
```

MCP:

```text
notion_objet_link_plan
```

Inputs:

- `archive_root`
- `path` or `zettel_id`
- `dry_run`, which must be true
- optional `max_locators`
- optional `max_candidates`

## What It Scans

The planner scans one non-redacted zettel for Notion provider locators in
frontmatter and body text. It groups locators by opaque `sha256:` fingerprint.

It can match a locator to `objects/manifests/files.jsonl` when the manifest
already carries one of these reviewed local metadata facts:

- an exact provider locator field, which is never echoed back,
- a locator fingerprint such as `provider_locator_sha256`,
- a Notion-labeled external store location such as `notion_source_export`.

The command does not call Notion. It does not open a browser. It does not read
object bytes or derived text bodies.

## Output Shape

For each distinct locator fingerprint, output includes:

- `locator_fingerprint`,
- occurrence counts and safe position hints,
- candidate state,
- candidate `object_id`,
- redacted manifest match fields,
- safe store labels,
- objet resolver state,
- suggested `objet:sha256:<hex>` ref for later human review.

The provider locator itself is not included in output.

## Privacy And Safety Boundaries

`notion-objet-link-plan` is read-only.

It does not:

- write zettels,
- rewrite provider locators,
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

Redacted zettels are blocked and do not expose locator previews.

## Relationship To `zettel-objet-links`

Use `notion-objet-link-plan` before a zettel has stable object refs.

Use `zettel-objet-links` after reviewed `sha256:` or `objet:sha256:` refs exist.

That split keeps the dangerous provider locator layer separate from the stable
content-addressed objet layer.

## Future Work

A later approval-gated command can replace reviewed Notion provider locators
with `objet:sha256:<hex>` refs or write reviewed `embed` edges.

This release does not perform that rewrite.
