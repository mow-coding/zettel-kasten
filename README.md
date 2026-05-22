# Zettel-Kasten + Zet

`zettel-kasten` is a local-first, AI-native archive system.

`zet` is the text-centered sharing layer that can later turn selected archive knowledge into private messages, social feeds, or collaborative workspaces.

## 한국어 요약

`zettel-kasten`은 로컬 우선, AI-native 개인/조직 아카이브 시스템입니다.

`zet`는 그 아카이브 안에서 사람이 직접 쓰거나, AI와 함께 작성하고, 사람이 승인해 민팅한 텍스트 문서입니다.

핵심 구조는 다음과 같습니다.

```text
원본/source 데이터 + 메타데이터 + 민팅된 zets
```

중요한 원칙:

- `zet`는 항상 텍스트입니다.
- 원본 파일은 별도의 source/object layer에 보관합니다.
- `.hwp`, `.hwpx`, `.docx`, `.xlsx`, `.pdf`, `.txt`, `.md`, `.csv` 같은 문서도 원본이면 source object입니다.
- OCR, 음성인식, AI 전사 텍스트도 보관하지만, 원래부터 존재하던 편집 가능한 텍스트와 같은 위계로 보지 않습니다.
- 민팅은 외부 공개가 아니라, 우선 private archive에 공식 기록으로 편입하는 행위입니다.
- 공유, 메시징, SNS, 협업은 그 private archive 위에 얹히는 별도 projection layer입니다.

현재 이 공개 저장소는 실제 개인 아카이브가 아니라, 공개 전시용/오픈소스 구현 작업공간입니다.

## Core Idea

Most tools start from an app.

This project starts from a person's archive:

```text
source/original data + metadata + minted zets
```

A `zet` is always text: a Markdown-like document created by a human, or drafted by AI under human supervision, then minted into a private archive.

Raw files, media, Notion pages, Google Drive folders, local SSDs, object storage, and external URLs can be referenced as source worlds. The durable human-readable unit remains the `zet`.

## Why This Exists

The project is an experiment in durable AI-assisted memory:

```text
Human talks with AI.
AI helps draft and organize.
Important context becomes a zet.
Zets accumulate into a stronger zettel-kasten.
Sharing is deliberate, permissioned, and separate from private thinking.
```

The future `zet` service is based on this projection model:

```text
1:1 zet sharing       -> messenger
1:many zet sharing    -> social feed / SNS
many:many zet sharing -> collaboration workspace
```

## Current Status

This repository is a public showcase and open-source implementation workspace.

It currently contains:

- protocol and product specs,
- schemas,
- fake examples,
- setup and security docs,
- implementation plans,
- early Python CLI/MCP tooling.

The system is not production-ready yet.

한국어:

이 저장소는 공개 전시용 오픈소스 저장소입니다. 실제 사용자의 개인 자료, 실제 source map, 실제 receipt, provider token, private zet는 여기에 올리면 안 됩니다.

Current public baseline:

```text
v0.2.3 draft
```

## Versioned Compatibility

`zettel-kasten` and `zet` should be understood as a versioned protocol family.

Release tags such as `v0.1.0`, `v0.2.0`, and future `v1.0.0` are compatibility checkpoints. Users may follow the latest release, or stay on an older release, but sharing and verification work best when both sides understand the same major protocol version.

See `VERSIONING.md`.

See `UPGRADE.md` for version-by-version upgrade instructions.

See `CHANGELOG.md` for release notes.

한국어:

`zettel-kasten`과 `zet`는 버전별 규칙을 따르는 프로토콜 계열로 관리합니다. 같은 major version을 쓰는 사람들은 같은 핵심 규칙을 이해할 수 있어야 하고, 다른 major version 사이에는 migration이나 compatibility bridge가 필요할 수 있습니다.

## Repository Map

```text
ai-archive-kit/
  specs/        product and protocol specifications
  docs/         setup, security, onboarding, and operating notes
  plans/        implementation plans and public-safe work logs
  schemas/      JSON Schema files
  src/          Python package code
  cli/          local CLI entrypoint
  examples/     fake sample archive data
  templates/    personal, family, and company archive templates
```

## Source Documents And Object Storage

Object storage is not only for images, audio, and video.

Original documents such as `.hwp`, `.hwpx`, `.docx`, `.xlsx`, `.pdf`, `.txt`, `.md`, and `.csv` may also be source objects. The recommended default is:

```text
original source files -> local object store and/or object storage
object identity       -> object manifest
derived text          -> provenance-aware derived text records
zets and metadata     -> Git repository
search text           -> SQLite/search index
```

A minted `zet` is stored as text. The original file it cites remains a source object.

See `ai-archive-kit/docs/source-object-storage-policy.md`.

OCR, speech-to-text, and AI transcription are also stored, but they have different authority from original editable text. See `ai-archive-kit/docs/text-provenance-hierarchy.md`.

한국어:

객체 스토리지는 사진/영상만 넣는 곳이 아닙니다. 원본 문서 파일도 source object로 들어갈 수 있습니다. 단, `zet` 자체는 텍스트 문서이며, 원본 문서나 OCR 결과와 섞어버리면 안 됩니다.

특히 OCR/AI 전사 텍스트는 모델이 발전하면 다시 생성될 수 있으므로, 원본 텍스트와 다른 provenance를 가져야 합니다.

## Open Source And Attribution

The code and documentation in this repository are released as open source under the MIT License unless a file says otherwise.

Original concept, product philosophy, naming, written design, schemas, and reference implementation:

```text
Copyright (c) 2026 Kim Seong Kyun (김성균)
```

Creator:

```text
Kim Seong Kyun (김성균)
Department of Urban Sociology, University of Seoul
Undergraduate student, currently on leave
GitHub: mow-coding
Email: mow.coding@gmail.com
Email: ellie0129@uos.ac.kr
```

If this project helps you, teaches you something, or gives you an idea, a GitHub star is warmly appreciated.

Messages, collaboration notes, and investment inquiries are welcome at:

```text
mow.coding@gmail.com
ellie0129@uos.ac.kr
```

## Privacy Boundary

This public repository is not a user's real archive.

Real archives should remain private by default and should not commit:

- provider tokens,
- local credentials,
- real source maps,
- real receipts,
- private zets,
- private AI conversations,
- personal files or media.

See `ai-archive-kit/docs/open-source-publication-model.md` for the intended public/private split.

한국어:

이 공개 저장소는 실제 사용자의 private archive가 아닙니다. 실제 개인 파일, 실제 경로, 실제 provider token, 실제 source map, 실제 receipt, private AI 대화 기록은 공개 저장소에 커밋하지 마세요.
