# Work Log: v0.2.22 Source Intake Planner

Date: 2026-05-25

Branch: `codex/v0.2.22-source-intake-planner`

## User Intent

Add a dry-run-only planner that safely classifies a source/objet before draft creation.

The desired workflow is:

```text
profile-resolve
-> runtime-context
-> source-intake --dry-run
-> create-draft --dry-run with source_refs
-> human draft approval
-> create inbox draft
-> mint only with separate approval
```

## Decisions

- Keep WOM-kit naming stable.
- Keep `objet` as WOM product language and `object_id` as the technical manifest id.
- Add CLI `archive source-intake <archive-root> --dry-run --format json`.
- Add read-only MCP `source_intake_plan`.
- Require exactly one locator mode per source intake run.
- Return draft-ready safe refs without reading bodies, hashing, copying, uploading, importing, OCR, transcription, extraction, provider API calls, automatic draft creation, or minting.

## Implementation Notes

- Core logic lives in `wom_kit.archive_services`.
- CLI wiring lives in `wom_kit.archive_cli`.
- MCP wiring lives in `wom_kit.mcp_server`.
- Existing `objects/manifests/files.jsonl` remains the technical source of truth for manifested objets.
- Existing `source-maps/*.jsonl` can supply metadata-only item refs.
- `provider-bindings.yml` is read only to summarize object storage context.

## Safety Notes

- Dry-run writes nothing.
- Local absolute paths are redacted by default.
- Raw provider URLs, local absolute paths in refs, token-like values, and secret-like values are blocked.
- Local files outside registered source roots warn.
- `.md` and `.txt` source candidates warn because they may already be zets or text notes.
- Missing direct `object_id` / `objet_ref` manifest records block.
- MCP exposes no apply/capture/upload/sync/provider API tool.

## Verification Plan

- CLI local-path metadata-only no-write test.
- Locator exclusivity tests.
- Manifested and missing `object_id` tests.
- Source map item tests.
- Source map relative-path tests, including traversal rejection.
- Provider and AI artifact safety tests.
- Provider URL / token-like ref rejection tests.
- Object storage context tests.
- MCP no-write, allowed-root, and forced-redaction tests.
- create-draft and mint dry-run propagation tests.

## Review Follow-Up

Claude review caught a real blocker before release: the source-relative locator path called `normalize_archive_relative_path` without importing it, so `--source ... --relative-path ...` crashed with `NameError`.

The fix imports `normalize_archive_relative_path` from `wom_kit.paths` and adds regression tests for:

- successful `--relative-path` source map resolution,
- traversal rejection through `../secret.txt`,
- provider URL / email / token-like ref rejection,
- MCP redaction enforcement when a client requests `redact_local_paths: false` without the server opt-in environment variable.
