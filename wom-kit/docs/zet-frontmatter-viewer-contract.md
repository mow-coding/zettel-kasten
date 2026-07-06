# zet Frontmatter Viewer Contract

Status: v0.3.184 canonical-storage versus human-document view checkpoint

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

Text output in `document` mode prints only the body. It does not print raw
frontmatter fences or the CLI metadata header.

JSON output keeps a small machine-readable envelope:

```json
{
  "section": "document",
  "viewer_mode": "human_document",
  "frontmatter_hidden": true,
  "raw_frontmatter_delimiters_echoed": false
}
```

This lets a future viewer/editor show metadata in a folded side panel while the
main reading pane stays body-first.

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
- use `--section details` only when the user asks to inspect metadata.

## Boundary

This release does not add a web UI, editor, or Markdown renderer. It adds a
stable read-only CLI contract that a UI, editor, or AI runtime can call.
