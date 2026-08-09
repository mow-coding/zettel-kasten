# Archive infrastructure decision log: Letter 117 completion

Date: 2026-08-09

Status: v0.3.310 implementation and release-scope decision. This record does
not replace independent CI, exact-tag, GitHub Release, packaged-resource,
wheel, or fresh-install evidence.

## Context

Letter 116 made repeated imported references individually reviewable, but
three exact unknown synced/transclusion placeholders still remained blocked
even when a human could identify a static zettel or manifested objet
destination. Empty imported database pairs similarly carried a possible page
identity but were not ordinary decorative wrappers.

Other Letter 117 shapes were different. Callouts can encode icon, color,
nesting, and indentation. Unknown column placeholders lack reliable child
boundaries. `unknown:unsupported` does not reveal its source block type or
omitted content. Literal markup examples inside raw HTML or Markdown reference
definitions also exposed whole-zettel fail-open cases if parsed as live
migration markup.

## Decision

- Reuse binding-manifest v0.2 and its complete per-zettel occurrence authority;
  do not introduce another schema or command.
- Treat only exact lowercase, attribute-free, self-closing
  `unknown:synced_block`, `unknown:transclusion_reference`, and
  `unknown:transclusion_container` fragments as reviewed reference candidates.
  Allow only `zettel_reference` or fully manifested `objet` bindings.
- Treat an empty paired `database` as a complete-fragment candidate only when
  its parsed attribute set is required `inline`/`url` plus optional
  `data-source-url`, `inline` is an exact boolean value, locator values are
  bounded and control-free, and the inner fragment is whitespace-only. Allow
  only `zettel_reference`.
- Render all four lanes as static navigation/object references. Do not create
  a graph edge, query a provider, reconstruct transcluded children, preserve
  live synchronization, or materialize a database view.
- Make any blocker atomic at the zettel-body boundary: discard the complete
  proposed body and retain the exact original bytes.
- Extend protected-literal detection across quoted HTML attributes, unreviewed
  CommonMark raw-HTML type 6/type 7 blocks, Markdown blockquote/list container
  prefixes, multiline-label reference definitions, and continued reference
  destinations/titles. Preserve the complete zettel as expected terminal
  literal content. Keep the scanners linear under adversarial repeated
  containers and definitions.
- Defer callout, unknown column-list/column, and unsupported placeholders until
  a separately reviewed lossless structure or source-recovery contract exists.
  Do not flatten or silently delete them.

## Authority and safety boundary

The binding manifest records human-reviewed static identity; it does not prove
the original provider block identity or recover omitted content. Fragment
SHA-256 plus complete v0.2 occurrence indexing remains the selection boundary.
Plan and apply revalidate canonical zettel targets or manifested objet identity
under the existing writer lock.

Surrounding indentation and line endings remain untouched. Malformed or
alternate unknown-tag spelling, a self-closing/content-bearing/malformed
database, incompatible binding kind, incomplete/unused occurrence authority,
protected context, or any other blocker writes nothing for that zettel.
Approved changes keep exact before/after snapshots, journal, recovery, receipt,
and exact-byte revert.

No provider/network call, credential read, object-body read, archive migration,
automatic canonical-beta write, MCP writer, or UI behavior is added.

## Evidence and consequences

A read-only content-free beta census distinguished 419 exact placeholder
occurrences across 165 zettels from a maximum reviewed binding lane of 410
occurrences across 156 zettels after nine protected literal occurrences were
excluded. This is candidate-shape evidence only. Binding authority and other
whole-zettel blockers still decide whether any item is ready; no archive write
was performed.

Reviewed static destinations can now replace a narrow identity-bearing import
remnant without pretending to restore dynamic provider behavior. Empty
database pairs can preserve reviewed navigation instead of being deleted.
Protected examples become an explicit terminal result rather than migration
debt. Rich display/structure gaps remain visible for a future lossless design.

Standards references:

- https://developers.notion.com/guides/data-apis/enhanced-markdown
- https://developers.notion.com/guides/data-apis/working-with-markdown-content
- https://developers.notion.com/reference/block
- https://spec.commonmark.org/0.31.2/
- https://github.github.io/gfm/#raw-html

See `docs/letter117-completion.md` for the operator boundary and
`docs/releases/v0.3.310.md` for the public source summary.
