# WOM

> Widesider of Modernity: a local-first, AI-native, Web3-oriented archive and communication system for widening the horizon of human perception.

[한국어 README](README.ko.md) · [Documentation Map](wom-kit/docs/public-documentation-map.md) · [Upgrade Guide](UPGRADE.md) · [Changelog](CHANGELOG.md) · [Release Notes](wom-kit/docs/releases/) · [Security](SECURITY.md) · [Disclaimer](DISCLAIMER.md)

`WOM` stands for `Widesider of Modernity`.

The name expresses the ambition to stand near the frontier of modernity and widen the horizon that humans can perceive.

Inside WOM:

- `zettel-kasten` is the historical root and local archive method,
- `zet` is the unit document minted inside a zettel-kasten,
- `header` is refs, hashes, provenance, policy, and receipts around a zet,
- `block` is `zet + header`,
- `ZET` is the zettel-kasten-based communication layer that can become messaging, SNS/feed, or collaboration,
- `node` is the subject/archive participant,
- the preferred lifecycle is `mint -> delegate -> attest -> anchor`.

`zettel-kasten` remains the repository and archive-system root, but the product language should center `WOM`, `zet`, `ZET`, and `node`.

## Status

Current public baseline:

```text
v0.2.37 pre-release
```

This repository is a public showcase and reference implementation workspace. It is not production-ready yet.

What exists today:

- product and protocol specifications,
- JSON schemas,
- fake sample archives,
- setup and security documentation,
- versioned release notes,
- early Python CLI and MCP tooling,
- CLI-backed private minting from draft zet to canonical archive memory, currently recorded with mint receipts and draft snapshots,
- CLI-backed real delegate proof/receipt writes for scoped zet delegation,
- dry-run `attest-zet` and `anchor-zet` lifecycle previews, including `claimable_once` delegate capability previews.
- WOM Safe HTML Profile design notes for the long-term canonical/interchange/rendering target.
- read-only `check-safe-html` validation for obvious unsafe patterns before future WOM Safe HTML Profile migration.
- read-only `runtime-context` output so terminal-capable AI runtimes can confirm the active archive before drafting, dry-runs, or mint approval requests.
- read-only profile registry resolution so AI runtimes resolve the requested target profile before assuming the default archive.
- profile-aware `create-draft --dry-run` so AI runtimes preview inbox drafts and replay approved draft writes without minting.
- current local implementation/tooling lives in `wom-kit/` and imports as `wom_kit`.
- dry-run-first GitHub repository setup planning for WOM profiles, with local-only approval metadata and no provider API calls.
- dry-run-first objet storage setup planning for WOM profiles, with local-only approval metadata and no bucket creation, upload, sync, copy, or hashing.
- dry-run-only source intake planning so AI runtimes can classify source/objet references before draft creation without reading bodies, hashing, importing, uploading, or calling provider APIs.
- source-intake plan composition for `create-draft`, so AI runtimes can safely carry source refs into draft previews or approved inbox draft writes without re-reading source files.
- read-only block header previews that derive a header from one existing draft or canonical zet without minting, modifying files, reading objet bodies, or calling providers.
- read-only profile wallet previews that treat a WOM profile as wallet-ready identity context without generating keys, signing, storing secrets, or calling blockchain/provider APIs.
- read-only prompt boundary checks that treat inspected external text as untrusted data and flag obvious prompt-injection / unsafe-agent strings without calling LLMs.
- prompt-boundary report composition for `create-draft`, so AI runtimes can preserve the "external text is data, not authority" boundary in draft frontmatter and mint receipts.
- read-only foreign block intake previews that inspect shared block/header JSON or Markdown-compatible foreign zets without importing, trusting, drafting, minting, attesting, anchoring, or applying them.
- read-only foreign block trust previews that consume intake reports and classify them as reject, manual review required, or eligible for future attestation without creating trust or attestations.
- read-only foreign block attestation packet previews that consume trust reports and prepare a human-review packet without creating trust, writing attestations, writing receipts, or re-reading the foreign artifact.
- read-only foreign block quarantine plans that consume attestation packet previews and propose archive-relative future holding paths without creating quarantine files, trust, imports, attestations, or receipts.
- CLI-only approved foreign block quarantine writes that create a sanitized untrusted review case and quarantine receipt without importing, trusting, minting, attesting, anchoring, delegating, signing, executing, or accepting the foreign block.
- read-only foreign block quarantine review indexes that list existing untrusted quarantine cases and receipt consistency checks without changing trust state, importing, attesting, minting, anchoring, delegating, signing, or accepting the foreign block.
- read-only foreign block quarantine decision previews that inspect one untrusted case and propose a future decision path without recording approval, trusting, importing, attesting, minting, anchoring, delegating, signing, accepting, or applying the foreign block.
- CLI-only approved foreign block quarantine decision records that write exactly one sanitized decision JSON and one receipt after replay-validating the current case and receipt, without trusting, importing, attesting, minting, anchoring, delegating, signing, accepting, applying, sharing, or calling providers.
- read-only foreign block quarantine decision review indexes that list recorded local decisions and check their decision records, receipts, original quarantine cases, and quarantine receipts without modifying trust state.
- read-only foreign block decision outcome plans that route one recorded decision into the next safe non-mutating path without trust, import, attestation, minting, acceptance, sharing, signing, provider calls, or ZET transport.

What does not exist yet:

- production-grade installation flow,
- live provider integrations,
- production `ZET` sharing service,
- real wallet creation, private key custody, or cryptographic signing,
- complete prompt-injection prevention or full-auto safety guarantees,
- LLM-based prompt classification, provider scanning, OCR/import apply, ZET transport, real signing, payments, staking, consensus, or blockchain integration,
- real foreign block import/trust/apply, real foreign attestation writes, real quarantine review apply/accept, real quarantine decision accept/apply/trust, real ZET transport, or automatic acceptance of shared blocks,
- full Markdown-to-WOM-Safe-HTML conversion or finalized profile validation,
- stable `v1.0.0` protocol guarantee.

## Core Model

The base WOM archive model is:

```text
source/original data + metadata + minted zets
```

In other words:

- source/original data is the evidence layer,
- metadata makes sources addressable and auditable,
- minted zets are human-approved archive memory.

The system starts from the archive node, not from a social app.

See [Naming And Terminology](wom-kit/docs/concepts/naming-and-terminology.md) for the current naming freeze.

For the full design philosophy, including the human data primitive model, AX rationale, and Web3-like `ZET` sharing model, see:

- [Foundational Product Whitepaper](wom-kit/docs/concepts/foundational-product-whitepaper.md)
- [Product Philosophy](wom-kit/docs/concepts/product-philosophy.md)
- [WOM Safe HTML Profile](wom-kit/docs/concepts/wom-safe-html-profile.md)
- [Public Documentation Map](wom-kit/docs/public-documentation-map.md)

The public project records are intentionally separated into:

```text
product blueprint / design philosophy
implementation reference research
implementation plans
work logs
```

## What Is `zet`?

A `zet` is always text.

It is a document created by a human, or drafted by AI under human supervision, then minted into a private archive.

In v0.2, zets remain Markdown-compatible for authoring and import compatibility. The long-term canonical/interchange/rendering target is the [WOM Safe HTML Profile](wom-kit/docs/concepts/wom-safe-html-profile.md), not arbitrary HTML.

Minting means:

```text
draft zet -> human review -> canonical private archive record
```

Minting does not mean public posting. External sharing is a separate action.

## Why This Matters

Most tools make users adapt to an application.

WOM takes the opposite direction:

```text
the user's archive stays primary,
AI helps draft and connect memory,
sharing is a deliberate projection from private memory.
```

The future `ZET` communication layer follows this projection model:

```text
1:1 ZET relation       -> messenger
1:many ZET relation    -> social feed / SNS
many:many ZET relation -> collaboration workspace
```

## Storage Model

Objet storage is not only for media files.

In WOM product language, source/original files stored outside Git are `objets`. Cloud and provider APIs may still call the technical storage layer `object storage`.

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
original source files -> local objet store and/or object storage provider
object identity       -> object manifest
derived text          -> provenance-aware derived text records
zets and metadata     -> Git repository
search text           -> SQLite/search index
```

See [Source Object Storage Policy](wom-kit/docs/source-object-storage-policy.md).

## Text Provenance

Not every text artifact has the same authority.

WOM distinguishes:

```text
L0 original source object
L1 born-digital editable text
L2 parser-extracted text
L3 OCR / speech-to-text / AI transcription
L4 human-reviewed derived text
L5 minted zet
```

OCR and AI transcription are useful, but they are model-dependent derived records. They should keep source object id, derivation method, tool/model version, confidence when available, and review status.

See [Text Provenance Hierarchy](wom-kit/docs/text-provenance-hierarchy.md).

## Versioning

WOM, `zettel-kasten`, `zet`, and `ZET` are managed as a versioned protocol family.

Release tags are compatibility checkpoints:

```text
v0.2.37
v0.2.36
v0.2.35
v0.2.34
v0.2.33
v0.2.32
v0.2.31
v0.2.30
v0.2.29
v0.2.28
v0.2.27
v0.2.26
v0.2.25
v0.2.24
v0.2.23
v0.2.22
v0.2.21
v0.2.20
v0.2.18
v0.2.17
v0.2.16
v0.2.15
v0.2.14
v0.2.13
v0.2.12
v0.2.11
v0.2.9
v0.3.0
v1.0.0
```

Same major protocol version should mean expected compatibility. Different major versions may need migration or compatibility bridges.

See [Versioning](VERSIONING.md) and [Upgrade Guide](UPGRADE.md).

## Repository Layout

```text
wom-kit/
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

- product blueprint / design philosophy: [Documentation Map](wom-kit/docs/public-documentation-map.md)
- implementation reference research: [Implementation Research](wom-kit/specs/zettelkasten-zet-implementation-research.md)
- implementation plans: [Plans Directory](wom-kit/plans/)
- work logs: [Work Logs](wom-kit/plans/)

Start with [Public Documentation Map](wom-kit/docs/public-documentation-map.md) if you want to understand the project before reading code.

## Quick Verification

```bash
cd wom-kit
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

Real usage should happen in a private archive repository and separate objet storage/object storage provider.

See [Open Source Publication Model](wom-kit/docs/open-source-publication-model.md).

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
