# zet Markdown Style Guide

Status: v0.3.139 zet Markdown range-tilde authoring checkpoint

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

Many Markdown renderers treat double tilde as strikethrough. In WOM zet
authoring, `~~text~~` is reserved for intentional strikethrough only.

## AI Authoring Contract

AI runtimes drafting or reviewing zets should follow this contract:

- Range notation uses `A ~ B`.
- Double tilde is used only when the human explicitly wants Markdown
  strikethrough.
- If a literal tilde is part of code or a command, use a code span.
- If spacing would be ambiguous in prose, prefer words such as "from A to B".

`archive ai-response-concept-guide --topic all --dry-run` now includes the same
rule so the AI runtime can discover it during normal WOM concept handoff.

## Safety Boundary

The command is read-only. It does not read zet bodies, write zets, mint zets,
call providers, or inspect private source material.
