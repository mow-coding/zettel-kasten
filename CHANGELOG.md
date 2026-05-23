# Changelog

All notable public releases of `zettel-kasten`, `zet`, and `ZET` should be documented here.

This project uses semantic versioning for public compatibility checkpoints.

## v0.2.17 - 2026-05-24

WOM Profile Registry dry-run patch.

Added:

- `archive profile-list --registry <path> --format json`, a read-only CLI command that lists local WOM profile registry entries with local paths redacted by default,
- `archive profile-resolve --registry <path> --target <query> --format json`, a read-only CLI command that resolves a requested profile by exact profile id, label, or alias before runtime context or draft work,
- read-only MCP tools `wom_profile_list` and `wom_profile_resolve`,
- token-state aware resolution so a missing token can still resolve profile identity while disabling direct write availability,
- delegate fallback previews when a target profile is missing or a matched profile has no usable token,
- an example profile registry template with placeholder paths and fake `token_ref` values only,
- Unicode-normalized matching and blockers for registry version drift, duplicate profile ids, and raw token-like fields.

Compatibility:

- no private archive migration is required,
- no schema change is required,
- profile registry commands never write files, never scan the whole disk, never store tokens, and do not add create-draft dry-run, provider API sync, UI, real minting through MCP, or any MCP write/register/apply tool.

## v0.2.16 - 2026-05-24

WOM AI Runtime Context Layer patch.

Added:

- `archive runtime-context <archive-root> --format json`, a read-only CLI command for terminal-capable AI runtimes to confirm archive identity, type/scope, owner/principal summary, AI write policy, safe archive-relative paths, safe next actions, and doctor summary before drafting or asking for mint approval,
- default local path redaction for runtime context JSON, with `--no-redact-local-paths` available only for trusted local debugging,
- `--expected-archive-id`, `--expected-type`, and `--strict` gates so the runtime can block on archive id mismatches and treat archive type mismatches as warning-by-default or blocking in strict mode,
- read-only MCP tool `archive_runtime_context` with the same core behavior and existing MCP allowed-root enforcement,
- stable runtime context summary keys for AI parsing, with unavailable optional values represented as `null`,
- MCP local path disclosure gating through `AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1`.

Compatibility:

- no private archive migration is required,
- no schema change is required,
- runtime context never writes files and does not implement create-draft dry-run, provider API sync, UI, real minting through MCP, or any new MCP apply tool.

## v0.2.15 - 2026-05-23

WOM Safe HTML Profile validator dry-run patch.

Added:

- `archive check-safe-html --path <zet> --dry-run` CLI command, a read-only validator that inspects a v0.2 Markdown-compatible zet and reports whether it is compatible with a future WOM Safe HTML Profile migration,
- block detection for `<script>`, `<iframe>`, `<object>`, `<embed>`, `javascript:` URLs, and inline event handler attributes (for example `onclick=`),
- structured JSON output with `ok`, `lifecycle_action: check_safe_html`, `source_path`, `detected_format: markdown_compatible`, `proposed_profile: wom-safe-html/v0.1-draft`, `blockers`, `warnings`, `html_profile_preview`, `text_extraction_preview`, and `source_reference_preview`.

Compatibility:

- existing Markdown-compatible zets remain valid in the v0.2 compatibility line,
- the validator only reads; it never writes files, never converts Markdown to HTML, never changes mint output, and never migrates existing zets,
- the WOM Safe HTML Profile element/attribute allowlist is still not finalized; the validator only flags obviously unsafe patterns at this stage,
- no private archive migration is required.

## v0.2.14 - 2026-05-23

WOM Safe HTML Profile documentation/spec baseline patch.

Added:

- WOM Safe HTML Profile documents in English and Korean,
- public distinction between `WOM`, `zet`, and `ZET`,
- documentation that keeps Markdown as an authoring/import compatibility format while setting WOM Safe HTML Profile as the long-term canonical/interchange/rendering target,
- stronger explanation that `ZET` is the communication layer that can become messaging, SNS/feed, or collaboration.

Compatibility:

- no private archive migration is required,
- existing Markdown-compatible zets remain valid in the v0.2 compatibility line,
- no Markdown-to-HTML converter, validator, UI, live sharing, or P2P transport is implemented in this release.

## v0.2.13 - 2026-05-23

WOM naming baseline and compatibility alias patch.

Added:

- public WOM naming documents in English and Korean,
- `mint-zet` as the preferred CLI surface for minting a zet, with `mint-zettel` preserved as a compatibility alias,
- `parcel` as the preferred CLI surface for creating a portable bounded unit, with `pack` preserved as a compatibility alias,
- `admit --dry-run` as the preferred CLI surface for previewing parcel/workpack admission, with `import --dry-run` preserved as a compatibility alias,
- documentation that places `WOM`, `zet`, `node`, and `mint -> delegate -> attest -> anchor` at the center of the product language.

Compatibility:

- `ai-archive-kit`, `zettels/`, `receipts/`, `workpacks/`, and existing schema names remain unchanged for v0.2 compatibility,
- `promote`, `share`, `mint-zettel`, `pack`, and `import` remain available,
- no private archive migration is required.

## v0.2.12 - 2026-05-23

Real delegate receipt write patch.

Added:

- `delegate-zet --approve --reviewed-by <actor>` for writing a schema-backed delegate receipt,
- `receipts/delegate/*.delegate.json` doctor validation,
- real delegate capability nonce issuance with receipt-local claim/spent state,
- duplicate delegate receipt protection through dry-run blockers and exclusive file creation.

Compatibility:

- `delegate-zet --dry-run` remains the preview gate,
- MCP delegate tooling remains read-only and dry-run only,
- no real claim registry, spent registry, revocation registry, P2P transport, blockchain, or payment is implemented,
- no private archive migration is required.

## v0.2.11 - 2026-05-23

Delegate capability contract patch.

Added:

- `delegate-zet --target-policy counterparty_bound|claimable_once`,
- `claimable_once` delegate previews that can defer the recipient archive until attestation,
- `delegation_capability` preview fields for capability id, claim/spent preview state, nonce placeholder, binding method, and settlement condition,
- `claim_binding` previews in attestation and anchor metadata,
- MCP parity for `delegate_zet_check` with optional `target_archive`.

Compatibility:

- existing `delegate-zet` and `share --dry-run` flows remain compatible,
- v0.2.10 delegate receipts without capability fields are treated as legacy `counterparty_bound`,
- no real claim registry, spent registry, P2P transport, blockchain, or payment is implemented,
- no private archive migration is required.

## v0.2.10 - 2026-05-23

ZET sharing dry-run lifecycle contract.

Added:

- `delegate-zet --dry-run` as the product-facing dry-run surface for scoped zet delegation,
- `attest-zet --dry-run` for verifying a delegated foreign zet receipt without writing files,
- `anchor-zet --dry-run` for previewing local meaning-network anchoring without writing files,
- read-only MCP tools `delegate_zet_check`, `attest_zet_check`, and `anchor_zet_check`,
- schemas for delegate receipts, attestation receipts, and anchor metadata.

Compatibility:

- existing `share --dry-run` and MCP `share_check` remain available,
- no real P2P, SNS/feed, transport, external sending, or foreign zet import is implemented,
- no private archive migration is required.

## v0.2.9 - 2026-05-23

Terminology stabilization patch.

Changed:

- made `mint` the preferred product language for current CLI and user-facing docs,
- changed newly initialized archives to use `ai_write_policy.canonical_requires: human_minting`,
- kept `human_promotion` valid for legacy archives without doctor warnings,
- added optional `minting_rules` to zettel rules while keeping `promotion_rules` for v0.2 compatibility,
- made mint dry-runs prefer `minting_rules` and fall back to legacy `promotion_rules`,
- kept `promote`, `promotion_check`, `promotion` frontmatter, and old promotion receipts as compatibility surfaces.

Migration:

- no private archive migration required,
- existing archives that still use `human_promotion` remain valid,
- new archives should use `human_minting`.

## v0.2.8 - 2026-05-23

Minting lifecycle implementation.

Added:

- `mint-zettel` CLI command for `draft zet -> canonical private zet -> mint receipt -> draft snapshot`,
- mint receipt schema at `schemas/mint-receipt.schema.json`,
- canonical zettel `mint` frontmatter metadata with `authority_mode: basic`,
- `receipts/mint/*.mint.json` and `receipts/mint/drafts/*.draft.md` validation in doctor,
- read-only MCP `mint_zettel_check` dry-run tool.

Changed:

- real minting preserves the original `inbox/` draft,
- real minting snapshots the exact draft text at mint time,
- canonical zettels may now satisfy doctor lifecycle metadata with either new `mint` metadata or legacy `promotion` metadata,
- `promote` remains available as a compatibility command.

Migration:

- no private archive migration required,
- archives that use `mint-zettel` should keep the generated mint receipts and draft snapshots under `receipts/mint/`.

## v0.2.7 - 2026-05-23

Foundational product whitepaper patch.

Added:

- detailed English foundational product whitepaper,
- detailed Korean foundational product whitepaper,
- public-safe product whitepaper depth correction work log.

Clarified:

- `zettel-kasten` is memory infrastructure, not only a note app,
- `zet` is always text and functions as interpreted archive memory,
- minting means private archive issuance, not posting or sharing,
- the same authority model supports HITL workflows and scoped AI-agent harnesses,
- object storage covers source/original documents as well as media,
- Notion, Google Drive, local folders, GitHub, object storage, and external URLs should be handled through provenance-aware provider bindings,
- `zet` sharing can project into messenger, SNS/feed, or collaboration workspace behavior depending on relationship topology,
- the Web3-like property is subject-owned, portable, verifiable memory rather than token hype.

Migration:

- no private archive migration required.

## v0.2.6 - 2026-05-23

README baseline display correction.

Changed:

- updated the English README current public baseline from `v0.2.5` to `v0.2.6`,
- updated the Korean README current public baseline from `v0.2.5` to `v0.2.6`,
- aligned package and citation metadata with the new public patch release.

Why:

- `v0.2.5` correctly published the documentation map and philosophy patch, but the public repository page needed a follow-up patch so the visible README baseline and release chain stayed consistent without moving an already-published tag.

Migration:

- no private archive migration required.

## v0.2.5 - 2026-05-23

Public documentation map and philosophy patch.

Added:

- public documentation map,
- Korean public documentation map,
- product philosophy document,
- Korean product philosophy document.

Clarified:

- public records are separated into product blueprint/design philosophy, implementation reference research, implementation plans, and work logs,
- the project philosophy includes human data primitives, AX rationale, and Web3-like `zet` sharing,
- README files now link directly to those document groups.

Migration:

- no private archive migration required.

## v0.2.4 - 2026-05-23

Documentation polish patch.

Added:

- `README.ko.md` as a full Korean project entrypoint,
- `UPGRADE.ko.md` as a Korean upgrade guide,
- `v0.2.4` release note.

Changed:

- rewrote `README.md` as a cleaner English public entrypoint,
- split bilingual explanations into separate English/Korean documents,
- clarified public status, storage model, text provenance, versioning, and privacy boundaries.

Migration:

- no private archive migration required.

## v0.2.3 - 2026-05-23

Bilingual documentation patch.

Added:

- Korean summary in `README.md`,
- Korean upgrade guidance in `UPGRADE.md`,
- Korean notes in the `v0.2.3` release note.

Migration:

- no private archive migration required.

## v0.2.2 - 2026-05-23

Public history hygiene and text provenance clarification.

Added:

- text provenance hierarchy documentation,
- clearer distinction between original editable text, parser-extracted text, OCR/AI transcription, human-reviewed derived text, and minted zets.

Clarified:

- OCR and AI transcription should be stored, but as model-dependent derived text records,
- born-digital editable text has higher evidence authority than OCR-derived text,
- derived text must keep provenance to the source object and tool/model that produced it.

Repository hygiene:

- public history should be rewritten so older public commits do not remain as normal refs with local/private-looking examples.

Migration:

- no private archive migration required,
- future derived-text schemas may require a migration once implemented.

## v0.2.1 - 2026-05-23

Public documentation and repository hygiene patch.

Added:

- `UPGRADE.md`,
- per-version release notes under `ai-archive-kit/docs/releases/`,
- clearer version compatibility guidance,
- neutralized public examples that looked too close to local/private context.

Clarified:

- document files such as `.hwp`, `.hwpx`, `.docx`, `.xlsx`, `.pdf`, `.txt`, `.md`, and `.csv` can be source/original objects,
- object storage is the warehouse for original source files, not only media files,
- minted zets remain text and belong in the zettel layer.

Migration:

- no private archive migration required from `v0.2.0`.

## v0.2.0 - 2026-05-23

Initial public showcase baseline.

Includes:

- local-first archive protocol documents,
- zettel and zettel-kasten specs,
- JSON schemas,
- fake sample archive,
- early Python CLI and MCP tooling,
- setup and security docs,
- public product blueprint for `zettel-kasten` and `zet`,
- versioning and compatibility policy,
- source object storage policy for document files and media files.

Notes:

- This is not a production-stable `v1.0.0` release.
- The future `zet` sharing service is not implemented yet.
- Real private archives should not be pushed to the public repository.
