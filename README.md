# Zettel-Kasten + Zet

> A local-first, AI-native archive protocol where private memory becomes durable, inspectable, and deliberately shareable text.

[한국어 README](README.ko.md) · [Documentation Map](ai-archive-kit/docs/public-documentation-map.md) · [Upgrade Guide](UPGRADE.md) · [Changelog](CHANGELOG.md) · [Release Notes](ai-archive-kit/docs/releases/) · [Security](SECURITY.md)

`zettel-kasten` is a personal and organizational archive system designed for AI-assisted work without surrendering the archive to a central SaaS server.

`zet` is the text-centered unit that can later power private messaging, social feeds, and collaborative workspaces.

## Status

Current public baseline:

```text
v0.2.11 pre-release
```

This repository is a public showcase and reference implementation workspace. It is not production-ready yet.

What exists today:

- product and protocol specifications,
- JSON schemas,
- fake sample archives,
- setup and security documentation,
- versioned release notes,
- early Python CLI and MCP tooling,
- CLI-backed private minting from draft zet to canonical zettel, mint receipt, and draft snapshot.
- dry-run `delegate-zet`, `attest-zet`, and `anchor-zet` lifecycle previews, including `claimable_once` delegate capability previews.

What does not exist yet:

- production-grade installation flow,
- live provider integrations,
- production `zet` sharing service,
- stable `v1.0.0` protocol guarantee.

## Core Model

The base archive model is:

```text
source/original data + metadata + minted zets
```

In other words:

- source/original data is the evidence layer,
- metadata makes sources addressable and auditable,
- minted zets are human-approved archive memory.

The system starts from the archive, not from a social app.

For the full design philosophy, including the human data primitive model, AX rationale, and Web3-like `zet` sharing model, see:

- [Foundational Product Whitepaper](ai-archive-kit/docs/concepts/foundational-product-whitepaper.md)
- [Product Philosophy](ai-archive-kit/docs/concepts/product-philosophy.md)
- [Public Documentation Map](ai-archive-kit/docs/public-documentation-map.md)

The public project records are intentionally separated into:

```text
product blueprint / design philosophy
implementation reference research
implementation plans
work logs
```

## What Is A Zet?

A `zet` is always text.

It is a Markdown-like document created by a human, or drafted by AI under human supervision, then minted into a private archive.

Minting means:

```text
draft zet -> human review -> canonical private archive record
```

Minting does not mean public posting. External sharing is a separate action.

## Why This Matters

Most tools make users adapt to an application.

`zettel-kasten` takes the opposite direction:

```text
the user's archive stays primary,
AI helps draft and connect memory,
sharing is a deliberate projection from private memory.
```

The future `zet` sharing layer follows this projection model:

```text
1:1 zet sharing       -> messenger
1:many zet sharing    -> social feed / SNS
many:many zet sharing -> collaboration workspace
```

## Storage Model

Object storage is not only for media files.

Original documents and captures are source objects when they are used as evidence:

- `.hwp`
- `.hwpx`
- `.docx`
- `.xlsx`
- `.pdf`
- `.txt`
- `.md`
- `.csv`
- screenshots
- audio/video
- provider exports

Recommended default:

```text
original source files -> local object store and/or object storage
object identity       -> object manifest
derived text          -> provenance-aware derived text records
zets and metadata     -> Git repository
search text           -> SQLite/search index
```

See [Source Object Storage Policy](ai-archive-kit/docs/source-object-storage-policy.md).

## Text Provenance

Not every text artifact has the same authority.

`zettel-kasten` distinguishes:

```text
L0 original source object
L1 born-digital editable text
L2 parser-extracted text
L3 OCR / speech-to-text / AI transcription
L4 human-reviewed derived text
L5 minted zet
```

OCR and AI transcription are useful, but they are model-dependent derived records. They should keep source object id, derivation method, tool/model version, confidence when available, and review status.

See [Text Provenance Hierarchy](ai-archive-kit/docs/text-provenance-hierarchy.md).

## Versioning

`zettel-kasten` and `zet` are managed as a versioned protocol family.

Release tags are compatibility checkpoints:

```text
v0.2.11
v0.2.9
v0.3.0
v1.0.0
```

Same major protocol version should mean expected compatibility. Different major versions may need migration or compatibility bridges.

See [Versioning](VERSIONING.md) and [Upgrade Guide](UPGRADE.md).

## Repository Layout

```text
ai-archive-kit/
  specs/        product and protocol specifications
  docs/         setup, security, onboarding, release, and operating notes
  plans/        implementation plans and public-safe work logs
  schemas/      JSON Schema files
  src/          Python package code
  cli/          local CLI entrypoint
  examples/     fake sample archive data
  templates/    personal, family, and company archive templates
```

## Documentation Map

The public documentation is organized by purpose:

- product blueprint / design philosophy: [Documentation Map](ai-archive-kit/docs/public-documentation-map.md)
- implementation reference research: [Implementation Research](ai-archive-kit/specs/zettelkasten-zet-implementation-research.md)
- implementation plans: [Plans Directory](ai-archive-kit/plans/)
- work logs: [Work Logs](ai-archive-kit/plans/)

Start with [Public Documentation Map](ai-archive-kit/docs/public-documentation-map.md) if you want to understand the project before reading code.

## Quick Verification

```bash
cd ai-archive-kit
python -m unittest discover -s tests
python cli/archive.py doctor examples/fake-life-archive --strict
```

Expected result:

```text
tests pass
doctor reports 0 errors and 0 warnings
```

## Privacy Boundary

This public repository is not a real user archive.

Do not commit:

- provider tokens,
- local credentials,
- real private zets,
- real source maps,
- real receipts,
- private AI conversations,
- personal files or media,
- local machine paths or private filenames.

Real usage should happen in a private archive repository and separate object storage.

See [Open Source Publication Model](ai-archive-kit/docs/open-source-publication-model.md).

## Authorship

Original concept, product philosophy, naming, written design, schemas, and reference implementation:

```text
Kim Seong Kyun (김성균)
Department of Urban Sociology, University of Seoul
GitHub: mow-coding
Email: mow.coding@gmail.com
Email: ellie0129@uos.ac.kr
```

If this project helps you, a GitHub star is appreciated. Collaboration and investment inquiries are welcome by email.

## License

MIT License. See [LICENSE](LICENSE).
