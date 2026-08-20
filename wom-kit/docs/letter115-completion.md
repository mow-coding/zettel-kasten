# Letter 115 completion

Status: v0.3.308 implementation and operator guide

Current v0.4.0 override: the normalization, locator, and related compound
approval routes recorded below are historical evidence only. Approval returns
`compound_exact_human_approval_binding_required` before private reads or
mutation and writes nothing. Their read-only plans/audits remain available.

## Requirement map

| Letter 115 gap | v0.3.308 behavior |
|---|---|
| One paired `<file ...></file>` appears as two references | The complete paired fragment has one digest. One reviewed manifest row binds it to one verified manifested objet. |
| `mention-page` remains unknown | A self-closing page mention can bind to one already-reviewed source-zettel edge. A paired mention with visible inner text remains blocked. |
| `unknown:audio` follows a different path from `audio` | One self-closing identity-free tag can bind to one verified manifested objet. Two or more identity-free tags in the same zettel remain ambiguous and block. |
| Duplicate active locators cannot be retired | A dedupe-only plan names both the weaker target and the active locator to keep. Approved apply changes only the target status to `inactive`, writes an exact before snapshot and receipt, and can use the ordinary exact-byte locator revert. |
| Safe table-cell markup remains blocked | Strict self-closing Notion dates become visible text and reviewed `span` wrappers are removed while their inline content is preserved. Unsafe, block-level, unbalanced, or reference-bearing cell markup remains unchanged and blocks. |

## Reference-binding workflow

Run the plan first. `--only-ready` is optional and does not weaken any blocker;
it only allows unrelated ready zettels to proceed while blocked zettels remain
byte-identical.

```powershell
archive markup-normalization-plan <archive-root> `
  --binding-manifest <archive-relative-manifest.json> `
  --only-ready --dry-run --format json

archive markup-normalization <archive-root> `
  --binding-manifest <archive-relative-manifest.json> `
  --only-ready --expected-plan-sha256 <digest> `
  --approve --reviewed-by person:<reviewer> --format json
```

Each binding row still names one zettel and one exact tag digest:

```json
{"zettel_id":"zet_example","tag_sha256":"<64 lowercase hex>","binding_kind":"objet","binding_id":"sha256:<64 lowercase hex>"}
```

For a page mention, use `binding_kind: "zettel_edge"` and an existing reviewed
edge id instead. WOM does not infer the destination from the Notion URL.

The following cases remain fail-closed even when a manifest tries to bind them:

- a paired file with non-whitespace inner content;
- a self-closing file opener followed later by `</file>`;
- repeated identity-free `<unknown:audio/>` tags in one zettel;
- paired `mention-page` content whose visible label would otherwise be lost; and
- duplicate manifest rows for the same zettel and digest.

## Duplicate-locator workflow

First inspect the content-free recovery projection. It shows opaque locator ids,
types, statuses, and coordinate-presence booleans without returning locator
values.

```powershell
archive external-locator-recovery-plan <archive-root> `
  --zettel-id <zet-id> --dry-run --format json
```

Choose the weaker active row as `--locator-id` and the coordinate-complete row
as `--keep-locator-id`. Preview the exact change:

```powershell
archive external-locator-deactivate-plan <archive-root> `
  --zettel-id <zet-id> `
  --locator-id <target-locator-id> `
  --keep-locator-id <retained-locator-id> `
  --dry-run --format json
```

Approve only the fresh plan digest:

```powershell
archive external-locator-deactivate <archive-root> `
  --zettel-id <zet-id> `
  --locator-id <target-locator-id> `
  --keep-locator-id <retained-locator-id> `
  --expected-plan-sha256 <digest> `
  --approve --reviewed-by person:<reviewer> --format json
```

The command is intentionally dedupe-only. It requires one active target and one
active keeper with the same locator type, reference, and occurrence anchor. The
keeper must contain every reviewed service/account coordinate present on the
target. It refuses to deactivate a locator already referenced from the zettel
body. It never deletes or reorders a row and never rewrites a locator value.

To undo the approved change, preview and approve the existing locator revert
against the new receipt:

```powershell
archive external-locator-revert <archive-root> `
  --receipt <archive-relative-receipt.json> --dry-run --format json

archive external-locator-revert <archive-root> `
  --receipt <archive-relative-receipt.json> `
  --expected-plan-sha256 <digest> `
  --approve --reviewed-by person:<reviewer> --format json
```

## Table boundary

The canonical read-only census found 444 table fragments, including 77 target
fragments across 41 files. Whole-zettel planning leaves 36 of those files
table-normalization eligible: strict self-closing dates, safe paired spans, or
both. Five files remain
byte-preserved and blocked: two contain literal markup inside protected
Markdown contexts, one also contains a non-standalone table context elsewhere,
one retains unsupported cell markup/reference semantics, and one has invalid
table structure. Other existing structural or semantic blockers remain visible.

This boundary follows the
[GitHub Flavored Markdown table rule](https://github.github.com/gfm/#tables-extension):
cell text may contain inline content, literal pipes must be escaped, and block
elements do not belong inside a GFM table cell. Notion's official
[enhanced Markdown format](https://developers.notion.com/guides/data-apis/enhanced-markdown)
documents `mention-page` and self-closing mention syntax, but that syntax alone
does not authorize WOM to guess a local zettel relation.

## Safety boundaries

- no provider, network, credential, or live Notion lookup is performed;
- no canonical beta archive is changed by the release or its verification;
- inactive locators cannot satisfy new markup bindings;
- blocked zettels remain byte-identical under `--only-ready`;
- fenced or inline code, comments, declarations, CDATA/PI, raw code elements,
  escaped examples, Markdown link targets/titles, and non-standalone table
  contexts are not normalized;
- add, update, deactivate, and revert all revalidate under the per-zettel lock;
- locator revert accepts only validated regular receipts below
  `receipts/external-locators/`, derives its record/snapshot paths, and rolls
  the record back if receipt publication fails;
- record schema upgrades occur only when an approved locator write happens;
- existing locator records and historical receipts remain readable; and
- this release adds no MCP writer and changes no UI.
