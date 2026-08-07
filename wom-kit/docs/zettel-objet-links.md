# Zettel Objet Links

Status: v0.3.18 read-only preview
Extended: v0.3.301 approval-gated structured link writer
Date: 2026-08-07

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
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli zettel-objet-links <archive-root> `
  --path inbox/example.md `
  --dry-run
```

or:

```powershell
$env:PYTHONPATH='wom-kit\src'; python -m wom_kit.archive_cli zettel-objet-links <archive-root> `
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

## Add A Structured Link

The read-only preview remains unchanged. v0.3.301 adds a separate CLI-only
writer for one reviewed asset entry:

```text
archive zettel-objet-link <archive-root> --zettel-id <id> \
  --object-id sha256:<64-hex> --role source --dry-run --format json

archive zettel-objet-link <archive-root> --zettel-id <id> \
  --object-id sha256:<64-hex> --role source \
  --expected-plan-sha256 <sha256:...> --approve --reviewed-by <actor> \
  --format json
```

The objet must already exist in `objects/manifests/files.jsonl`. The writer
adds one strict `assets` entry containing `object_id`, a safe role, and an
optional label. A complete SHA-256 is mandatory. Truncated hashes are not
guessed or expanded.

Before changing the zet, approval re-runs the full plan under a per-zettel
lock. The workflow stores the exact earlier bytes privately and writes an
immutable receipt. `zettel-objet-link-revert` restores those exact bytes only
while the zet still equals the recorded post-write bytes, so unrelated later
human edits cannot be overwritten. Neither command reads or echoes object
bytes.

## What It Scans

The preview looks for:

- `sha256:<64 hex characters>`
- `objet:sha256:<64 hex characters>`

It does not treat provider locators as object refs. For imported Notion page
mentions or embeds, first run `archive notion-objet-link-plan --dry-run` to
match locator fingerprints against reviewed manifest metadata without echoing
provider URLs.

It scans zettel frontmatter and body text, but it does not echo the body text or
frontmatter values back to the caller. Output locations are limited to safe
position hints such as:

- `source: frontmatter`
- `field: frontmatter.source_refs[0].object_id`
- `source: body`
- `line: 12`

## Count Scope Compared With Overview And Catalog

`zettel-objet-links.count` is the number of distinct normalized objet IDs
discovered across the valid frontmatter and body of one non-redacted zettel.
This is deliberately broader than the v0.3.292 overview and catalog
`tie_summary.referenced_objets_count`.

```text
tie_summary.referenced_objets_count
  = distinct structured frontmatter objet relationships

zettel-objet-links.count
  = distinct objet IDs discovered across valid frontmatter and body
```

The tie summary recognizes structured frontmatter sources and exact canonical
edge target fields without reading the body; catalog output therefore keeps
`body_read: false`. This link preview performs the broader read-only scan, so a
body-only objet ID can increase its count without increasing the tie summary.

The link preview deliberately performs a broader recursive token scan across
valid frontmatter plus body text. It can discover a canonical object-ID token
inside arbitrary nested edge metadata, a URL string, or a path string. Such a
discovery is a token occurrence for this link command; it does not make that
location a structured relationship target and does not increase the tie
summary.

Overview and catalog also replace malformed object-shaped or non-string direct
edge targets with the fixed `<redacted-reference>` placeholder. A target that
does not count therefore cannot leak through the neighboring edge preview.
This does not change the broader body/frontmatter scan performed by this
read-only link command.

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

`zettel-objet-links` is read-only. The singular
`zettel-objet-link` writer is CLI-only and approval-gated.

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

Redacted zettels are blocked before the frontmatter/body scan and do not expose
a count, private relationship existence, or link previews. Redacted overview
and catalog surfaces independently return zero ties, empty edges, and
`body_read: false`.

## Relationship To `resolve-objet-ref`

`resolve-objet-ref` resolves one object id.

`zettel-objet-links` finds object ids mentioned by one zettel and then reuses
the same resolver for each id.

That means the link preview inherits the resolver boundary:

```text
manifest metadata in, safe local/external candidates out, no provider action.
```

## Relationship To `notion-objet-link-plan`

`notion-objet-link-plan` is the earlier bridge for imported Notion zets whose
body still contains provider locators instead of stable content refs.

After human review adds `sha256:` or `objet:sha256:` refs, run
`zettel-objet-links` to resolve those stable refs into safe local-client
candidates.

## Future Work

Future reader surfaces can render `archive_relative_path` candidates as
clickable local-client links.

Provider-backed presigned URLs are separate future work. They need explicit
provider binding, credential handling, expiry policy, and user opt-in before
they can safely exist.
