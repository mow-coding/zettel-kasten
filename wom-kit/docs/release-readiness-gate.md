# Release Readiness Gate

Status: local pre-release hygiene gate
Version: v0.2.53

v0.2.53 adds a small local release-readiness gate for WOM-kit.

Run it from the repository root:

```powershell
python wom-kit\tools\check_release_readiness.py
```

The gate runs the three current public-release hygiene checkers:

- `wom-kit/tools/check_public_links.py`
- `wom-kit/tools/check_korean_product_language.py`
- `wom-kit/tools/check_public_privacy.py`

It prints a compact pass/fail summary and exits with `0` only when every child checker passes.

## What It Is

This is a local pre-release convenience gate. It standardizes the public hygiene checks that were already part of the manual release loop.

It is a bridge toward future CI, status checks, and branch protection, but it is not those things yet.

## What It Is Not

The gate:

- is not CI yet,
- does not enable branch protection,
- does not replace the full release checklist,
- does not run product doctor commands,
- does not run the full unit test suite,
- does not fetch external URLs,
- does not call GitHub APIs,
- does not edit files,
- does not add product CLI or MCP behavior.

The full release checklist still includes tests, doctor checks, naming scans, privacy scans, and human review.

See [Main Branch Protection Readiness](main-branch-protection-readiness.md) for the staged path from this local gate toward future CI, required status checks, and branch protection.
