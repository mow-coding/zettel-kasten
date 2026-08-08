# Archive infrastructure decision log: Letter 115 completion

Date: 2026-08-09

## Context

A beta archive used v0.3.305-v0.3.307 to normalize almost two thousand zettels
and bind 449 reviewed media references. Real use then exposed four remaining
boundaries: paired file tags were counted as two references, self-closing page
mentions and unknown-audio placeholders were not bindable, older duplicate
active locator rows had no reversible retirement path, and safe inline shapes
inside imported tables remained blocked.

## Decision

- Hash one complete paired file fragment and bind it through one existing
  manifest row. Keep nonempty or malformed pairs fail-closed.
- Treat only self-closing `mention-page` and `unknown:audio` as reviewed binding
  candidates. Page mentions require an existing source-zettel edge; audio
  requires a manifested objet. Paired page labels and repeated identity-free
  audio placeholders remain ambiguous and block.
- Add a dedupe-only locator deactivate plan/apply pair. The human must identify
  both the weaker target and the active keeper. The exact plan binds the current
  record bytes and both opaque ids; apply re-plans under the existing lock,
  changes only the target status, snapshots the complete prior record, and
  emits a receipt compatible with exact-byte locator revert.
- Extend locator records with `inactive` while keeping inactive rows visible in
  recovery projections and ineligible for new reference binding. Older record
  and receipt schemas remain readable.
- Convert only the table-cell shapes proven lossless in a content-free canonical
  census: strict self-closing dates and balanced, allowlisted inline/span
  content. Escape pipes according to GFM. Block scripts, inputs, block markup,
  unsafe attributes or URLs, comments, unbalanced tags, and table-cell
  reference semantics. Treat Markdown code, comments/declarations, link
  targets/titles, and non-standalone or malformed table structure as protected
  source rather than guessing through it.

## Authority and safety boundary

No command infers a page edge, objet, locator keeper, or duplicate identity.
No command echoes locator values or calls a provider. Deactivation is not a
general delete/status editor: it requires a retained compatible active row and
refuses any target already linked from the zettel body. Stale bytes, ambiguous
ids, conflicting coordinates, a different occurrence anchor, an invalid
reviewer, or a changed plan all write nothing.

Locator revert trusts neither target nor snapshot paths from an otherwise
well-shaped receipt. The receipt must be a regular non-reparse file under the
locator receipt directory; its schema/action and current/snapshot record
identity are checked, canonical paths are derived, corrupt content-addressed
snapshots block forward writes, and handled publication failures restore the
pre-operation record bytes.

The release changes WOM-kit only. The beta archive is read-only verification
evidence, and no UI or MCP writer is added.

## Consequences

One reviewed binding can unlock each ordinary paired file without inventing a
two-digest manifest contract. The two new self-closing reference classes use the
same verified binding and exact-revert boundaries as existing references. Older
duplicate locators can be retired without deleting provenance or weakening the
linear receipt history. Thirty-six canonical table-shape files gain a
whole-zettel lossless conversion path, while five files with protected
Markdown, a non-standalone table context, unsupported cell semantics, or
invalid structure stay byte-preserved and blocked.

Standards references:

- https://github.github.com/gfm/#tables-extension
- https://developers.notion.com/guides/data-apis/enhanced-markdown

See `docs/letter115-completion.md` for operator commands and
`docs/releases/v0.3.308.md` for the public release summary.
