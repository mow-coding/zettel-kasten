# Archive infrastructure decision log: Letter 116 completion

Date: 2026-08-09

Status: v0.3.309 implementation and release-scope decision. This record does
not replace independent CI, exact-tag, GitHub Release, or wheel evidence.

## Context

Letter 115 made one complete reference fragment digest-bindable, but two
byte-identical fragments inside one zettel still shared the same manifest key.
Real reviewed page navigation could also lack a previously authored edge, and
Notion export remnants included an exact generated
`<unknown:table_of_contents/>` placeholder. Separately, bare `callout` and
`database` plus unsupported `unknown:` synced/transclusion/column/link-preview
placeholders did not carry enough verified identity or child semantics for a
lossless Markdown mapping. Existing narrow paired synced-wrapper and structural
column-wrapper support was not part of that gap.

## Decision

- Adopt binding-manifest v0.2 with an optional 1-based `occurrence_index` scoped
  to one zettel's same-digest source-order sequence. Require complete indexed
  coverage when the digest repeats. Reject mixed keyed/unkeyed, duplicate,
  incomplete, out-of-range, invalid, stale, or unused selectors.
- Continue reading manifest v0.1 only at its original unique-only boundary. It
  cannot select one member of a repeated same-digest sequence.
- Add `zettel_reference` as a reviewed navigation-only binding for a
  self-closing `mention-page`. Revalidate one unique, readable, schema-valid,
  canonical target in the same archive before plan and apply. Render a
  `wom-zettel:` link, but do not create an edge or infer a relation.
- Remove one exact attribute-free `<unknown:table_of_contents/>` only when it is
  the immutable original body's first nonempty standalone line and occurs once.
  Do not parse headings or materialize generated navigation. If any blocker
  remains, restore the complete original body.
- Defer bare `callout` and `database`, plus `unknown:synced_block`,
  `unknown:transclusion_reference`, `unknown:transclusion_container`,
  `unknown:column_list`, `unknown:column`, `unknown:link_preview`, and
  `unknown:unsupported`. Their identity or required child semantics are absent
  or unverified, so keep them fail-closed instead of flattening nesting,
  changing indentation, or claiming that live provider behavior survives.
  Preserve the existing support for paired `<synced_block>` /
  `<synced_block_reference>` inner snapshots and structural `<column>` /
  `<columns>` wrappers.

## Authority and safety boundary

The binding manifest is human-reviewed evidence, not permission to guess a
target. An occurrence number is local to one zettel and one exact digest; it is
not a global ordinal or a substitute for the digest. `zettel_reference` is not
a typed relation, reciprocal edge, import, or target mutation. TOC removal is
not a navigation generator and does not prove that the remaining headings form
a usable table of contents.

All changes stay inside the existing markup lifecycle: bounded content-free
plan, exact digest approval, attributed reviewer, fresh re-plan under lock,
before/after snapshots, journal, recovery, receipt, and exact-byte revert.
Protected Markdown/HTML contexts, incomplete occurrence coverage, an invalid
or changed target, another unknown semantic tag, or any other blocker write
nothing for that zettel. `--only-ready` can select unrelated ready zettels but
does not weaken those blockers.

No provider/network call, credential read, object-body read, archive migration,
automatic canonical-beta write, MCP writer, or UI behavior is added.

## Evidence and consequences

A read-only, content-free census of the canonical beta snapshot found 139 exact
single TOC placeholders at the original first nonempty body line: 114
whole-zettel ready and 25 blocked by other markup or protected-context rules.
The archive was not modified. These counts are snapshot evidence, not an apply
receipt or external release evidence.

Repeated references can now receive distinct reviewed destinations without
weakening fragment identity. A direct reviewed page link can be preserved
without fabricating a semantic edge. Exact generated TOC remnants can be
removed without pretending to rebuild navigation. Rich block structures remain
visible as explicit deferred work rather than being silently flattened.

Standards references:

- https://developers.notion.com/guides/data-apis/enhanced-markdown
- https://spec.commonmark.org/0.31.2/

See `docs/letter116-completion.md` for the operator boundary and
`docs/releases/v0.3.309.md` for the public release summary.
