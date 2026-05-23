# Work Log: v0.2.9 Terminology Stabilization

Date: 2026-05-23
Status: public-safe work log
Related release: v0.2.9

## Context

`v0.2.8` made `mint-zettel` real, but parts of the codebase and documentation still treated the older `promote` language as the main lifecycle word.

The goal of this batch was not a breaking rename. The intended rule was:

```text
new product-facing language = mint
existing promote behavior = legacy compatibility
existing archives must keep working
```

## Work Performed

Stabilized the current public terminology around:

- `archive mint-zettel`
- minting
- mint receipt
- draft snapshot
- `mint` frontmatter
- `minting_rules`

Kept the v0.2 compatibility surfaces:

- `archive promote`
- MCP `promotion_check`
- `promotion` frontmatter
- `promotion_rules`
- old promotion receipts under `receipts/promotion/`

Changed new archive defaults:

- `ai_write_policy.canonical_requires: human_minting`

Kept legacy archives valid:

- `human_promotion` remains accepted by doctor without warnings.

Added minting-rule precedence:

- mint dry-run uses `minting_rules` when present,
- mint dry-run falls back to legacy `promotion_rules` when needed.

Updated user-facing docs, release docs, README files, upgrade guides, package version metadata, and CLI/MCP descriptions so new users see minting as the preferred lifecycle word.

## Safety Decisions

- No public API breaking rename was performed.
- Existing archives using `human_promotion` remain valid.
- Existing promotion tests and MCP `promotion_check` remain in place.
- Deep internal variable renaming was intentionally deferred because it would increase risk without changing user behavior.
- Sharing, P2P, SNS/feed, live Notion/Google Drive API, UI, and full-authority agent minting remain out of scope.

## Verification

Verification:

```bash
cd ai-archive-kit
python -m unittest discover -s tests
python cli/archive.py doctor examples/fake-life-archive --strict
```

Results:

```text
134 tests OK, 8 skipped
doctor: 0 errors, 0 warnings
```

## Follow-Up

Future refactors can gradually rename internal helpers once the product surface is stable and test coverage is broader.

The next feature work can build on the stabilized minting language instead of spreading new `promotion` references.
