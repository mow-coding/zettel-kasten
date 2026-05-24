# WOM AI Runtime Skill And Plugin Layer

Status: v0.2.22 planning and implementation baseline

## Purpose

WOM is AI-runtime first, but AI runtimes need a safe first step before they act.

In v0.2.18, the first step is still profile resolution when the user names a target archive/profile. The next safe write step is a dry-run inbox draft preview, not minting.

The profile registry layer gives terminal-capable AI tools a read-only way to answer:

```text
Which WOM profile did the user ask for?
Is the requested profile the current/default profile or another profile?
Does the profile have an archive id, type, root, and token state?
Is direct draft writing available, or should the AI suggest token registration or delegation?
```

The runtime context layer gives terminal-capable AI tools a read-only way to answer:

```text
Which archive am I operating on?
What type of archive is it?
Who owns or operates it?
Where may drafts and zets live?
What safe actions are available?
Are there blockers before I continue?
```

## Profile Registry Commands

CLI:

```bash
archive profile-list --registry <path> --format json
archive profile-resolve --registry <path> --target <query> --format json
```

MCP:

```text
wom_profile_list
wom_profile_resolve
```

Profile resolution must happen before runtime context whenever the user names a target profile. This prevents the AI from assuming the current/default archive is correct.

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

## Draft Creation Dry-Run

CLI:

```bash
archive create-draft <archive-root> --dry-run --format json
```

MCP:

```text
create_draft_zettel with dry_run: true
```

The dry-run returns the proposed `inbox/` path, frontmatter preview, body hash, blockers, warnings, and approval replay values. It writes nothing.

Draft body hashes normalize line endings before replay. This lets an approved multi-line draft keep the same body hash across common LF and CRLF environments.

When `creation_mode` is `ai_assisted` or `ai_generated`, provenance must identify the assisting AI runtime through `assisted_by`. Generic `cli:` or `mcp:` provenance is not enough for an AI-created draft.

For profile-bound AI draft writes, normal mode requires:

```text
draft_approved_by
expected_body_sha256
```

This approval only creates an inbox draft. Minting remains a separate `mint-zet --approve --reviewed-by` step.

## Source Intake Dry-Run

Before drafting from a presentation, document, image, provider item, or AI artifact, the AI should classify the source/objet reference:

```bash
archive source-intake <archive-root> --dry-run --format json
```

MCP:

```text
source_intake_plan
```

The planner accepts exactly one locator mode, such as a local path, source map item, `objet:sha256:...`, technical `object_id`, provider object ref, or AI artifact ref. It returns `source_refs_for_draft`, `objet_status`, object storage context, content access flags, blockers, warnings, and next safe actions.

It writes nothing and does not read file bodies, calculate full hashes, copy, upload, import, OCR, transcribe, extract, call provider APIs, create drafts, or mint.

## Expected AI Runtime Flow

An AI runtime should start with:

```text
1. resolve requested WOM profile when the user names a target
2. confirm or switch target archive context
3. call runtime context with expected archive id and type
4. check ok/blockers/warnings
5. run source-intake dry-run when a source/objet/provider/AI artifact is involved
6. run create-draft dry-run with the returned safe source refs and show the proposed inbox draft
7. replay the draft only after human draft approval
8. run mint dry-run before asking for mint approval
9. use CLI approval paths for real minting
```

This keeps the AI helpful without giving it a broad mutation surface.

## Skill Template

The `templates/ai-runtime/wom-archive/SKILL.md` file is a reusable prompt-side policy for AI runtimes that support local skills.

The skill tells the AI to:

- resolve the requested profile first when the user names a target archive/profile,
- then run runtime context,
- run source-intake dry-run before drafting from source/objet material,
- use create-draft dry-run before any profile-bound draft write,
- keep paths archive-relative,
- avoid exposing local absolute paths,
- use dry-run checks before approval requests,
- avoid MCP apply assumptions,
- respect `WOM`, `zet`, and `ZET` naming.

## Plugin Boundary

The plugin layer should expose read and preview tools first.

Allowed v0.2.18 direction:

- profile list and profile resolve,
- runtime context,
- source intake dry-run,
- doctor,
- list/read zets,
- create-draft dry-run and approved inbox draft writes,
- dry-run mint checks,
- safe HTML dry-run through CLI,
- onboarding and source planning,
- ownership transfer check.

Not allowed in this layer yet:

- real minting through MCP,
- profile registration or token registration through MCP,
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

This layer adds optional frontmatter fields for draft provenance and replay-safe draft creation. It does not change product philosophy or naming rules.

It is a safe confirmation layer above the existing CLI/MCP runtime.
