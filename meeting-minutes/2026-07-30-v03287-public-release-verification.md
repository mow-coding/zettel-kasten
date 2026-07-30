# v0.3.287 Public Release Verification

Date: 2026-07-30

Status: public release lifecycle complete

## Exact Source

- Release: `v0.3.287`
- Exact merged/main commit:
  `e78282ea40b9efecde3d0c2c3046902a56f8f2aa`
- Main CI run: `30511473503`, all four jobs passed
- Annotated tag points to the exact merged commit
- Tag CI run: `30513766123`, all four jobs passed
  - release readiness: passed
  - Ubuntu Python 3.12: passed
  - Ubuntu Python 3.10: passed
  - Windows Python 3.12: passed

## Exact Wheel

- File: `wom_kit-0.3.287-py3-none-any.whl`
- Size: `1,204,586` bytes
- SHA-256:
  `0bb793a5a071c756366e7e55fc364534d9ae783ecb7e33134a4f7c504a55e3d4`
- Clean-wheel verification before publication:
  - package version `0.3.287`
  - 102 manifested resources
  - 117 wheel files
  - all four entrypoints
  - runtime Agent Skill lifecycle
  - onboarding preview/write
  - strict Doctor

## Public Evidence

GitHub Release:

```text
https://github.com/mow-coding/zettel-kasten/releases/tag/v0.3.287
```

The public unauthenticated release API reported:

- `draft: false`
- `prerelease: false`
- one asset with the exact wheel name and size

The wheel was then downloaded through the public browser URL without GitHub
CLI credentials into a fresh directory. Its SHA-256 exactly matched the
verified pre-publication artifact.

## Fresh Install

A new virtual environment installed only the publicly downloaded wheel and
its declared dependency.

- `archive --version` returned `archive 0.3.287`
- `archive version --format json` returned version `0.3.287`
- isolated `python -I` imported `wom_kit` version `0.3.287` from the fresh
  virtual environment's `site-packages`

An initial non-isolated `python -c` check was intentionally rejected as
evidence after it imported the older repository-root shim from the current
working directory. Repeating the check outside the repository with `-I`
proved the installed package. This is a verification-command contamination,
not a wheel defect, and reinforces the isolated-path boundary being added in
v0.3.291.

## Remaining Boundary

Engineering publication is complete. Real-use semantic confirmation remains a
separate beta-tester step and is not inferred from CI or installation evidence.
