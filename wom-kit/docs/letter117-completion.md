# Letter 117 completion

Status: v0.3.310 implementation and operator guide. This document records the
source contract; external CI, exact-tag, GitHub Release, wheel synchronization,
and fresh-install evidence must be verified independently.

Current v0.4.0 override: the normalization apply/revert/recovery approval
examples below are historical evidence only. Approval returns
`compound_exact_human_approval_binding_required` before private reads or
mutation and writes nothing; use the read-only plan/audit surfaces only.

## Requirement map

| Letter 117 gap | v0.3.310 behavior |
|---|---|
| Exact synced/transclusion placeholders contain no recoverable child snapshot | A reviewed binding-manifest v0.2 occurrence may replace the exact placeholder with one static canonical zettel or manifested objet link. WOM does not reconstruct missing children or claim live sync. |
| An empty imported database pair retains a reviewed page identity | A strict, whitespace-only paired `database` fragment may bind to one reviewed canonical zettel. WOM does not materialize a database view. |
| Imported callout and column shapes still carry display or structural meaning | Callout icon/color/indentation, unknown column boundaries, and unsupported unknown content remain byte-identical and fail closed. |
| Literal markup examples can resemble migration candidates | Quoted HTML attributes, unreviewed CommonMark raw-HTML type 6/type 7 blocks, Markdown container prefixes, and multiline reference definitions are protected as terminal literal content. |

## Use the existing normalization lifecycle

Letter 117 adds no command or schema revision. Preview through the existing
bounded plan and approve only the exact fresh digest:

```powershell
archive markup-normalization-plan <archive-root> `
  --binding-manifest <archive-relative-manifest.json> `
  --only-ready --dry-run --format json

archive markup-normalization <archive-root> `
  --binding-manifest <archive-relative-manifest.json> `
  --only-ready --expected-plan-sha256 <digest> `
  --approve --reviewed-by person:<reviewer> --format json
```

`--only-ready` selects only changes already classified as ready by the same
plan. It does not weaken a blocker. If any blocker remains in a candidate
zettel, WOM discards the complete proposed normalized body and retains the
original zettel bytes.

If an approved run is interrupted, use `markup-normalization-recovery` to
resume the exact after snapshots or roll back the exact before snapshots. Use
`markup-normalization-revert` with the completed receipt to restore all
original zettel bytes.

## Exact unknown synced/transclusion references

Only these literal fragment bytes enter the Letter 117 binding lane:

```text
<unknown:synced_block/>
<unknown:transclusion_reference/>
<unknown:transclusion_container/>
```

The tag name must be lowercase, the tag must have no attribute, the slash must
have no preceding space, and the shape must be self-closing. Surrounding line
indentation and newline style are not part of the fragment digest and remain in
place around the replacement. Alternate case, spacing, attributes, paired
opening/closing tags, or content-bearing forms block without a write.

The manifest row keeps the existing v0.2 fields: source zettel id, SHA-256 of
the exact fragment, complete 1-based `occurrence_index` authority when that
digest repeats, reviewed `binding_kind`, and reviewed `binding_id`.

- `zettel_reference` requires one unique, readable, schema-valid, canonical
  target in the same archive. Plan and apply revalidate it. The replacement is
  a static `wom-zettel:` navigation link and changes no edge or target zettel.
- `objet` requires the complete `sha256:<64 lowercase hex>` identity to exist
  in the archive's reviewed object manifest. The replacement is a static
  `wom-objet:` link and reads no object body.
- `zettel_edge` and `external_locator` are not accepted for these three shapes.

These placeholders prove neither the original provider identity nor the
presence of omitted child blocks. A reviewed binding therefore authorizes a
static reference only. It never authorizes provider lookup, live synchronization,
transclusion reconstruction, semantic edge inference, or silent deletion.

## Strict empty database reference

One paired `database` fragment is a binding candidate only when all of these
conditions hold:

- the opening tag parses to required `inline` and `url` attributes plus an
  optional `data-source-url`, with no duplicate or extra attribute;
- `inline` is exactly `true` or `false` after strict value parsing;
- `url` and an included `data-source-url` are nonempty, at most 4,096
  characters, and contain no control character;
- the inner fragment contains only whitespace; and
- a matching closing `</database>` is present.

The SHA-256 covers the complete opening tag, whitespace-only inner fragment,
and closing tag. Attribute order and exact source quoting therefore remain
part of the reviewed digest even though the supported attribute set is parsed.

`database` accepts only `binding_kind: "zettel_reference"` and reuses the same
canonical same-archive target validation. The result is a static
`wom-zettel:` link. A self-closing tag, visible inner content, missing or extra
attribute, invalid value, stale digest, objet/edge/locator binding, or changed
target lifecycle blocks and preserves the source bytes. WOM does not query the
private URL values and does not construct a database view.

## Protected literal contexts are terminal content

Markup normalization must distinguish source markup from text that merely
shows markup. v0.3.310 strengthens the whole-zettel guard when a normalizable
candidate appears in:

- single- or double-quoted raw-HTML attributes;
- unreviewed CommonMark raw-HTML type 6 or type 7 blocks, including blockquote,
  unordered-list, ordered-list, and repeated container prefixes;
- multiline-label link reference definitions;
- reference-definition destinations or titles continued onto later lines;
- the existing fenced/indented code, code span, escaped, declaration, CDATA,
  processing-instruction, raw-code-element, link destination/title, and
  reviewed raw-container contexts.

The container-prefix and reference-definition scanners have adversarial
linear-time regression coverage so deeply repeated `>`/list prefixes or many
reference definitions do not introduce a backtracking denial of service.

When this guard fires, the expected terminal result is preservation: the plan
reports `markup_protected_context_unsupported`, creates no reference candidate,
and leaves the entire zettel byte-identical. Protected-context items are not a
count of migration debt that an operator should try to force through. A future
source-span-aware parser may normalize proven-safe spans outside a literal,
but v0.3.310 does not claim that partial behavior.

## Deferred display and structure

Letter 117 does not flatten imported display or layout semantics:

- a `callout` may carry visible icon, color, nesting, and indentation meaning;
- `unknown:column_list` and `unknown:column` placeholders do not provide the
  complete child boundaries needed for a lossless tree rewrite; and
- `unknown:unsupported` does not reveal its original block type or content.

Those shapes remain unchanged and block. Existing narrow support for complete
paired `<synced_block>` / `<synced_block_reference>` inner snapshots and
reviewed `<column>` / `<columns>` structural wrappers remains available; it is
not authority to reinterpret the unknown placeholder shapes above.

## Read-only beta evidence

A content-free census of the reviewed beta snapshot found 419 exact
synced/transclusion placeholder occurrences across 165 zettels. Nine protected
occurrences in nine zettels are terminal literals, leaving a maximum reviewed
binding lane of 410 occurrences across 156 zettels before manifest authority
and all other whole-zettel blockers are evaluated.

The distinction matters: 419/165 is raw exact-shape presence, while 410/156 is
only an upper bound on occurrences that may be reviewed for a static binding.
Neither count is a ready-item count, approved binding set, apply receipt,
migration result, or promise that another archive has the same shapes. The
beta archive remained read-only during this census.

## Safety boundaries

- no provider/network call, credential read, live Notion lookup, or objet-body
  read is performed;
- no edge is inferred or written and no target zettel is modified;
- no transcluded child, live sync behavior, or database view is reconstructed;
- no automatic archive migration, canonical-beta write, UI change, or MCP
  writer is introduced;
- apply re-plans under the existing writer lock and requires the unchanged
  exact plan digest plus an attributed reviewer;
- malformed shape, incomplete occurrence coverage, unused authority, changed
  source/target lifecycle, a protected context, or any coexisting blocker
  writes no bytes for that zettel; and
- release publication, tag identity, CI, packaged-resource synchronization,
  wheel inspection, and fresh installation are separate completion gates.

The syntax boundary follows Notion's
[enhanced Markdown guide](https://developers.notion.com/guides/data-apis/enhanced-markdown),
[Markdown-content guide](https://developers.notion.com/guides/data-apis/working-with-markdown-content),
and [block reference](https://developers.notion.com/reference/block), plus
[CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) and the
[GFM raw-HTML rules](https://github.github.io/gfm/#raw-html). These standards
define syntax; they do not grant WOM authority to infer private identity or
live provider state.
