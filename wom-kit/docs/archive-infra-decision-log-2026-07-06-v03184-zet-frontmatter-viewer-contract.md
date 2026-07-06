# Decision Log - v0.3.184 zet frontmatter viewer contract

Date: 2026-07-06

## Decision

Keep YAML frontmatter as canonical zet storage metadata, and add a separate
human document read surface through `archive read-zettel --section document`.

## Context

Real-use feedback showed that a beginner reading a canonical zet as a document
can interpret visible `---` frontmatter fences as a broken file. WOM still needs
frontmatter for ids, provenance, facets, edges, visibility, and receipt links.
The problem is therefore a storage-vs-viewer boundary, not a reason to remove
metadata.

## Consequences

- Raw `.md` files remain canonical storage records.
- `read-zettel --section document` is the recommended body-first view for human
  reading.
- Text mode prints only the body in document mode.
- JSON mode exposes `viewer_mode`, `frontmatter_hidden`, and
  `raw_frontmatter_delimiters_echoed` so future viewers and AI runtimes can make
  the same distinction.
- No web UI or editor is introduced in this patch.
