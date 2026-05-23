# WOM AI Runtime Skill And Plugin Layer

Status: v0.2.16 planning and implementation baseline

## Purpose

WOM is AI-runtime first, but AI runtimes need a safe first step before they act.

The runtime context layer gives terminal-capable AI tools a read-only way to answer:

```text
Which archive am I operating on?
What type of archive is it?
Who owns or operates it?
Where may drafts and zets live?
What safe actions are available?
Are there blockers before I continue?
```

## Runtime Context Command

CLI:

```bash
archive runtime-context <archive-root> --format json
```

MCP:

```text
archive_runtime_context
```

The output is intentionally small and stable. It includes archive identity, archive type/scope, owner/principal summary, AI write policy, archive-relative paths, safe next actions, doctor summary, blockers, warnings, and redaction status.

Local absolute paths are redacted by default.

MCP clients must not request `redact_local_paths: false` unless trusted local debugging has been explicitly authorized. The stdio MCP server keeps local paths redacted unless `AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1` is set in the MCP server environment.

## Expected AI Runtime Flow

An AI runtime should start with:

```text
1. call runtime context
2. check ok/blockers/warnings
3. confirm expected archive id and type when known
4. create drafts only in inbox
5. run mint dry-run before asking for mint approval
6. use CLI approval paths for real minting
```

This keeps the AI helpful without giving it a broad mutation surface.

## Skill Template

The `templates/ai-runtime/wom-archive/SKILL.md` file is a reusable prompt-side policy for AI runtimes that support local skills.

The skill tells the AI to:

- run runtime context first,
- keep paths archive-relative,
- avoid exposing local absolute paths,
- use dry-run checks before approval requests,
- avoid MCP apply assumptions,
- respect `WOM`, `zet`, and `ZET` naming.

## Plugin Boundary

The plugin layer should expose read and preview tools first.

Allowed v0.2.16 direction:

- runtime context,
- doctor,
- list/read zets,
- create drafts in inbox,
- dry-run mint checks,
- safe HTML dry-run through CLI,
- onboarding and source planning,
- ownership transfer check.

Not allowed in this layer yet:

- real minting through MCP,
- provider API sync,
- source scan apply,
- source registration apply,
- real sharing,
- real transfer,
- UI automation as the canonical write path.

## Privacy Rule

Runtime context output must be safe for logs by default.

That means:

- archive-relative paths by default,
- no real local absolute paths unless explicitly requested,
- no MCP local path disclosure unless the server environment explicitly enables it,
- no provider token values,
- no source file body reads,
- no whole-disk scanning.

## Compatibility

This layer does not change archive schemas, zettel frontmatter, product philosophy, or naming rules.

It is a safe confirmation layer above the existing CLI/MCP runtime.
