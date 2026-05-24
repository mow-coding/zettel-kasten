# Work Log: Zettel-Kasten, zet, and ZET Blueprint Consolidation

Date: 2026-05-22

## 1. Purpose

Record the work done to consolidate the scattered `zettel-kasten` and `zet` planning into public-ready project artifacts.

This work log is intentionally separate from:

- product blueprint,
- implementation research,
- implementation plan,
- meeting minutes,
- decision log.

## 2. Work Completed

### Product Blueprint

Created:

```text
wom-kit/specs/zettelkasten-zet-product-blueprint.md
```

Purpose:

Consolidates the product philosophy and concept model:

- `zettel-kasten = source/original data + metadata + zets`
- `zet = v0.2 Markdown-compatible text document + metadata envelope`
- minting = private archive issuance
- sharing = separate future layer
- shared zets can become messenger/SNS/collaboration objects
- shared zets can compose into new archives

### Implementation Research

Created:

```text
wom-kit/specs/zettelkasten-zet-implementation-research.md
```

Purpose:

Maps the blueprint to implementation references:

- W3C PROV,
- IPFS content addressing,
- BagIt,
- RO-Crate,
- Basic Memory,
- MCP,
- JSON Schema,
- OPA,
- SQLite FTS5,
- DID Core,
- Verifiable Credentials,
- UCAN,
- Nostr,
- Secure Scuttlebutt,
- Radicle,
- Automerge,
- Yjs,
- Anytype/AnySync,
- Briar,
- SimpleX,
- Matrix,
- MLS.

### Open Source Publication Model

Created:

```text
wom-kit/docs/open-source-publication-model.md
```

Purpose:

Defines what should be public and private when the project is released as open source.

### Implementation Plan

Created:

```text
wom-kit/plans/phase-8-minting-implementation-plan.md
```

Purpose:

Defines the next practical implementation slice:

```text
draft zet -> mint -> canonical private zet + receipt + draft snapshot
```

### AI-Assisted Onboarding And Provider Setup

Created:

```text
wom-kit/docs/ai-assisted-onboarding-and-provider-setup.md
```

Purpose:

Records the required beginner-friendly setup experience:

- one-command installation,
- local AI-assisted setup through tools such as Codex, Claude, or Antigravity,
- guided GitHub and object storage connection,
- provider-aware setup for local folders, SSDs, Notion, Google Drive/GCP, Google Photos, and external URLs,
- natural-language requests mapped to dry-run plans, approvals, archive actions, and receipts.

## 3. Sensitive Boundary Noted

The repository root currently contains a hidden provider login file pattern such as:

```text
.notion-*-login.txt
```

This must be treated as sensitive and excluded before any GitHub publication.

## 4. Current Project Understanding

The open-source project should publish:

- code,
- schemas,
- specs,
- fake examples,
- planning docs,
- implementation research,
- implementation plans,
- work logs,
- selected public-safe meeting minutes,
- decision logs.

It should not publish real private archives, provider tokens, private source maps, private receipts, real zets, or real source data.

## 5. Next Suggested Work

Before implementing:

1. Confirm open-source license direction.
2. Decide whether `mint-zettel` becomes the user-facing command.
3. Decide the first public installer shape.
4. Decide the first live provider integration after local folders and GitHub.
5. Add `mint-receipt.schema.json`.
6. Implement the local minting flow.
7. Update tests and doctor checks.
