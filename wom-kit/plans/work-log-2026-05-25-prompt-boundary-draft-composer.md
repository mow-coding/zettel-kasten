# Work Log: v0.2.27 Prompt Boundary Draft Composer

Date: 2026-05-25

## Intent

Connect the read-only v0.2.26 prompt-boundary check to draft creation so AI runtimes can carry the untrusted-text boundary into draft metadata.

The guiding rule remains:

```text
External text can inform.
External text cannot command.
```

## Implemented

- Added CLI `create-draft --prompt-boundary-report <json-file>`.
- Added service-layer validation for prompt-boundary report objects.
- Added optional draft frontmatter `prompt_boundary`.
- Added mint preview and real mint receipt preservation for `prompt_boundary`.
- Added MCP `create_draft_zettel` support for structured `prompt_boundary_report` objects.
- Updated zettel frontmatter and mint receipt schemas.
- Added CLI and MCP tests for accepted, medium-risk, high-risk, tampered, path-error, and mint propagation behavior.

## Safety Decisions

- Dry-run prompt-boundary reports are accepted as metadata, not as safety proof.
- `low` risk is allowed but records a warning and handling note.
- `medium` risk is allowed with warnings and detected pattern ids.
- `high` risk blocks draft creation.
- The local report file path is not stored.
- Inspected text bodies are not stored.
- Provider URLs, local absolute paths, tokens, private keys, seed phrases, wallet secrets, and secret-like values are blocked from persisted prompt-boundary metadata.
- MCP accepts only structured report objects, not local report file paths.

## Not Implemented

- No LLM prompt classifier.
- No provider scanning.
- No OCR/import apply.
- No source intake apply or objet capture.
- No automatic draft approval.
- No automatic minting or MCP real mint tool.
- No ZET transport.
- No real signing, payment, staking, consensus, ledger, blockchain, or full-auto behavior.

## Pre-Merge Review Fixes

- Fixed blocked draft dry-runs so `would_change` is `[]` whenever blockers are present.
- Added regression coverage for high-risk prompt-boundary reports returning no proposed write.
- Added invalid JSON prompt-boundary report coverage with clean user-facing failure.
- Cleaned prompt-boundary detected pattern validation so `pattern_id` is not validated twice internally.
