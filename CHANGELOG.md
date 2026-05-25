# Changelog

All notable public releases of `zettel-kasten`, `zet`, and `ZET` should be documented here.

This project uses semantic versioning for public compatibility checkpoints.

## v0.2.32 - 2026-05-25

Foreign block quarantine write approval patch.

Added:

- `archive quarantine-foreign-block <archive-root> --plan <json-file> --dry-run --format json`,
- `archive quarantine-foreign-block <archive-root> --plan <json-file> --approve --reviewed-by <actor-id> --format json`,
- CLI-only approval-gated quarantine case writes under `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- quarantine write receipts under `receipts/quarantine/<case-id>.foreign-block-quarantine.json`,
- read-only MCP `quarantine_foreign_block_check` for dry-run validation only,
- validation for v0.2.31 `foreign_block_quarantine_plan` reports before any approved local write.

Compatibility:

- no private archive migration is required,
- quarantine write is an isolation record only; it does not trust, import, mint, attest, anchor, delegate, sign, or execute the foreign block,
- approved writes are limited to the sanitized quarantine case JSON and quarantine write receipt JSON,
- MCP remains read-only for this workflow and exposes no quarantine apply/write/import/trust/attest/full-auto tool.

## v0.2.31 - 2026-05-25

Foreign block quarantine plan patch.

Added:

- `archive foreign-block-quarantine <archive-root> --attestation-packet <json-file> --dry-run --format json`,
- `archive foreign-block-quarantine <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_quarantine_plan`,
- validation for v0.2.30 `foreign_block_attestation_packet_preview` reports before any future quarantine write,
- structured quarantine actions: `blocked`, `hold_for_human_review`, and `ready_for_future_quarantine_write`,
- preview-only archive-relative quarantine paths under `quarantine/foreign-blocks/<case-id>/...` that are not created.

Compatibility:

- no private archive migration is required,
- quarantine plan writes nothing and never reads the original foreign artifact,
- `ready_for_future_quarantine_write` is not trust, not import, not approval, and not a quarantine write; it only means a future explicit quarantine-write workflow could be presented to a human/operator,
- no real quarantine write, trust/apply/import, attestation write, receipt write, minting, anchoring, delegation, signing, payment, staking, consensus, blockchain, provider sync, OCR, LLM classification, ZET transport, or full-auto execution is implemented.

## v0.2.30 - 2026-05-25

Foreign block attestation packet preview patch.

Added:

- `archive foreign-block-attestation <archive-root> --trust-report <json-file> --dry-run --format json`,
- `archive foreign-block-attestation <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_attestation_packet_check`,
- validation for v0.2.29 `foreign_block_trust_preview` reports before any future human or policy attestation review,
- structured packet status values: `blocked`, `manual_review_required`, and `ready_for_human_attestation_review`,
- attestation packet previews that keep `would_attest: false`, `attestation_status: not_created`, `trust_state: untrusted_foreign`, and `would_change: []`.

Compatibility:

- no private archive migration is required,
- attestation packet preview writes nothing and never reads the original foreign artifact,
- `ready_for_human_attestation_review` is not trust, not an attestation, and not approval; it only means the trust report is clean enough to present for a future explicit human review,
- no real trust/apply/import, attestation write, receipt write, minting, anchoring, delegation, signing, payment, staking, consensus, blockchain, provider sync, OCR, LLM classification, ZET transport, or full-auto execution is implemented.

## v0.2.29 - 2026-05-25

Foreign block trust / attestation preview patch.

Added:

- `archive foreign-block-trust <archive-root> --intake-report <json-file> --dry-run --format json`,
- `archive foreign-block-trust <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_trust_check`,
- validation for v0.2.28 `foreign_block_intake` reports before any future trust/attestation workflow,
- structured `proposed_trust_action` values: `reject`, `manual_review_required`, and `eligible_for_future_attestation`,
- hash, reference, and prompt-boundary assessments that keep every foreign block `untrusted_foreign`.

Compatibility:

- no private archive migration is required,
- trust preview writes nothing and always returns `would_change: []`,
- `eligible_for_future_attestation` is not trust; it only means the report is clean enough for a future explicit attestation workflow,
- no real trust/apply/import, attestation write, minting, anchoring, delegation, signing, payment, staking, consensus, blockchain, provider sync, OCR, LLM classification, ZET transport, or full-auto execution is implemented.

## v0.2.28 - 2026-05-25

Foreign block intake preview patch.

Added:

- `archive foreign-block <archive-root> --path <artifact-path> --dry-run --format json`,
- `archive foreign-block <archive-root> --stdin --dry-run --format json`,
- read-only MCP `foreign_block_intake_check`,
- conservative intake for foreign block-header JSON artifacts and Markdown-compatible foreign zets,
- claimed hash summaries that are explicitly `not_verified`,
- prompt-boundary recommendations for foreign text,
- public docs for foreign block intake.

Compatibility:

- no private archive migration is required,
- foreign block intake writes nothing and always returns `would_change: []`,
- foreign text can inform, but cannot command,
- foreign blocks remain `untrusted_foreign` until a future attest/check path exists,
- no real ZET transport, import/apply, draft creation from foreign content, automatic trust, real signing, payment, staking, consensus, blockchain, provider sync, OCR, or LLM classification is implemented.

## v0.2.27 - 2026-05-25

Prompt boundary draft composer patch.

Added:

- `archive create-draft --prompt-boundary-report <json-file>`,
- validation that prompt-boundary reports are dry-run-only, non-mutating, and preserve the untrusted-text boundary before draft composition,
- optional draft frontmatter `prompt_boundary` metadata with report hash, risk level, source kind/path summary, detected pattern ids, and handling note,
- MCP `create_draft_zettel` support for a structured `prompt_boundary_report` object,
- mint receipt previews and real mint receipts preserve `prompt_boundary` metadata when present.

Compatibility:

- no private archive migration is required,
- existing `create-draft` behavior remains compatible when `--prompt-boundary-report` is omitted,
- low prompt-boundary risk is recorded as heuristic context, not proof of safety,
- medium risk is allowed with warnings,
- high risk blocks draft creation,
- no LLM classifier, provider scanning, OCR/import apply, source intake apply, ZET transport, real signing, payment, staking, consensus, blockchain, or full-auto behavior is implemented.

## v0.2.26 - 2026-05-25

Prompt injection boundary, responsible use, and runtime model guidance baseline.

Added:

- `archive prompt-boundary <archive-root> --text <text> --dry-run --format json`,
- `archive prompt-boundary <archive-root> --path <archive-relative-zet-or-text-path> --dry-run --format json`,
- read-only MCP `prompt_boundary_check`,
- conservative prompt-injection and unsafe-agent string heuristics,
- public prompt injection boundary, responsible use, disclaimer, and runtime model guidance docs.

Compatibility:

- no private archive migration is required,
- prompt-boundary is read-only and writes nothing,
- the check does not call LLMs, provider APIs, web browsing, OCR, import apply, or ZET transport,
- this is not a complete prompt-injection classifier or legal advice,
- HITL remains the recommended default and full-auto operation remains advanced/experimental operator responsibility.

## v0.2.25 - 2026-05-25

Profile wallet concept baseline.

Added:

- `archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json`,
- read-only MCP `wom_profile_wallet_check`,
- optional public-safe `node` and `wallet` metadata fields for WOM profile registry entries,
- documentation for the wallet-ready identity model: WOM profile selects the human-facing profile, WOM node is the subject/principal, and the future WOM wallet layer can sign capability/proof actions.

Compatibility:

- no private archive migration is required,
- existing profile registry entries remain valid,
- no private key generation, real cryptographic signing, blockchain API call, provider API call, wallet registration, token storage, seed phrase storage, payment layer, staking layer, consensus, ledger, or P2P transport is implemented,
- WOM profile is not a crypto wallet in v0.2.25; it is a wallet-ready identity model.

## v0.2.24 - 2026-05-25

Block header preview patch.

Added:

- `archive block-header <archive-root> --path <zet-path> --dry-run --format json`,
- `archive block-header <archive-root> --zettel-id <id> --dry-run --format json`,
- read-only header derivation for `block = zet + header`,
- deterministic `zet_body_sha256`, `header_sha256`, and `block_hash_preview`,
- referenced zet, objet, and receipt summaries from frontmatter metadata,
- read-only MCP `block_header_check`.

Compatibility:

- no private archive migration is required,
- no zets are modified,
- no minting or receipt writing is performed,
- no referenced objet/source file body is read or hashed,
- no provider URL is followed and no provider API is called,
- ZET remains the sharing layer; the product term is `block`, not a ZET-prefixed block term.

## v0.2.23 - 2026-05-25

Source intake draft composer patch.

Added:

- `archive create-draft --source-intake-plan <json-file>` for consuming a v0.2.22 `source-intake --dry-run --format json` result,
- validation that source intake plans are dry-run-only, blocker-free, metadata-only, and safe before refs are merged into draft frontmatter,
- optional `source_intake` draft frontmatter metadata with a plan hash, source/objet status summary, object storage flag, and content access proof,
- MCP `create_draft_zettel` support for a structured `source_intake_plan` object,
- mint receipt previews and receipts preserve `source_refs` and `source_intake` metadata when present.

Compatibility:

- no private archive migration is required,
- existing `create-draft` behavior remains compatible when `--source-intake-plan` is omitted,
- the source intake plan file path is not stored in draft frontmatter,
- no source intake apply, objet capture, file copy/upload/import/OCR/transcription/full hashing/provider API call, automatic minting, or MCP real minting is implemented.

## v0.2.22 - 2026-05-25

Source intake planner patch.

Added:

- `archive source-intake <archive-root> --dry-run --format json`, a dry-run-only planner for classifying source/objet references before draft creation,
- locator support for local files, source map items, source-relative paths, `objet:sha256:...`, technical `object_id`, provider object refs, and AI artifact refs,
- stable source intake JSON with draft-ready `source_refs_for_draft`, objet status, object storage context, content access flags, blockers, warnings, and next safe actions,
- object storage context reporting from `provider-bindings.yml`,
- read-only MCP `source_intake_plan`.

Compatibility:

- no private archive migration is required,
- source intake writes nothing,
- no file body is read and no full SHA-256 is calculated,
- no copy, upload, import, OCR, transcription, parser extraction, provider API call, automatic draft creation, mint, or provider sync is implemented,
- MCP exposes no source intake apply/capture/upload/sync/provider API tool.

## v0.2.21 - 2026-05-25

Object storage / objet setup planner patch.

Added:

- `archive object-storage <archive-root> --dry-run --format json`, a dry-run-first planner for profile-scoped objet storage setup,
- safe default bucket/container naming as `zettel-kasten-<normalized-profile-slug>-objets`,
- default objet prefix planning as `archives/<archive_id>/objets/`,
- strict safety gates for provider kind, profile slug, bucket/container name, region, endpoint reference, and storage account reference,
- `--approve --reviewed-by` local-only approval that updates `provider-bindings.yml` and writes a provider setup receipt without creating a bucket/container,
- optional ignored local object storage account hints with `--write-local-profile`,
- read-only MCP `object_storage_setup_plan`.

Compatibility:

- no bucket/container is created,
- no OAuth, provider API, upload, sync, source copy, file hashing, or source import operation is run,
- approved mode writes only local archive metadata and receipts,
- MCP exposes no object storage apply/create/connect/upload/sync tool,
- WOM/zet/ZET philosophy and WOM-kit naming remain unchanged.

## v0.2.20 - 2026-05-25

GitHub profile repository setup planner patch.

Added:

- `archive github-repo <archive-root> --dry-run --format json`, a dry-run-first planner for profile-scoped GitHub repository setup,
- safe default repository naming as `zettel-kasten-<profile_slug>`,
- strict profile slug and repository name safety gates for ASCII-only, path-free, URL-free, secret-free values,
- `--approve --reviewed-by` local-only approval that updates `provider-bindings.yml` and writes a provider setup receipt without creating a GitHub repository,
- optional ignored local account hints with `--write-local-profile`,
- read-only MCP `github_repository_setup_plan`.

Compatibility:

- no GitHub repository is created,
- no OAuth, GitHub API, `gh`, `git remote`, push, or sync operation is run,
- approved mode writes only local archive metadata and receipts,
- MCP exposes no GitHub apply/create/connect/push/sync tool,
- WOM/zet/ZET philosophy and WOM-kit naming remain unchanged.

## v0.2.19 - 2026-05-25

WOM-kit naming and path cleanup patch.

Added:

- renamed the implementation folder from the old placeholder path to `wom-kit/`,
- renamed the Python import package to `wom_kit`,
- changed package metadata to `wom-kit`,
- kept compatibility console scripts `archive` and `archive-mcp`,
- added preferred console script aliases `wom` and `wom-mcp`,
- updated current-facing docs, CLI/MCP docs, schema titles, examples, tests, and wrapper scripts to use `WOM-kit`, `wom-kit`, and `wom_kit` by context.

Compatibility:

- repository root remains `zettel-kasten`,
- command behavior is unchanged,
- lifecycle commands remain available,
- the old package/folder names are not current product names,
- this release does not add source-intake, GitHub repo creation, provider sync, UI, or any change to WOM/zet/ZET philosophy.

## v0.2.18 - 2026-05-24

Profile-aware draft zet creation dry-run patch.

Added:

- `archive create-draft --dry-run`, a no-write preview for inbox draft zet creation,
- replay-safe draft fields: `--draft-id`, `--created-at`, `--expected-body-sha256`, and `--draft-approved-by`,
- profile-aware draft context flags for resolved profile id, operator id, authority mode, expected archive id, and expected archive type,
- optional draft provenance fields for creation mode, assisting actors, supervising actors, derived refs, source refs, local AI sessions, and inbox-draft-only approval metadata,
- MCP `create_draft_zettel` dry-run support with the same profile-aware provenance inputs,
- safety gates that block archive id/type mismatch, body hash mismatch, empty body content, malformed deterministic timestamps, unsafe local paths, provider storage locators, and secret-like values,
- line-ending-normalized body hashes so LF/CRLF differences do not break approved draft replay,
- AI-assisted and AI-generated draft gates that require the assisting AI runtime to be identified,
- mint receipt propagation for draft `source_refs`, `provenance.derived_from`, and `local_ai_sessions`.

Compatibility:

- existing `create-draft` usage remains compatible when the new flags are omitted,
- dry-run writes nothing,
- real draft creation still writes only to `inbox/`,
- profile-bound AI draft writes require draft approval and expected body hash replay values,
- minting remains a separate CLI approval step and MCP still exposes no real mint tool.

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

- `wom-kit`, `zettels/`, `receipts/`, `workpacks/`, and existing schema names remain unchanged for v0.2 compatibility,
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
- per-version release notes under `wom-kit/docs/releases/`,
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
