# zet Markdown Style Guide

Status: v0.4.11 zet Markdown authoring and safe human-view checkpoint
Extended: v0.3.301 human-record integrity rules; v0.4.11 display projection

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

In v0.4.11 an unpaged `--section document` read also returns WOM-safe Markdown:

- single range tildes and unmatched `~~` or `**` are backslash-escaped;
- completed `~~strike~~`, completed `**bold**`, inline code, fenced code, and
  indented code are preserved;
- the canonical file and canonical body hash stay unchanged;
- `--section body` remains the exact decoded canonical body route;
- bounded pages remain canonical source pages so cursors and the complete body
  hash never mix canonical and derived text.

The result's `display` and `integrity` fields distinguish the source hash from
the returned display hash. The projection is not a new zet, repair, or write.

## Safety Boundary

The style-guide command itself is read-only and does not read zet bodies. The
separate `read-zettel --section document` command reads only the selected local
zet and derives its display copy in memory; neither command writes zets, mints
zets, or calls providers.
