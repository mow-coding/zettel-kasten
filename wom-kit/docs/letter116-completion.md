# Letter 116 completion

Status: v0.3.309 implementation and operator guide. This document records the
source contract; external CI, exact-tag, GitHub Release, and wheel evidence
must be verified independently.

## Requirement map

| Letter 116 gap | v0.3.309 behavior |
|---|---|
| Repeated byte-identical references share one digest | Manifest v0.2 adds an optional, 1-based `occurrence_index`. Its scope is one zettel and one same-digest reference sequence, in source order. |
| A reviewed page destination may exist without a pre-existing edge | `zettel_reference` can replace one self-closing `mention-page` with a navigation-only `wom-zettel:` link after the target is revalidated. It does not create an edge. |
| A generated Notion table-of-contents placeholder remains as unknown markup | One exact `<unknown:table_of_contents/>` at the original body's first nonempty line can be removed. Generated navigation is not materialized. |
| Unsupported imported block structures are still ambiguous | Bare `callout` and `database`, plus the unsupported `unknown:` synced/transclusion/column/link-preview placeholder shapes, remain deferred and fail-closed. Existing supported synced and column wrapper normalization is unchanged. |

## Use the existing normalization lifecycle

Letter 116 adds no new command. Preview through the existing bounded plan, then
approve only its fresh digest:

```powershell
archive markup-normalization-plan <archive-root> `
  --binding-manifest <archive-relative-manifest.json> `
  --only-ready --dry-run --format json

archive markup-normalization <archive-root> `
  --binding-manifest <archive-relative-manifest.json> `
  --only-ready --expected-plan-sha256 <digest> `
  --approve --reviewed-by person:<reviewer> --format json
```

`--only-ready` does not weaken a blocker. It selects only byte changes already
classified as ready by the same plan and leaves every blocked zettel
byte-identical. Strict all-clear planning remains the default.

If an approved run is interrupted, use `markup-normalization-recovery` to
resume the exact after snapshots or roll back the exact before snapshots. Use
`markup-normalization-revert` with the ordinary receipt to restore all original
zettel bytes after a completed run.

## Same-digest occurrence selection

The v0.2 manifest keeps the existing zettel id and full-fragment SHA-256, then
optionally selects one occurrence:

```json
{
  "schema": "wom-kit/markup-reference-binding-manifest/v0.2",
  "archive_id": "<archive-id>",
  "bindings": [
    {
      "zettel_id": "zet_example",
      "tag_sha256": "<64 lowercase hex>",
      "occurrence_index": 1,
      "binding_kind": "zettel_reference",
      "binding_id": "zet_reviewed_target_a"
    },
    {
      "zettel_id": "zet_example",
      "tag_sha256": "<same 64 lowercase hex>",
      "occurrence_index": 2,
      "binding_kind": "zettel_reference",
      "binding_id": "zet_reviewed_target_b"
    }
  ]
}
```

The index is not global, not shared across different digests, and not a line
number. For each zettel, WOM numbers byte-identical reference fragments with
the same digest `1, 2, ...` in source order. When that digest occurs more than
once, v0.2 must cover the complete sequence. A missing, duplicate, mixed
indexed/unindexed, out-of-range, non-integer, stale, or unused selector blocks
without writing.

Manifest v0.1 remains readable for compatibility, but it is unique-only: an
unindexed binding may be used only when that digest occurs exactly once in the
zettel. Repeated same-digest references require v0.2 occurrence selectors.

## Reviewed navigation without an edge

`binding_kind: "zettel_reference"` is restricted to a self-closing
`mention-page`. Its `binding_id` is the reviewed target zettel id. Before both
plan and apply, WOM requires exactly one readable, schema-valid, canonical
target in the same archive. Missing, draft, archived, redacted, malformed,
wrong-archive, duplicate, unreadable, invalid-UTF-8, and self targets block.

A successful replacement uses the label `Referenced zettel` and the
navigation-only destination `wom-zettel:zet_reviewed_target`.

It does not create an edge, infer a relation type, update either zettel's
frontmatter, or claim that the destination is semantically related. When a
durable semantic relation is intended, use the separate reviewed edge workflow.
The plan and ordinary result do not echo the target id, original provider
coordinate, zettel body, or local absolute path.

## Exact generated TOC placeholder

WOM removes the literal `<unknown:table_of_contents/>` only when all of these
conditions hold in the immutable original body:

- the exact lowercase, attribute-free, self-closing bytes occur once;
- the marker is a standalone line at column zero;
- it is the first nonempty body line, after optional blank lines containing
  only ASCII spaces or tabs; and
- its line ends with LF, CRLF, or end of file, with no trailing whitespace.

Attributes, alternate case or spacing, paired tags, repetition, a later body
position, indentation, a BOM before the marker, or trailing spaces remain
unknown and block. Fenced or indented code, code spans, escaped examples,
comments, declarations, processing instructions, CDATA, raw code elements,
Markdown link destinations/titles, reference definitions, and raw HTML
contexts are protected rather than interpreted.

If another blocker exists anywhere in a zettel containing the exact marker,
the candidate body is discarded and the complete original body is restored.
The command does not inspect headings or create a list of links: generated
navigation is not materialized. This rule removes only the reviewed generated
placeholder.

## Read-only beta evidence

The canonical beta archive remained read-only during a content-free census.
It contained 139 exact, single generated TOC placeholders at the original
first nonempty body line. Whole-zettel analysis classified 114 as ready and 25
as blocked by other markup or protected-context rules. Under `--only-ready`,
the 25 blocked zettels remain byte-identical.

These counts describe the reviewed snapshot only. They are not a migration
receipt, proof of an approved write, or a promise that another archive has the
same shapes.

## Deferred structures

Letter 116 does not authorize lossy wrapper removal or pretend that a static
Markdown snapshot retains live provider behavior. Bare `callout` and
`database`, plus `unknown:synced_block`, `unknown:transclusion_reference`,
`unknown:transclusion_container`, `unknown:column_list`, `unknown:column`,
`unknown:link_preview`, and `unknown:unsupported`, remain deferred and
fail-closed because their identity or required child semantics are absent or
unverified. A future change needs a separately reviewed, lossless mapping for
nesting, indentation, attributes, identity, children, and visible content.

This deferred boundary does not remove the existing narrow support for paired
`<synced_block>` and `<synced_block_reference>` wrappers whose complete inner
snapshot is preserved, or the existing structural normalization of `<column>`
and `<columns>` wrappers.

## Safety boundaries

- no provider/network call, credential read, live Notion lookup, or objet-body
  read is performed;
- no archive migration, automatic canonical-beta write, UI change, or MCP
  writer is introduced;
- apply re-plans under the existing lock and requires the exact plan digest and
  an attributed reviewer;
- incomplete occurrence coverage and changed source or target lifecycle write
  no files;
- blocked zettels remain byte-identical under `--only-ready`;
- approved writes retain exact before/after snapshots, recovery, receipt, and
  exact-byte revert behavior; and
- release publication, tag identity, CI, wheel synchronization, and external
  installation evidence are separate completion gates.

The syntax boundary follows Notion's
[enhanced Markdown documentation](https://developers.notion.com/guides/data-apis/enhanced-markdown)
and CommonMark's rules for
[code, links, escapes, and raw HTML](https://spec.commonmark.org/0.31.2/), but
those formats do not authorize WOM to infer an edge or live provider state.
