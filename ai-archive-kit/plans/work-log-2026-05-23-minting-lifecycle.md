# Work Log: v0.2.8 Minting Lifecycle

Date: 2026-05-23
Status: public-safe work log
Related release: v0.2.8

## Context

The product language has moved from legacy `promote` toward `mint-zettel`.

The intended lifecycle is:

```text
draft zet -> mint -> canonical private zet -> mint receipt -> draft snapshot
```

The implementation needed to preserve existing `promote` behavior while adding the product-facing minting path.

## Work Performed

Added service and CLI support for:

- `mint_zettel_dry_run`
- `mint_zettel`
- `archive mint-zettel --dry-run`
- `archive mint-zettel --approve --reviewed-by <id>`

Added durable minting evidence:

- canonical zettel under `zettels/`
- mint receipt under `receipts/mint/`
- exact draft snapshot under `receipts/mint/drafts/`

Added validation:

- `schemas/mint-receipt.schema.json`
- doctor validation for mint receipt paths and SHA-256 hashes
- doctor validation for canonical zettel `mint.receipt_path`
- compatibility allowance for older canonical zettels that only contain `promotion` metadata

Added MCP support:

- read-only `mint_zettel_check`
- no MCP tool for real minting

## Safety Decisions

- The original `inbox/` draft remains untouched.
- Real minting requires `--approve`.
- Real minting requires `--reviewed-by`.
- The first authority mode is `basic`.
- The older `promote` command remains available for compatibility.
- External sharing, P2P, workpack export, live Notion/Google Drive import, and full-authority agent minting remain out of scope for this release.

## Verification

Verification:

```bash
cd ai-archive-kit
python -m unittest discover -s tests
python cli/archive.py doctor examples/fake-life-archive --strict
```

Results:

```text
132 tests OK, 8 skipped
doctor: 0 errors, 0 warnings
```

## Follow-Up

Future releases can build on the mint receipt structure for:

- richer authority modes,
- scoped AI-agent harness operation,
- share/export receipts,
- workpack-based zet sharing,
- provider-aware source attachment policies.
