# Work Log: v0.2.16 WOM AI Runtime Context Layer

Date: 2026-05-24

Status: public-safe work log

## Context

The user requested a v0.2.16 implementation on branch `codex/v0.2.16-ai-runtime-context`.

The request was specifically to avoid working on `main`, avoid push/tag/release/commit, preserve product philosophy and naming rules, and add a read-only runtime context layer for terminal-capable AI runtimes such as Codex and Claude Code.

## Decision

Add one safe confirmation command:

```text
archive runtime-context <archive-root> --format json
```

The command returns archive identity, type/scope, principal/owner summary, AI write policy, archive-relative paths, safe actions, doctor summary, blockers, warnings, and path redaction status.

The command is read-only. It writes no files.

## MCP Decision

Add one read-only MCP tool:

```text
archive_runtime_context
```

It uses the same service behavior as the CLI command and respects existing MCP allowed roots.

No real mint/apply MCP tool was added.

## Behavior

- Expected archive id mismatch blocks.
- Expected archive type mismatch warns by default.
- Expected archive type mismatch blocks in `--strict`.
- Local absolute paths are redacted by default.
- `--no-redact-local-paths` is available for trusted local debugging.
- MCP local path disclosure stays redacted unless `AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1` is set on the MCP server and the caller explicitly disables redaction.
- Runtime context summary objects keep stable keys with `null` values instead of dropping optional fields.
- The object manifest path is included only when available.

## Non-Goals Preserved

This batch does not implement:

- create-draft dry-run,
- provider API sync,
- UI,
- real minting through MCP,
- product philosophy changes,
- naming rule changes.

## Files Changed

Implementation and tests:

- `ai-archive-kit/src/ai_archive_kit/archive_services.py`
- `ai-archive-kit/src/ai_archive_kit/archive_cli.py`
- `ai-archive-kit/src/ai_archive_kit/mcp_server.py`
- `ai-archive-kit/src/ai_archive_kit/__init__.py`
- `ai-archive-kit/pyproject.toml`
- `ai-archive-kit/tests/test_cli.py`
- `ai-archive-kit/tests/test_mcp_server.py`

Docs and templates:

- `CHANGELOG.md`
- `AUTHORS.md`
- `CITATION.cff`
- `UPGRADE.md`
- `UPGRADE.ko.md`
- `VERSIONING.md`
- `README.md`
- `README.ko.md`
- `ai-archive-kit/README.md`
- `ai-archive-kit/mcp/README.md`
- `ai-archive-kit/docs/new-user-flow.md`
- `ai-archive-kit/docs/ai-assisted-onboarding-and-provider-setup.md`
- `ai-archive-kit/docs/releases/v0.2.16.md`
- `ai-archive-kit/docs/wom-ai-runtime-skill-plugin-layer.md`
- `ai-archive-kit/templates/ai-runtime/wom-archive/SKILL.md`
- `ai-archive-kit/plans/work-log-2026-05-24-ai-runtime-context.md`

## Verification Plan

Required checks:

```text
python -m unittest discover -s ai-archive-kit\tests
python ai-archive-kit\cli\archive.py doctor ai-archive-kit\examples\fake-life-archive --strict
git diff --check
run the forbidden title-case zet and legacy phrase scan
run the forbidden mixed-case WOM scan
```

Also scan changed public files for real local paths, tokens, secrets, private filenames, and private user data.

## Review Follow-Up

Claude review identified two release-blocking issues before final publication:

- AI runtimes need stable JSON shapes, so optional `principal`, `owner`, and `ai_write_policy` keys must remain present with `null` values instead of disappearing.
- MCP callers must not be able to expose local absolute paths merely by passing `redact_local_paths: false`.

Both were fixed inside the v0.2.16 branch before release. Focused tests were added for stable summary keys, CLI local path disclosure behavior, and MCP redaction gating.
