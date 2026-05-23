# AI-Assisted Onboarding And Provider Setup

Status: planning baseline
Date: 2026-05-22

This document describes the desired beginner experience:

```text
Install zettel-kasten with one command,
or ask a local AI agent to prepare zettel-kasten,
then connect local folders, GitHub, object storage, Notion, Google Drive, and other source worlds through guided setup.
```

## 1. Product Goal

The user should not need to understand the whole architecture before starting.

Target experience:

```text
User:
  zettel-kasten 사용 준비해줘.

AI:
  Checks local environment.
  Explains the setup plan.
  Asks simple questions.
  Opens provider login flows when needed.
  Creates the archive safely.
  Registers source worlds.
  Runs doctor/preflight.
  Shows what is ready.
```

The user should be able to speak naturally:

```text
내 PC의 Documents 폴더를 zettel-kasten에 적재해줘.
이 SSD 안의 사진 폴더를 source로 등록해줘.
내 Notion 워크스페이스의 이 페이지들을 지도화해줘.
내 Google Drive의 이 폴더를 바탕으로 zet 초안을 만들어줘.
이 파일을 바탕으로 zet 작성하고 민팅까지 도와줘.
이 minted zet를 공유 가능한 형태로 준비해줘.
```

The AI should translate those requests into safe archive actions.

## 2. One-Command Setup Principle

Installation should be possible through one terminal command.

The existing direction is Docker-first:

```text
one command
-> check Docker
-> prepare archive mount folder
-> create local config
-> run doctor
-> begin onboarding
```

Future public command shape may become:

```powershell
irm https://zettel-kasten.example/install.ps1 | iex
```

or:

```bash
curl -fsSL https://zettel-kasten.example/install.sh | sh
```

But the safe baseline should keep:

- dry-run,
- explicit approval,
- no silent provider login,
- no silent Docker install,
- no secret storage in project files.

## 3. AI-Assisted Setup Principle

The system should be easy for device-accessible AI tools to set up.

Examples:

- Codex,
- Claude Code,
- Antigravity,
- Cursor-like coding agents,
- other terminal-capable AI assistants.

The AI should be able to run setup commands, inspect logs, and guide the user.

Before it drafts, runs mint dry-runs, or asks for mint approval inside an existing archive, the AI should confirm runtime context:

```text
archive runtime-context <archive-root> --format json
```

For MCP clients, the equivalent read-only tool is:

```text
archive_runtime_context
```

This context check should show the archive id, archive type/scope, owner/principal summary, AI write policy, archive-relative paths, safe next actions, doctor summary, blockers, warnings, and whether local paths are redacted. It should not write files.

But the AI should not silently:

- create provider accounts,
- store tokens in committed files,
- upload source data,
- scan entire home folders,
- mint zets without approval,
- share zets externally.

## 4. Setup Wizard Stages

### Stage 1: Local Environment Check

Check:

- OS,
- shell,
- Docker or host Python availability,
- Git availability,
- GitHub CLI availability,
- disk location for archive root,
- unsafe path risks,
- existing archive files,
- existing secrets or local profiles.

### Stage 2: Archive Identity

Ask simple beginner questions:

```text
Is this archive for you personally or an organization/project?
What display name should this archive use?
Where should the local archive folder live?
```

Default:

```text
personal archive
local-first
private
```

### Stage 3: Versioned Map

Ask whether to connect GitHub:

```text
Do you want GitHub private repo sync for versioned zets, specs, source maps, and receipts?
```

If yes:

- use `gh auth login`,
- create/select repo,
- write safe Git remote config,
- do not commit secrets.

### Stage 4: Object Storage

Ask which object storage should hold large originals:

```text
local only
Cloudflare R2
Backblaze B2
AWS S3
other S3-compatible storage
```

If object storage is selected:

- use provider login/API key flow,
- store credentials in keyring/env/local profile,
- write only references in `provider-bindings.yml`,
- run upload/list dry-run,
- do not upload until approved.

### Stage 5: Source Worlds

Register source worlds:

```text
local_folder
external_ssd
github_repo
object_manifest
notion
google_drive
google_photos
external_web
```

Each source world should first be registered, then scanned in metadata-first dry-run mode.

### Stage 6: Provider Connections

Provider connections should be optional.

Possible flows:

```text
Notion
  OAuth/public connection for product use,
  personal access token or internal integration for trusted local scripts,
  export-folder fallback for no live API mode.

Google Drive
  Google Drive API OAuth for product use,
  rclone/gcloud/manual export fallback,
  exported manifest fallback for no live API mode.

GitHub
  GitHub CLI gh auth login,
  token from credential store or env var,
  private repo for versioned map.

Object storage
  S3-compatible CLI/API,
  credentials in keyring/env/local profile,
  endpoint/bucket in provider bindings.
```

### Stage 7: First Source Scan

The first source scan should be metadata-first:

- names,
- relative paths,
- provider ids,
- mime guesses,
- size,
- modified time,
- visibility hint,
- provenance hint.

It should not immediately:

- read every file body,
- summarize private data,
- upload originals,
- hash huge files without approval,
- call provider APIs repeatedly without clear scope.

### Stage 8: First zet Draft And Mint

After sources are registered, the user can say:

```text
이 자료를 바탕으로 zet 초안 만들어줘.
```

The AI should:

1. inspect allowed source references,
2. create draft in `inbox/`,
3. show the draft,
4. ask whether to mint,
5. run mint checklist,
6. mint only after approval.

## 5. Natural Language To Action Mapping

Examples:

```text
"이 폴더를 적재해줘"
-> add-source dry-run
-> scan-source dry-run
-> approval
-> source-map + receipt
```

```text
"이 파일 바탕으로 zet 만들어줘"
-> inspect source ref
-> create draft
-> link source_refs
-> ask for mint
```

```text
"민팅해줘"
-> mint-zettel dry-run/checklist
-> approval
-> canonical zet + receipt + draft snapshot
```

```text
"이 zet 공유하고 싶어"
-> future share dry-run
-> scope gate
-> trust gate
-> payload policy
-> approval
```

## 6. Provider-Aware Safety Rules

Use provider APIs as bridges, not as the source of truth.

Canonical archive identity should rely on:

- object ids,
- source refs,
- provider bindings,
- receipts,
- source maps.

Do not put secrets into:

- zets,
- public docs,
- source maps,
- receipts,
- Git commits.

Provider URLs need classification:

```text
external web URL that is the source itself
  may be recorded as an external source reference.

provider URL that merely locates a private file
  should be represented through provider/source bindings,
  not treated as canonical file identity.
```

## 7. Minimum Components For This UX

The base `zettel-kasten` system needs:

- local setup script,
- archive root,
- `archive.yml`,
- `archive-identity.yml`,
- `provider-bindings.yml`,
- `source-bindings.yml`,
- local profiles,
- keyring/env references,
- `inbox/`,
- `zettels/`,
- `objects/manifests/files.jsonl`,
- `source-maps/`,
- `receipts/`,
- `views/`,
- `workbench/`,
- `workpacks/`,
- SQLite search index,
- CLI actions,
- MCP tools,
- doctor/preflight checks,
- fake examples and tests.

## 8. Open Source Boundary

The onboarding logic, schemas, and provider connectors can be open source.

The user's real provider connections remain local:

- Notion tokens,
- Google OAuth credentials,
- GitHub tokens,
- object storage keys,
- local folder paths,
- SSD paths,
- source maps with private filenames,
- private zets.

## 9. Reference Notes

Provider setup should follow official provider documentation:

- Notion supports internal connections, personal access tokens, and public OAuth connections.
- Google Drive API represents Drive files as `files` resources and supports metadata, search, export, and permissions.
- GitHub CLI supports browser-based `gh auth login` and secure credential storage where available.
- S3-compatible object storage can use AWS CLI-compatible workflows, Cloudflare R2, Backblaze B2, or similar providers.
- rclone can be a practical CLI bridge for Google Drive and other cloud storage backends.
