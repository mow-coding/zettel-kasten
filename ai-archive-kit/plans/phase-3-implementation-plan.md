# Phase 3 Implementation Plan: Receipt-Based Real Promotion

Date: 2026-05-20

## Summary

Phase 3 adds the first safe real write path for canonical memory:

```text
archive promote <archive> --path <draft-path> --approve --reviewed-by person:me
```

The strategy is intentionally narrow:

- Keep `archive promote --dry-run` as the source of truth for promotion checks.
- Allow real promotion only in the CLI.
- Keep MCP limited to `promotion_check` dry-run.
- Keep workpack import, OS keyring integration, web UI, Notion migration, and CI matrix out of Phase 3.
- Preserve the original inbox draft after promotion.

## Implementation Scope

Implemented:

- Added service function `promote_zettel`.
- Reused `promote_zettel_dry_run` as the required gate before file writes.
- Added CLI flags:
  - `--approve`
  - `--reviewed-by`
  - `--allow-warnings`
- Wrote canonical zettels to `zettels/<same filename>.md`.
- Wrote receipts to `receipts/promotion/<zettel_id>.promotion.json`.
- Updated canonical frontmatter:
  - `status: canonical`
  - `updated_at`
  - `promotion.stage: promoted`
  - `promotion.reviewed_by`
  - `promotion.reviewed_at`
  - `promotion.checklist_version: zettel-promotion/v0.2`
- Preserved the inbox draft.
- Kept MCP without a real promotion tool.

## Safety Rules

Real promotion fails before writing if:

- `--approve` is missing.
- `--reviewed-by` is missing.
- dry-run reports blockers.
- dry-run reports warnings and `--allow-warnings` is missing.
- the target canonical path already exists.
- the target receipt path already exists.
- the source path is not an inbox draft.

If canonical write succeeds but receipt write fails, the command removes the canonical file it created and returns failure.

## Receipt Shape

Promotion receipts include:

```text
receipt_id
action: promote_zettel
dry_run: false
timestamp
reviewed_by
source.path
target.path
zettel.id
zettel.title
checklist
near_duplicates
warnings
result.created_paths
```

## Verification Plan

Run from the repository root:

```powershell
python ai-archive-kit\cli\archive.py doctor ai-archive-kit\examples\fake-life-archive --strict
cd ai-archive-kit
python -m unittest discover -s tests
python -m py_compile src\ai_archive_kit\archive_services.py src\ai_archive_kit\archive_cli.py src\ai_archive_kit\mcp_server.py tests\test_cli.py tests\test_mcp_server.py
cd ..
```

Expected result after implementation:

```text
fake-life-archive doctor strict passes
unit tests pass and increase from 45
MCP still exposes promotion_check only
fake archive remains unmodified by tests
```

Actual result:

```text
fake-life-archive doctor strict: 0 errors, 0 warnings
unit tests: 49 passed
py_compile checks: passed
```

## Future Work

Not included in Phase 3:

- Real workpack import.
- OS keyring integration.
- Web UI.
- Notion/cloud migration.
- CI matrix.
