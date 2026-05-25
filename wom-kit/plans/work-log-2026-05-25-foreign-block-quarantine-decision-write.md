# Work Log: v0.2.35 Foreign Block Quarantine Decision Write

Date: 2026-05-25

## Intent

Add the first approved local write after the v0.2.34 quarantine decision preview.

The user wanted a minimal layer that can record an operator-reviewed quarantine decision without granting trust, importing a foreign block, writing attestations, minting, anchoring, delegation, signing, provider calls, or ZET transport.

## Implementation

- Added `archive record-quarantine-decision`.
- Added dry-run mode that writes nothing and returns the two archive-relative files approve mode would create.
- Added approve mode gated by `--approve --reviewed-by`.
- Added `--expected-case-id`, `--expected-decision`, and `--review-note`.
- Added validation for saved decision previews as untrusted input.
- Added current-state replay checks that re-read the quarantine case and matching quarantine write receipt before writing.
- Added exclusive file creation and rollback if the receipt write fails after the decision file is created.
- Added read-only MCP `record_quarantine_decision_check`.
- Added tests for dry-run, approve, mode guards, mismatch blockers, stale/tampered preview blockers, overwrite refusal, rollback, decision values, unsafe input redaction, and MCP no-write behavior.

## Boundaries

The approved command writes exactly:

```text
quarantine/foreign-blocks/<case-id>/quarantine-decision.json
receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json
```

It does not trust, import, attest, mint, anchor, delegate, sign, execute, accept, apply, share, call providers, or create any MCP write surface.

## Documentation

Updated public docs, CLI/MCP docs, runtime skill guidance, changelog, upgrade/versioning files, release notes, and this work log.

## Verification Plan

- `python -m unittest discover -s wom-kit\tests`
- `python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict`
- `python -m wom_kit.archive_cli doctor wom-kit\examples\fake-life-archive --strict`
- `git diff --check`
- naming and privacy scans requested for the batch.

## Pre-Merge Fixes

Claude's pre-merge review gave v0.2.35 a GO with one required follow-up: stale runtime/test version references still pointed at `0.2.34`.

Applied fixes:

- updated `wom-kit/src/wom_kit/__init__.py` to `__version__ = "0.2.35"`,
- updated the repository-root `wom_kit/__init__.py` shim to `__version__ = "0.2.35"`,
- updated bootstrap tests to assert `0.2.35` and compare the runtime package version with `wom-kit/pyproject.toml`,
- added decision-write regression checks for UTC `Z` timestamps, expected case mismatch no-write behavior, and valid-but-changed quarantine case drift,
- replaced a guarded production assert in the decision write path with a user-facing blocker.
