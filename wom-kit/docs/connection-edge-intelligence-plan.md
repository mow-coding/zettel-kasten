# Connection Edge Intelligence Plan

Status: v0.3.102 read-only connection edge review summary and supersedes heuristic checkpoint
Original checkpoint: Status: v0.3.87 read-only connection edge intelligence checkpoint

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
connection-import-plan -> connection-evidence-parse-fixture -> zettel-edge-batch
```

This command adds the review intelligence layer between a candidate and a
durable edge write:

```text
candidate edge -> meaning/mechanism review -> human approval -> zettel-edge
candidate edge set -> reviewed policy -> zettel-edge-batch
```

It keeps two axes separate:

- `source_mechanism`: how the evidence appeared, such as a Notion relation,
  internal link, page mention, view snapshot, comment context, or objet embed.
  In v0.3.123 this also includes Notion containment evidence such as child
  pages, child databases, and collection views.
- `relationship_meaning`: what the relation means for the zettel-kasten.

That distinction matters because a provider mechanism is not always the human
meaning of the edge.

## Review Counters

The output separates ambiguity from review need:

- `classification_summary.ambiguous_count` counts semantic or
  medium-confidence candidates only.
- `classification_summary.human_review_required_count` counts candidate-level
  review flags such as provisional relationship meanings.
- `review_summary.durable_write_human_approval_required_count` counts every
  candidate that would still need human approval before a durable edge write.
- `review_summary.auto_writable_count` remains `0` for this read-only command.

This means `ambiguous_count: 0` does not mean the edge candidates are ready to
write. For example, a clean Notion relation can still require review because
it may fit a richer provisional meaning such as `responds_to` or `fulfills`.

For high-confidence sets, a human can now prepare a separate reviewed JSON plan
for `archive zettel-edge-batch`. That later command writes only candidates
matching the approved policy and returns the rest in `human_review_queue`.

## Current Active Meanings

The current active edge types remain conservative:

```text
material
derived
semantic
embed
mention
contains
supersedes
view_query
comment_context
```

The command maps those active edge types to meaning labels such as
`source_material`, `derived_output`, `weak_semantic`, `embedded_objet`,
`explicit_mention`, `structural_containment`, `version_replacement`,
`view_snapshot_context`, and `comment_context`.

`contains` is an active meaning for structural nesting only. It should be used
when a parent zet/page contains a child zet/page/database/view. It should not
be used as a loose topical relation, and child database evidence should not be
forced into `view_query`, `references`, `material`, or `inherited_by`.

## Version Chain Heuristic

v0.3.102 adds a narrow version-chain heuristic. When sanitized fixture metadata
contains a safe hint such as:

```json
{"relationship_hint": "version_chain"}
```

the planner can recommend:

```text
recommended_edge_type: supersedes
relationship_meaning.suggested_id: version_replacement
```

This does not read source bodies and does not write the edge. It only helps the
reviewer see that a newer plan, correction, or revision may replace an older
zet. Durable writes still require a later human-approved `zettel-edge` or
`zettel-edge-batch` step.

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
- version-chain hints can recommend `supersedes`,
- structural child page/database evidence can recommend `contains`,
- AI suggestions require human approval,
- ambiguous edges get review flags,
- vague `semantic` links should be named more specifically or dropped,
- unknown relationship shapes should be escalated as model gaps instead of
  silently mapped to the nearest existing edge type,
- provisional meanings should accumulate before becoming active edge types.
