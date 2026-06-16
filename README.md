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
v0.3.71 pre-release
```

This repository is a public showcase and reference implementation workspace. It is not production-ready yet.

What exists today:

- a public WOM/zet/ZET design baseline with specs, schemas, fake archives, release notes, and work logs,
- WOM-kit local CLI and MCP tooling under `wom-kit/`, importing as `wom_kit`,
- read-only WOM-kit version truth-source checks through `archive --version`, `archive version --format json`, parent project installed-version pin discovery from archive roots, and runtime-context version metadata,
- runtime-context canonical entrypoint metadata so AI runtimes can see which archive-relative files/directories to treat as start-here and authoritative sources,
- private archive lifecycle tools for doctor checks, draft creation, minting, delegation, receipts, search, and metadata review,
- read-only preview layers for runtime context, profiles, source/objet intake, block headers, prompt boundaries, foreign block review, projection, shared update review/index, shared update route pointers, and ZET would-transport planning,
- read-only derived-text coverage/toolchain/doctor/agent-contract gates, manifest-scoped completeness signals, including non-echoed tool-hint paths for PATH-missing local extractors, plus approval-gated single-file and JSONL batch derived text capture for registering already extracted parser/OCR/ASR/vision text against source objets,
- approval-gated `.gitignore` repair for missing WOM-kit safe defaults,
- human-guided project intake planning, decision receipts, source-intake context, and objet-capture receipt gates,
- read-only beginner setup manual with KeePassXC first-vault field walkthroughs, KeePassXC CSV bulk migration import/merge guidance, and Cloudflare R2 bucket/API-token field walkthroughs, connected accounts bridge with separate credential-catalog status, plus read-only credential reference planning, inventory, external store recommendation, vault onboarding planning, credential semantic extraction recipe, plaintext migration planning, future access broker planning, local approval receipt preview/write, credential policy checking, KeePassXC command preflight, CLI-only KeePassXC write execution with non-secret execution receipts, adapter readiness planning, adapter manifest preview, and adapter audit receipt preview for mail, OpenAI API, OCR API, provider, object storage, and backup secrets,
- read-only human artifact store planning for WordPress, Joplin, Notion, Obsidian, Evernote, generic Markdown, and generic workspace surfaces, plus text-first external export planning before large media downloads, manifest-aware object-storage recommendation matching with surfaced bucket names, exact next commands, Cloudflare R2 setup field guidance, adapter readiness planning, operation request packaging, and presigned URL planning before live provider adapters,
- read-only IMAP mailbox source planning, operation request packaging, schema-validated adapter manifest previews, approval-gated local adapter manifest writes, adapter readiness checks, mailbox selection planning, adapter audit receipt previews, approval-gated local adapter audit receipt writes, adapter preflight checks, adapter execution-contract planning, a first approval-gated local IMAP header metadata scan for Gmail, Naver, and generic IMAP account refs, an offline audit checkpoint for those header scan execution receipts, read-only material selection, capture request, and capture execution-contract planning, approval-gated non-secret material selection records, and approval-gated material capture approval receipts before future body/attachment/derived-text work,
- documented Notion page snapshot and `store-ref` boundaries for page/block JSON exports,
- read-only objet reference resolution, presigned URL planning, and zettel objet link previews for mapping `sha256:<hex>` refs to safe local/external candidates without creating provider URLs,
- approval-gated local write paths for selected private archive, foreign-block review records, and the first v0.3.0 shared update attestation/review record,
- a v0.2.x freeze / v0.3.0 entry boundary document plus a narrow v0.3.0 write boundary that stays local-first and body-safe,
- local public-release hygiene tools for links, Korean product language, privacy, release readiness, and branch-protection planning.

For a status-by-capability view, see the [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md).

What does not exist yet:

- production-grade installation and platform support,
- real OS keyring read/write adapters, secret retrieval, OAuth flows, OpenAI API calls, or paid OCR API calls,
- live provider integrations or provider API sync,
- broad IMAP ingestion beyond the first approval-gated header metadata scan: OAuth login, keyring/password-manager retrieval, non-inbox mailbox selection, message body capture, attachment capture, or email-derived text extraction,
- production `ZET` transport, sharing service, feed update, or mirroring delivery,
- real wallet creation, private-key custody, cryptographic signing, token mechanics, payments, staking, consensus, or blockchain integration,
- recommendation fetching, ranking, automatic neighbor feed updates, or provider-backed recommendation services,
- projection-plan apply/write behavior, projection receipts, WordPress publishing, or provider-specific publishing,
- real foreign block import/trust/apply, signed attestation statements, receiver-side acceptance, or automatic shared-block renewal,
- complete prompt-injection prevention, full-auto execution, model training, backpropagation, Redis, queues, or background workers,
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
- [Korean Product Language Baseline](wom-kit/docs/concepts/korean-product-language-baseline.ko.md)
- [Korean Product Language Hygiene](wom-kit/docs/korean-product-language-hygiene.md)
- [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md)
- [Version Truth Source](wom-kit/docs/version-truth-source.md)
- [Runtime Canonical Entry Points](wom-kit/docs/runtime-canonical-entrypoints.md)
- [Derived Text Completeness Signal](wom-kit/docs/derived-text-completeness-signal.md)
- [ZET Radio-Frequency Recommendation Model](wom-kit/docs/zet-radio-frequency-recommendation-model.md)
- [ZET Shared Update Record Baseline](wom-kit/docs/zet-shared-update-record-baseline.md)
- [ZET Shared Update Record Review Preview](wom-kit/docs/zet-shared-update-record-review-preview.md)
- [ZET Shared Update Record Review Index](wom-kit/docs/zet-shared-update-record-review-index.md)
- [Shared Update Attestation Review Write](wom-kit/docs/shared-update-attestation-review-write.md)
- [Shared Update Route Preview](wom-kit/docs/shared-update-route-preview.md)
- [ZET Transport Threat Model](wom-kit/docs/zet-transport-threat-model.md)
- [v0.2.x Freeze And v0.3.0 Entry Boundary](wom-kit/docs/v02x-freeze-v03-entry-boundary.md)
- [Public Release Link Hygiene](wom-kit/docs/public-release-link-hygiene.md)
- [Public Privacy Hygiene](wom-kit/docs/public-privacy-hygiene.md)
- [Release Readiness Gate](wom-kit/docs/release-readiness-gate.md)
- [Main Branch Protection Readiness](wom-kit/docs/main-branch-protection-readiness.md)
- [Public Documentation Map](wom-kit/docs/public-documentation-map.md)
- [Project Intake Cookbook](wom-kit/docs/project-intake-cookbook.md)
- [Credential Store Contract](wom-kit/docs/credential-store-contract.md)
- [Credential Ref Inventory And Onboarding](wom-kit/docs/credential-ref-inventory-and-onboarding.md)
- [Credential Store Recommendations](wom-kit/docs/credential-store-recommendations.md)
- [Credential Vault Onboarding Plan](wom-kit/docs/credential-vault-onboarding-plan.md)
- [Beginner Setup Manual](wom-kit/docs/beginner-setup-manual.md)
- [Connected Accounts](wom-kit/docs/connected-accounts.md)
- [Credential Semantic Extraction Recipe](wom-kit/docs/credential-semantic-extraction-recipe.md)
- [Credential Plaintext Migration Plan](wom-kit/docs/credential-plaintext-migration-plan.md)
- [Credential Access Broker Plan](wom-kit/docs/credential-access-broker-plan.md)
- [Credential Access Approval Plan](wom-kit/docs/credential-access-approval-plan.md)
- [Credential Policy Check](wom-kit/docs/credential-policy-check.md)
- [Credential KeePassXC Command Plan](wom-kit/docs/credential-keepassxc-command-plan.md)
- [Credential KeePassXC Write](wom-kit/docs/credential-keepassxc-write.md)
- [Credential Adapter Readiness Plan](wom-kit/docs/credential-adapter-readiness-plan.md)
- [Credential Adapter Manifest Plan](wom-kit/docs/credential-adapter-manifest-plan.md)
- [Credential Adapter Audit Plan](wom-kit/docs/credential-adapter-audit-plan.md)
- [Human Artifact Store Contract](wom-kit/docs/human-artifact-store-contract.md)
- [External Export Plan](wom-kit/docs/external-export-plan.md)
- [Object Storage Recommendations](wom-kit/docs/object-storage-recommendations.md)
- [Object Storage Adapter Readiness Plan](wom-kit/docs/object-storage-adapter-readiness-plan.md)
- [Object Storage Operation Request Plan](wom-kit/docs/object-storage-operation-request-plan.md)
- [IMAP Mailbox Source](wom-kit/docs/imap-mailbox-source.md)
- [IMAP Mailbox Operation Request Plan](wom-kit/docs/imap-mailbox-operation-request-plan.md)
- [IMAP Mailbox Adapter Manifest Plan](wom-kit/docs/imap-mailbox-adapter-manifest-plan.md)
- [IMAP Mailbox Adapter Manifest Write](wom-kit/docs/imap-mailbox-adapter-manifest-write.md)
- [IMAP Mailbox Adapter Readiness Plan](wom-kit/docs/imap-mailbox-adapter-readiness-plan.md)
- [IMAP Mailbox Selection Plan](wom-kit/docs/imap-mailbox-selection-plan.md)
- [IMAP Mailbox Adapter Audit Plan](wom-kit/docs/imap-mailbox-adapter-audit-plan.md)
- [IMAP Mailbox Adapter Audit Write](wom-kit/docs/imap-mailbox-adapter-audit-write.md)
- [IMAP Mailbox Adapter Preflight Plan](wom-kit/docs/imap-mailbox-adapter-preflight-plan.md)
- [IMAP Mailbox Adapter Execution Contract](wom-kit/docs/imap-mailbox-adapter-execution-contract.md)
- [IMAP Mailbox Header Metadata Scan](wom-kit/docs/imap-mailbox-header-metadata-scan.md)
- [IMAP Mailbox Header Scan Receipt Audit](wom-kit/docs/imap-mailbox-header-scan-receipt-audit.md)
- [IMAP Mailbox Material Selection Plan](wom-kit/docs/imap-mailbox-material-selection-plan.md)
- [IMAP Mailbox Material Selection Record](wom-kit/docs/imap-mailbox-material-selection-record.md)
- [IMAP Mailbox Material Capture Request Plan](wom-kit/docs/imap-mailbox-material-capture-request-plan.md)
- [IMAP Mailbox Material Capture Execution Contract](wom-kit/docs/imap-mailbox-material-capture-execution-contract.md)
- [IMAP Mailbox Material Capture Approval Plan](wom-kit/docs/imap-mailbox-material-capture-approval-plan.md)
- [Notion Page Snapshot Model](wom-kit/docs/notion-page-snapshot-model.md)
- [Objet Ref Resolution](wom-kit/docs/objet-ref-resolution.md)
- [Presigned URL Plan](wom-kit/docs/presigned-url-plan.md)
- [Zettel Objet Links](wom-kit/docs/zettel-objet-links.md)
- [Derived Text Coverage And Toolchain](wom-kit/docs/derived-text-coverage-and-toolchain.md)

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
- provider page/block snapshot JSON

Recommended default:

```text
original source files -> local objet store and/or object storage provider
object identity       -> object manifest
derived text          -> provenance-aware derived text records
zets and metadata     -> Git repository
search text           -> SQLite/search index
```

See [Source Object Storage Policy](wom-kit/docs/source-object-storage-policy.md).
For Notion page/block exports, see [Notion Page Snapshot Model](wom-kit/docs/notion-page-snapshot-model.md).

For provider setup metadata, WOM-kit can also run a local receipt consistency
check:

```text
archive provider-status <archive-root> --dry-run
```

This CLI command, and the matching MCP `provider_setup_status` tool, check
`provider-bindings.yml` against local provider setup receipts. They do not call
GitHub, create buckets, upload files, push remotes, or verify live provider
account state.

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
v0.3.71
v0.3.70
v0.3.69
v0.3.68
v0.3.67
v0.3.66
v0.3.65
v0.3.61
v0.3.60
v0.3.59
v0.3.58
v0.3.57
v0.3.56
v0.3.55
v0.3.54
v0.3.53
v0.3.52
v0.3.51
v0.3.50
v0.3.49
v0.3.48
v0.3.47
v0.3.46
v0.3.45
v0.3.44
v0.3.43
v0.3.42
v0.3.41
v0.3.38
v0.3.37
v0.3.31
v0.3.30
v0.3.29
v0.3.28
v0.3.27
v0.3.26
v0.3.25
v0.3.24
v0.3.23
v0.3.22
v0.3.21
v0.3.20
v0.3.19
v0.3.18
v0.3.17
v0.3.16
v0.3.15
v0.3.14
v0.3.13
v0.3.12
v0.3.11
v0.3.10
v0.3.9
v0.3.8
v0.3.7
v0.3.6
v0.3.5
v0.3.4
v0.3.3
v0.3.2
v0.3.1
v0.3.0
v0.2.60
v0.2.59
v0.2.58
v0.2.57
v0.2.56
v0.2.55
v0.2.54
v0.2.53
v0.2.52
v0.2.51
v0.2.50
v0.2.49
v0.2.48
v0.2.47
v0.2.46
v0.2.45
v0.2.44
v0.2.43
v0.2.42
v0.2.41
v0.2.40
v0.2.39
v0.2.38
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
v0.2.10
v0.2.9
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
