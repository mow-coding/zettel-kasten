# Work Log: v0.2.18 Draft Provenance

Date: 2026-05-24

Branch: `codex/v0.2.18-draft-provenance`

## Goal

Implement profile-aware draft zet creation dry-run so AI runtimes can preview an inbox draft before writing, then replay the approved draft safely without treating draft approval as mint approval.

## Implementation Notes

- Extended `create-draft` with `--dry-run`, expected archive id/type checks, profile context, provenance refs, deterministic draft id/timestamp, body hash replay, and draft approval fields.
- Kept existing `create-draft` behavior compatible when new flags are omitted.
- Added write gates for profile-bound AI drafts:
  - require `draft-approved-by`,
  - require `expected-body-sha256`,
  - block expected body hash mismatch.
- Kept writes constrained to `inbox/`.
- Added MCP dry-run and profile-aware inputs to `create_draft_zettel`.
- Preserved mint receipt propagation for draft `source_refs`, `provenance.derived_from`, and `local_ai_sessions`.
- Updated frontmatter schema with optional draft provenance fields.
- After review, normalized draft body hashes across LF/CRLF line endings so approved replay works across common operating-system text conventions.
- After review, required AI-assisted and AI-generated drafts to identify the assisting AI runtime through `assisted_by`.
- After review, blocked empty/whitespace-only draft bodies and malformed deterministic `created_at` replay values.

## Safety Notes

- Dry-run writes no files.
- Unsafe local absolute paths and provider storage locators are blocked in draft bodies and draft provenance refs.
- Secret-like draft values are blocked.
- AI-assisted and AI-generated draft provenance must identify the assisting runtime.
- Body hash replay is line-ending-normalized before comparison.
- Natural-language "upload" style requests map to inbox draft preview/write, not canonical minting.
- MCP still has no real mint tool.

## Verification Plan

- Unit tests for CLI dry-run, replay write, archive mismatch, type mismatch, hash mismatch, unsafe refs, provenance preservation, and mint propagation.
- MCP tests for dry-run no-write and approved profile-bound write.
- Full unittest discovery.
- Strict doctor on fake archive.
- `git diff --check`.
- naming and privacy scans.
