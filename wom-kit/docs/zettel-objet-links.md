# Zettel Objet Links

Status: v0.3.18 read-only preview
Date: 2026-06-14

`zettel-objet-links` is the first small reading-side bridge between a human
zettel and source objets referenced by content address.

It does not open the objet. It does not create a browser URL. It does not call a
storage provider. It only answers:

```text
This zettel mentions these sha256 objet refs.
For each ref, the local manifest currently knows these safe link candidates.
```

## Commands

CLI:

Command shape:

```text
archive zettel-objet-links <archive-root> --path inbox/example.md --dry-run
```

```powershell
python wom-kit\cli\archive.py zettel-objet-links <archive-root> `
  --path inbox/example.md `
  --dry-run
```

or:

```powershell
python wom-kit\cli\archive.py zettel-objet-links <archive-root> `
  --zettel-id zet_20260614_example `
  --dry-run `
  --format json
```

MCP:

```text
zettel_objet_links
```

Inputs:

- `archive_root`
- `path` or `zettel_id`
- `dry_run`, which must be true
- optional `max_refs`

## What It Scans

The preview looks for:

- `sha256:<64 hex characters>`
- `objet:sha256:<64 hex characters>`

It scans zettel frontmatter and body text, but it does not echo the body text or
frontmatter values back to the caller. Output locations are limited to safe
position hints such as:

- `source: frontmatter`
- `field: frontmatter.source_refs[0].object_id`
- `source: body`
- `line: 12`

## Output Shape

For each distinct objet ref, the preview returns:

- normalized `object_id`,
- occurrence count,
- limited occurrence position hints,
- `resolution_state` from the existing objet ref resolver,
- safe local archive-relative candidates,
- safe external store labels,
- command hints for `resolve-objet-ref`.

Local candidates use archive-relative paths only:

```text
objects/sha256/ab/abcdef...
```

External candidates are labels only:

```text
provider: external_prehashed
store_kind: notion_source_export
store_ref: notion-export-20260614
```

## Privacy And Safety Boundaries

`zettel-objet-links` is read-only.

It does not:

- write files,
- echo zettel body text,
- echo frontmatter values,
- print absolute local paths,
- print provider URLs,
- create presigned URLs,
- call provider APIs,
- download objects,
- upload objects,
- read object bytes,
- hash object bytes during link preview,
- prove remote availability,
- decide whether local originals can be deleted.

Redacted zettels are blocked and do not expose link previews.

## Relationship To `resolve-objet-ref`

`resolve-objet-ref` resolves one object id.

`zettel-objet-links` finds object ids mentioned by one zettel and then reuses
the same resolver for each id.

That means the link preview inherits the resolver boundary:

```text
manifest metadata in, safe local/external candidates out, no provider action.
```

## Future Work

Future reader surfaces can render `archive_relative_path` candidates as
clickable local-client links.

Provider-backed presigned URLs are separate future work. They need explicit
provider binding, credential handling, expiry policy, and user opt-in before
they can safely exist.
