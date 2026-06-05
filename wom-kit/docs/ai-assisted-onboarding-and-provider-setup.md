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

If the user names a target profile or archive, the AI should resolve that profile before assuming the current/default archive:

```text
archive profile-resolve --registry <registry> --target <query> --format json
```

For MCP clients, the equivalent read-only tool is:

```text
wom_profile_resolve
```

Before it drafts, runs mint dry-runs, or asks for mint approval inside an existing archive, the AI should then confirm runtime context:

```text
archive runtime-context <archive-root> --format json
```

For MCP clients, the equivalent read-only tool is:

```text
archive_runtime_context
```

This context check should show the archive id, archive type/scope, owner/principal summary, AI write policy, archive-relative paths, safe next actions, doctor summary, blockers, warnings, and whether local paths are redacted. It should not write files.

Before a profile-bound AI draft write, the AI should run a draft creation dry-run:

```text
archive create-draft <archive-root> --dry-run --expected-archive-id <id> --expected-type <type> --profile-id <profile-id> --format json
```

The dry-run shows the proposed `inbox/` path, frontmatter preview, body hash, and replay values. It writes nothing. A later approved draft write must replay the expected body hash and include `draft-approved-by`; that approval is only for inbox draft creation, not minting.

Before planning a GitHub repository for a WOM profile, the AI should run:

```text
archive github-repo <archive-root> --dry-run --profile-id <profile-id> --profile-slug <ascii-slug> --github-owner <owner> --github-account-ref <safe-ref> --format json
```

The v0.2.20 planner proposes a private `zettel-kasten-<profile_slug>` repository, provider binding metadata, local profile hints, a setup receipt preview, and manual steps. Dry-run writes nothing. Approved mode writes only local metadata and a receipt; it still does not create a GitHub repository, start OAuth, call GitHub APIs, run `gh`, configure remotes, push, or sync.

Before planning object storage for WOM objets, the AI should run:

```text
archive object-storage <archive-root> --dry-run --provider <provider> --profile-id <profile-id> --profile-slug <ascii-slug> --storage-account-ref <safe-ref> --format json
```

The v0.2.21 planner proposes a private bucket/container such as `zettel-kasten-<normalized-profile-slug>-objets`, an `archives/<archive_id>/objets/` prefix, provider binding metadata, local profile hints, a setup receipt preview, an objet storage policy preview, and manual steps. Dry-run writes nothing. Approved mode writes only local metadata and a receipt; it still does not create buckets, start OAuth, call provider APIs, upload, sync, copy, hash, or import source files.

But the AI should not silently:

- create provider accounts,
- store tokens in committed files,
- upload source data,
- scan entire home folders,
- mint zets without approval,
- share zets externally.

## 4. Setup Wizard Stages

### Stage 0: First Personal WOM Setup Shape

For a first personal WOM archive, the AI should be directive before it is creative.
It should not ask the user to freely choose repository names, invent example
memories, or create a filled sample archive. It should first run a short
archive-shaping conversation and then show the canonical setup path.

Ask:

```text
What part of your life or work should WOM help with first?
Which source materials should be handled first: PDFs, chats, screenshots, notes, videos, docs, or something else?
Should this feel more like a private memory room, project workbench, research notebook, or evidence vault?
What must stay out of Git?
Do you want a tiny first test or a broader empty structure?
```

Then show the canonical first-use defaults:

```text
profile_slug:        username
GitHub repo:         zettel-kasten-<profile_slug>              [enforced prefix/default]
local archive root:  C:\Users\<user>\zettel-kasten-<profile_slug> [recommended default]
local objet store:   C:\Users\<user>\zettel-kasten-<profile_slug>-objets [recommended default]
object bucket:       zettel-kasten-<profile_slug>-objets      [deferred manual external step]
SQLite:              local generated search/index DB          [generated local]
Neon/Postgres:       remote coordination DB                    [deferred]
R2/B2/S3:            remote object storage provider            [deferred manual external step]
```

The enforced GitHub rule is the `zettel-kasten-` prefix. The first-use default
is the full `zettel-kasten-<profile_slug>` name, so guidance should show that
canonical default before any manual GitHub step.

`local objet store` means the local folder for raw source/original files. Git
stores zets, source maps, manifests, specs, and receipts. It should not be
presented as the default place for private raw documents, videos, photos, or
large binary originals.

Do now:

- choose/confirm `profile_slug`,
- confirm the local archive root,
- confirm the local objet store location,
- run GitHub and object storage planners with `--dry-run` before manual provider setup.

Defer:

- Neon/Postgres,
- R2/B2/S3 bucket creation,
- provider account creation,
- token entry,
- upload/sync,
- source import,
- minting.

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
What profile_slug should be used for safe folder, repo, and bucket names?
Is C:\Users\<user>\zettel-kasten-<profile_slug> okay as the local archive root?
Is C:\Users\<user>\zettel-kasten-<profile_slug>-objets okay as the local objet store for raw source/original files?
```

Default:

```text
personal archive
local-first
private
profile_slug = username
local archive root = C:\Users\<user>\zettel-kasten-<profile_slug>
local objet store = C:\Users\<user>\zettel-kasten-<profile_slug>-objets
```

### Stage 3: Versioned Map

Ask whether to connect GitHub:

```text
Do you want GitHub private repo sync for versioned zets, specs, source maps, and receipts?
```

If yes:

- resolve the WOM profile first,
- run `archive github-repo --dry-run`,
- show that the default repo name is `zettel-kasten-<profile_slug>`,
- ask for human review,
- write local provider metadata only with `--approve --reviewed-by`,
- create/select the actual GitHub repository manually outside this batch,
- configure Git remotes only after a separate explicit human step,
- do not commit secrets.

### Stage 4: Objet Storage

Ask which objet storage should hold large originals:

```text
local only
Cloudflare R2
Backblaze B2
AWS S3
other S3-compatible storage
```

If object storage is selected:

- run `archive object-storage --dry-run`,
- explain that local objet store means raw source/original files and the remote bucket is deferred unless the user explicitly proceeds,
- review the proposed bucket/container, prefix, provider binding, and receipt,
- use provider login/API key flow outside WOM-kit,
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
2. run create-draft dry-run,
3. show the proposed inbox draft,
4. create the draft only after human draft approval,
5. ask whether to mint,
6. run mint checklist,
7. mint only after separate approval.

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
-> create-draft dry-run
-> human draft approval
-> create inbox draft
-> link source_refs
-> ask for mint
```

```text
"방금 만든 발표대본을 우리 회사 zettel-kasten에 올려줘"
-> profile-resolve
-> runtime-context
-> create-draft dry-run
-> human draft approval
-> create inbox draft
-> mint only if separately approved
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
