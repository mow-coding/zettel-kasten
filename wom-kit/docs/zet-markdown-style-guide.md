# zet Markdown Style Guide

Status: v0.4.14 zet Markdown authoring and complete-document display boundary
Extended: v0.3.301 human-record integrity rules; v0.4.11 display projection;
v0.4.14 bounded-page deferral

WOM zets are Markdown-compatible today. That is useful for authoring and import
compatibility, but it means AI writers must avoid punctuation that Markdown
renderers can misread.

## Command

```powershell
archive zet-markdown-style-guide <archive-root> --topic range_tilde --dry-run --format json
```

Aliases:

```text
zet-style-guide
zettel-markdown-style-guide
```

## Range Tilde Rule

When a tilde means "from A to B", write one tilde with a space on both sides:

```markdown
A ~ B
2026-06-01 ~ 2026-06-22
v0.3.67 ~ v0.3.72
```

Do not use these forms for ranges:

```markdown
A~~B
A ~~ B
A~B
```

GFM can treat tilde delimiter runs as strikethrough. In WOM zet authoring,
`~~text~~` is reserved for intentional strikethrough only. Existing Korean
range forms such as `3~5` and `서울~부산` remain valid canonical prose; a human
document view escapes their display copy automatically in v0.4.11.

An incomplete `**` run can also make a Markdown surface emphasize unintended
later text. Completed `**bold**` remains intentional markup. An unmatched
`**` is escaped only in the display copy.

## AI Authoring Contract

AI runtimes drafting or reviewing zets should follow this contract:

- Range notation uses `A ~ B`.
- Double tilde is used only when the human explicitly wants Markdown
  strikethrough.
- If a literal tilde is part of code or a command, use a code span.
- If spacing would be ambiguous in prose, prefer words such as "from A to B".
- Load `authoring-conventions --dry-run` before drafting so archive-specific
  house rules are not invented from one example.
- Keep commands, plan hashes, receipt counts, and internal tool verification
  statuses out of ordinary human prose unless those operations are themselves
  the subject.
- After revising, read the complete zet again and resolve stale contradictions.
- Cite only files backed by openable archive-relative references.
- Revise an unminted draft in place. A title change is not a reason to delete
  and recreate it. `discard-draft` may be previewed, but v0.4.0 approval is
  fixed closed before private target read or mutation and deletes nothing.

`archive ai-response-concept-guide --topic all --dry-run` now includes the same
rule so the AI runtime can discover it during normal WOM concept handoff.

## Frontmatter Viewer Rule

Canonical zets may contain YAML frontmatter fenced by `---`. That frontmatter is
storage metadata, not document prose.

When a user wants to read a zet as a document, use:

```powershell
archive read-zettel <archive-root> --zettel-id <id> --section document
```

Human-facing viewers should hide frontmatter by default or show it in a folded
metadata panel. AI assistants should lead with the body or overview and mention
frontmatter only when it affects the user's decision.

Since v0.4.11 an unpaged `--section document` read returns WOM-safe Markdown.
In v0.4.14, every unpaged body-bearing CLI text read (`body`, `document`, or
`all`) uses the same human display projection, while structured JSON, service,
and MCP `body` reads retain the canonical source:

- single range tildes and unmatched `~~` or `**` are backslash-escaped;
- completed `~~strike~~`, completed `**bold**`, inline code, fenced code, and
  indented code are preserved;
- the canonical file and canonical body hash stay unchanged;
- `--section body --format json`, service, and MCP remain exact decoded
  canonical body routes;
- every request with `body_max_chars` or `body_cursor` remains a canonical
  source page, even when that page reaches the end, so cursors and the complete
  body hash never mix canonical and derived text.

The result's `display` and `integrity` fields distinguish the source hash from
the returned display hash. In v0.4.14, a bounded page omits `display` and reports
`body_page.display_projection_state: deferred_until_complete_body` with reason
`page_boundary_context_incomplete`. Assemble and hash-verify the complete body
before applying the pure display projection; never project pages independently.
The projection is not a new zet, repair, or write.

## Safety Boundary

The style-guide command itself is read-only and does not read zet bodies. The
separate `read-zettel` command reads only the selected local zet and derives a
display copy in memory for human text output; neither command writes zets,
mints zets, or calls providers. Structured body reads remain canonical.
Publishing or installing the release changes no canonical Markdown by itself.
