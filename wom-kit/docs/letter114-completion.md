# Letter 114 completion

Status: v0.3.305 implementation and release evidence guide

## Incident class

A human publication request can fail silently when an AI writes an inbox file
directly, does not enter the mint workflow, creates a duplicate on retry, and
does not surface the remaining unpublished state in later sessions. The mint
command may be correct yet never run. v0.3.305 treats that silence as a system
gap rather than only an operator mistake.

## Requirement map

| Publication-completion gap | v0.3.305 behavior |
|---|---|
| AI-created draft begins without publication-critical metadata | `create-draft` blocks `ai_assisted` and `ai_generated` writes unless an explicit safe abstract and at least one non-empty facet are present. Human-owned rough drafts remain available. |
| Same-title retry creates another unminted file | A bounded frontmatter-only check blocks the AI route when the same normalized title is already in `inbox/`; human flows receive a warning. No body, title, id, or path value is returned by the check. |
| Unpublished work stays invisible across sessions | Every `ai-start-here` result includes `inbox_attention`: unpublished count, oldest safely parsed age, possible pipeline-bypass count, and publication-metadata-gap count. Markdown output renders the same line. |
| “Publish” is reported complete after only drafting | The bundled runtime skill, archive templates, authoring-conventions output, and response contract require entering `mint-zet` preview immediately and claiming completion only after approved canonical and receipt evidence exists. Blockers or a remaining approval gate must be reported in the same task. |

## Layered boundary

WOM-kit is a CLI, not an operating-system filesystem policy service. It cannot
prevent an arbitrary external program from writing directly to `inbox/`.
Instead v0.3.305 closes every boundary it controls:

1. archive and Agent Skill instructions prohibit direct writes;
2. the official AI creation route blocks incomplete metadata and same-title
   duplicates before writing;
3. session startup always exposes remaining unpublished work;
4. human-response guidance forbids a false publication-complete claim.

`inbox-pipeline-audit` remains diagnostic and grants no automatic repair,
discard, abstract generation, facet invention, or mint approval.

## Operator evidence

```text
archive ai-start-here <archive-root> --dry-run --format json
archive inbox-pipeline-audit <archive-root> --dry-run --format json
archive authoring-conventions <archive-root> --dry-run --format json
```

For a human publication request, continue through the ordinary exact draft
preview, reviewed replay, mint preview, and approved mint gates. A draft path
alone is never publication evidence.
