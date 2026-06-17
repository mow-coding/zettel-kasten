# 2026-06-17 - v0.3.98 Notion Objet Link Rewrite Plan

## Context

The user asked to continue work that does not require more real-use feedback
after cleaning and checking the public privacy surface.

The safe remaining Phase 3 Notion thread was not the actual locator rewrite.
The missing step was a dry-run checkpoint that can validate one reviewed
locator/object selection before any future write command exists.

## Decision

Add a read-only `notion-objet-link-rewrite-plan`.

Despite the name, the command does not rewrite zettel body text and does not
write edges. It validates a selected `locator_fingerprint`, selected
`object_id`, target mode, and optional occurrence-count drift guard, then
returns an approval checklist plus a `would_change` preview.

## Implementation

Changed public/product files:

- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/src/wom_kit/mcp_server.py`
- `wom-kit/tests/test_cli.py`
- `wom-kit/tests/test_mcp_server.py`
- `wom-kit/tests/test_capability_matrix_docs.py`
- `wom-kit/docs/notion-objet-link-rewrite-plan.md`
- `wom-kit/docs/capability-matrix.md`
- `wom-kit/docs/public-documentation-map.md`
- `wom-kit/docs/public-documentation-map.ko.md`
- `wom-kit/docs/releases/v0.3.98.md`
- `README.md`
- `CHANGELOG.md`
- `wom-kit/README.md`
- `wom-kit/pyproject.toml`
- `wom-kit/src/wom_kit/__init__.py`

## Safety Boundary

The new planner reuses the existing one-zettel Notion locator plan. It writes
nothing, rewrites no provider locators, writes no `embed` edges, calls no
providers, creates no provider or presigned URLs, reads no object bytes, and
does not expose provider URLs, zettel body text, frontmatter values, page
titles, absolute paths, credentials, or secrets.

The actual approved conversion remains future work.

## Verification

Verification to run before release:

- `python -m py_compile wom-kit\src\wom_kit\archive_services.py wom-kit\src\wom_kit\archive_cli.py wom-kit\src\wom_kit\mcp_server.py`
- `python -m pytest wom-kit\tests\test_cli.py -k "notion_objet_link" -q`
- `python -m pytest wom-kit\tests\test_mcp_server.py -k "notion_objet_link_rewrite_plan or list_tools" -q`
- `python -m pytest wom-kit\tests\test_capability_matrix_docs.py -q`
- `python -m pytest wom-kit\tests\test_release_readiness.py -q`
- `python wom-kit\tools\check_public_privacy.py --repo-root .`
- `python wom-kit\tools\check_release_readiness.py --repo-root .`
- `python "$env:USERPROFILE\.zettel-kasten-private-guard\scan_public_surface.py" --repo-root . --mode tree`
- `python wom-kit\cli\archive.py version --format json`
- `git diff --check`
