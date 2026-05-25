# Work Log: v0.2.32 Foreign Block Quarantine Write

Date: 2026-05-25

Branch:

```text
codex/v0.2.32-foreign-block-quarantine-write
```

## Goal

Implement the first approved local quarantine write after the v0.2.31 foreign block quarantine plan.

The write is intentionally narrow:

- create a sanitized untrusted quarantine case,
- create a quarantine write receipt,
- keep the foreign block untrusted and unimported,
- keep MCP read-only.

## Implemented

- Added service-layer validation for `foreign_block_quarantine_plan` JSON before write preview or approval.
- Added `archive quarantine-foreign-block` with `--dry-run` and `--approve --reviewed-by`.
- Added optional `--expected-case-id` and `--review-note`.
- Wrote approved quarantine cases under `quarantine/foreign-blocks/<case-id>/quarantine-case.json`.
- Wrote quarantine receipts under `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.
- Added rollback cleanup for files created before a later write failure.
- Added read-only MCP `quarantine_foreign_block_check`.
- Added CLI and MCP tests for no-write preview, approved write, blocked/hold plans, unsafe inputs, invalid JSON, path traversal, overwrite refusal, and MCP no-write behavior.
- Updated public docs and release notes.

## Explicit Non-Goals

v0.2.32 does not implement:

- foreign block import,
- foreign block trust,
- foreign attestation writes,
- minting from foreign blocks,
- anchoring,
- delegation,
- ZET transport,
- signing,
- wallet key management,
- provider sync,
- OCR,
- LLM classification,
- full-auto execution.

## Privacy

Public examples and docs use placeholder actor ids and archive-relative paths only. No raw tokens, private keys, seed phrases, provider URLs, real local paths, or private filenames should be present.

## Pre-Merge Hardening Fix

After review, v0.2.32 received narrow write-safety regression coverage:

- rollback-on-partial-write-failure for the approved quarantine write path,
- archive id mismatch blocking for quarantine plans,
- explicit neither-mode CLI blocking when neither `--dry-run` nor `--approve` is supplied,
- approved write coverage for deterministic default `case-<hash>` case ids,
- UTC `reviewed_at` timestamps for new v0.2.32 quarantine artifacts to avoid leaking local timezone offsets.

The rollback path now returns a structured failed result and removes partial files created during the attempted quarantine write. It only cleans directories that were created by the failed write attempt.
