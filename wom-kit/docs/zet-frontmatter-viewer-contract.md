# zet Frontmatter Viewer Contract

Status: v0.4.14 complete-document WOM-safe view and bounded-source paging

Canonical WOM zets are Markdown files with YAML frontmatter. That frontmatter is
part of the storage format, not the human document body.

## Storage Format

The `---` frontmatter fence is allowed and expected in canonical zets. It stores
metadata such as:

- `id`
- `title`
- `kind`
- `facets`
- `provenance`
- `edges`
- `visibility`
- `mint` receipt references

Agents and tools must not delete this metadata just because it is visually noisy
in a raw Markdown viewer.

## Human Document View

When showing a zet to a human as a document, prefer:

```powershell
archive read-zettel <archive-root> --zettel-id <id> --section document
```

or:

```powershell
archive read-zettel <archive-root> --path zettels/example.md --section document
```

Text output is a human display surface. In `document` mode it prints only the
body and omits both raw frontmatter fences and the CLI metadata header. For any
unpaged body-bearing text read (`body`, `document`, or `all`), the characters
printed to the terminal are a display-only WOM-safe Markdown projection: Korean
range tildes and unmatched `~~` or `**` cannot accidentally open GFM markup,
while completed intentional markup and code remain unchanged.

JSON output keeps a small machine-readable envelope:

```json
{
  "section": "document",
  "viewer_mode": "human_document",
  "frontmatter_hidden": true,
  "raw_frontmatter_delimiters_echoed": false,
  "display": {
    "profile": "wom_safe_markdown",
    "display_only": true,
    "canonical_source_unchanged": true,
    "source_body_available_via": "section=body"
  }
}
```

This lets a future viewer/editor show metadata in a folded side panel while the
main reading pane stays body-first.

## Bounded Body Reading

Large zet bodies can be read in bounded JSON pages without changing the default
full-body behavior:

```powershell
archive read-zettel <archive-root> --zettel-id <id> --section document --body-max-chars 20000 --format json
```

The result includes `body_page.next_cursor` and a SHA-256 for the complete
decoded body. Every continuation must retain that hash:

```powershell
archive read-zettel <archive-root> --zettel-id <id> --section document --body-cursor <next> --body-max-chars 20000 --expected-body-sha256 <sha256:...> --format json
```

Offsets count Unicode code points. If the body changes between pages, the read
fails instead of joining two versions. Paging never changes canonical files.

Every request that supplies `body_max_chars` or `body_cursor` is a bounded page,
including a first page that happens to reach the end of the body. Every bounded
page returns canonical source characters rather than a display projection. Its
JSON result omits `display`, sets
`integrity.returned_body_is_display_projection` to `false`, and records:

```json
{
  "body_page": {
    "display_projection_state": "deferred_until_complete_body",
    "display_projection_reason": "page_boundary_context_incomplete"
  }
}
```

This prevents a page boundary from changing the meaning of fences, code spans,
or paired Markdown delimiters and keeps every cursor and `body_sha256` bound to
one unchanged source. A viewer may apply the same pure projection only after it
has assembled and hash-verified the complete body.

## Canonical versus display hashes

`integrity.body_sha256` always identifies the decoded canonical body.
`integrity.returned_body_sha256` identifies the actual returned body text, and
`integrity.returned_body_is_display_projection` says whether those characters
are a derived human view. When projection is active, `display` repeats both
hashes and content-free marker counts. It never includes a body excerpt, title,
or local absolute path.

Use `--section body --format json`, the service API, or MCP when a tool needs the
exact decoded canonical Markdown. Plain text CLI output is intentionally a
human display copy even when `--section body` or `--section all` is selected.
Use an unpaged `--section document` when the next surface will render Markdown
for a person without metadata. Do not project each page independently.

## Raw Markdown View

Opening the `.md` file directly may show `---` and YAML. That is the raw storage
view. It is useful for debugging, migration, and reviewer inspection, but it is
not the recommended beginner-facing document view.

## AI Guidance

When an AI assistant presents a zet to a human:

- treat frontmatter as metadata, not prose;
- lead with the body or overview;
- mention metadata only when it affects the user's decision;
- do not say the file is broken only because `---` is visible in a raw Markdown
  environment;
- use `--section document` for a body-first document read;
- treat its `display` metadata as a derived-view label, never as a canonical
  write instruction;
- use `--section body --format json`, the service API, or MCP for exact
  canonical Markdown after UTF-8 decoding;
- for a large body, use bounded JSON pages and bind every continuation to the
  first page's complete body hash;
- use `--section details` only when the user asks to inspect metadata.

## Boundary

This release does not add a web UI, editor, or Markdown renderer. It adds a
stable read-only CLI contract that a UI, editor, or AI runtime can call.
Installing the release changes no zet; both canonical paging and the safe
complete-document view occur only when the read command is invoked.
