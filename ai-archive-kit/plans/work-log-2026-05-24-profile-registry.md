# Work Log: v0.2.17 WOM Profile Registry Dry-Run

Date: 2026-05-24

Status: public-safe work log

## Context

The user requested a v0.2.17 implementation on branch `codex/v0.2.17-profile-registry`.

The request was to add a read-only profile registry layer before runtime-context and draft creation so an AI runtime does not assume the current/default archive is the target when the user names another profile.

## Decision

Add two CLI commands:

```text
archive profile-list --registry <path> --format json
archive profile-resolve --registry <path> --target <query> --format json
```

Add two read-only MCP tools:

```text
wom_profile_list
wom_profile_resolve
```

## Behavior

- Profile id, label, and alias matching are exact.
- Profile matching normalizes Unicode text to NFC and removes zero-width boundary markers.
- Profile matching is case-insensitive after normalization.
- Ambiguous matches return `resolution_state: ambiguous`.
- Missing targets return `resolution_state: not_found`.
- Missing tokens return `resolution_state: token_missing`.
- Missing tokens do not erase profile identity resolution, but direct write availability is false.
- Unsupported registry versions are blockers.
- Duplicate `profile_id` values are blockers.
- Raw token-like fields are blockers; registries may carry token metadata only.
- Local paths are redacted by default.
- MCP ignores `redact_local_paths: false` unless `AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1` is set.

## Non-Goals Preserved

This batch does not implement:

- profile registration,
- token storage,
- create-draft dry-run,
- provider API sync,
- UI,
- real minting through MCP,
- MCP write/register/apply tools,
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
- `UPGRADE.md`
- `UPGRADE.ko.md`
- `VERSIONING.md`
- `README.md`
- `README.ko.md`
- `CITATION.cff`
- `ai-archive-kit/README.md`
- `ai-archive-kit/mcp/README.md`
- `ai-archive-kit/docs/wom-ai-runtime-skill-plugin-layer.md`
- `ai-archive-kit/docs/new-user-flow.md`
- `ai-archive-kit/docs/ai-assisted-onboarding-and-provider-setup.md`
- `ai-archive-kit/docs/public-documentation-map.md`
- `ai-archive-kit/docs/public-documentation-map.ko.md`
- `ai-archive-kit/docs/releases/v0.2.17.md`
- `ai-archive-kit/docs/wom-profile-registry.md`
- `ai-archive-kit/templates/profiles/wom-profiles.example.yml`
- `ai-archive-kit/templates/ai-runtime/wom-archive/SKILL.md`
- `ai-archive-kit/plans/work-log-2026-05-24-profile-registry.md`

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

Claude review identified three safety/quality issues before release:

- visually identical Korean labels or aliases could fail across NFC/NFD Unicode forms,
- unsupported registry versions passed in non-strict mode,
- raw token-like fields inside `token` metadata were not detected.

All three were fixed before release. The reader now normalizes profile lookup text, blocks registry version drift, blocks duplicate profile ids, and blocks raw token-like fields such as `value`, `secret`, `password`, and `api_key`.
