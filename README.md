# Zettel-Kasten + Zet

`zettel-kasten` is a local-first, AI-native archive system.

`zet` is the text-centered sharing layer that can later turn selected archive knowledge into private messages, social feeds, or collaborative workspaces.

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

Current public baseline:

```text
v0.2.2 draft
```

## Versioned Compatibility

`zettel-kasten` and `zet` should be understood as a versioned protocol family.

Release tags such as `v0.1.0`, `v0.2.0`, and future `v1.0.0` are compatibility checkpoints. Users may follow the latest release, or stay on an older release, but sharing and verification work best when both sides understand the same major protocol version.

See `VERSIONING.md`.

See `UPGRADE.md` for version-by-version upgrade instructions.

See `CHANGELOG.md` for release notes.

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
