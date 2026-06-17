# Connection Edge Intelligence Plan

Status: v0.3.87 read-only connection edge intelligence checkpoint

`archive connection-edge-intelligence-plan` is a read-only review layer on top
of the sanitized connection fixture parser.

It does not decide final edges. It helps an AI runtime and a human reviewer see
which connection candidates are probably straightforward, which ones are
ambiguous, and which ones may need a richer relationship meaning later.

## Command

```powershell
python wom-kit\cli\archive.py connection-edge-intelligence-plan `
  wom-kit\examples\fake-life-archive `
  --evidence workbench/connection-evidence.sample.json `
  --source notion `
  --connection-kind all `
  --dry-run `
  --format json
```

Alias:

```text
connection-edge-classification-plan
```

## What It Adds

The earlier connection commands cover the mechanical path:

```text
connection-import-plan -> connection-evidence-parse-fixture -> zettel-edge
```

This command adds the review intelligence layer between a candidate and a
durable edge write:

```text
candidate edge -> meaning/mechanism review -> human approval -> zettel-edge
```

It keeps two axes separate:

- `source_mechanism`: how the evidence appeared, such as a Notion relation,
  internal link, page mention, view snapshot, comment context, or objet embed.
- `relationship_meaning`: what the relation means for the zettel-kasten.

That distinction matters because a provider mechanism is not always the human
meaning of the edge.

## Current Active Meanings

The current active edge types remain conservative:

```text
material
derived
semantic
embed
mention
view_query
comment_context
```

The command maps those active edge types to meaning labels such as
`source_material`, `derived_output`, `weak_semantic`, `embedded_objet`,
`explicit_mention`, `view_snapshot_context`, and `comment_context`.

## Provisional Meanings

The command also reports provisional meaning candidates:

```text
format_variant
responds_to
fulfills
enabling
sequence
```

These are not active durable edge types in v0.3.87. They are review labels. The
point is to collect repeated evidence under `neither_fits`-style review before
promoting too many edge types too early.

## Safety Boundary

This command reads only an archive-relative sanitized fixture JSON that already
passes the fixture parser boundary.

It does not:

- call Notion or any provider,
- start OAuth,
- read real source exports,
- read source body text,
- read derived-text bodies,
- read comment bodies,
- download media,
- call an LLM or run a multi-lens AI classifier,
- write candidate records,
- write zets,
- write edges,
- write receipts,
- update object manifests.

The output also avoids provider URLs, local absolute paths, raw export paths,
page titles, comment bodies, source body text, derived-text body text, account
ids, emails, tokens, and secret values.

## Review Rules

The command is intentionally cautious:

- edge type must be judged from edge content, not from node category,
- source mechanism and relationship meaning are separate axes,
- AI suggestions require human approval,
- ambiguous edges get review flags,
- vague `semantic` links should be named more specifically or dropped,
- provisional meanings should accumulate before becoming active edge types.
