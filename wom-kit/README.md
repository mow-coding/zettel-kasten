# WOM-kit v0.2 Draft

WOM-kit is the current implementation toolkit for WOM.

`WOM` stands for `Widesider of Modernity`: a local-first, AI-native, Web3-oriented archive and communication system.

`WOM-kit` is the implementation/tooling layer for running WOM locally with CLI, MCP, and terminal-capable AI runtimes. The repository root remains `zettel-kasten`, and the broader public system remains `WOM`.

It is not a website, SaaS app, dashboard, or visual note-taking product. The interface is an AI runtime such as Codex, Claude Code, or a future local agent. The durable unit of human-readable memory is the `zet`.

## Core Idea

```text
Human talks.
AI drafts and organizes.
zets persist.
Original files stay addressable.
Nodes can delegate, attest, and anchor.
UI is optional.
SaaS is replaceable.
```

The archive has four layers:

1. Original data layer: raw files and external objects.
2. Metadata/relation layer: SQLite and manifests.
3. zet layer: v0.2 Markdown-compatible zets with YAML frontmatter, with the long-term canonical/interchange/rendering target defined by the WOM Safe HTML Profile.
4. View/perspective layer: AI-facing saved filters and context policies.

## Contents

```text
specs/        Public protocol documents.
docs/         Beginner-facing operating and platform notes.
plans/        Implementation plans and handoff notes.
schemas/      JSON Schema documents used by archive doctor.
zettel-kasten/     v0.2 draft zettel-kasten layer: types, actions, and policies.
templates/    Personal, company, and family archive templates.
examples/     Fake sample archives with no private user data.
```

Canonical product terminology is documented in:

```text
docs/concepts/naming-and-terminology.md
docs/concepts/naming-and-terminology.ko.md
docs/concepts/wom-safe-html-profile.md
docs/concepts/wom-safe-html-profile.ko.md
```

v0.1 established the file protocol: specs, templates, and fake examples.

v0.2 starts the zettel-kasten layer:

```text
zettel-kasten/types.yml
zettel-kasten/actions.yml
zettel-kasten/policies.yml
zettel-kasten/zettel-rules.yml
```

These files describe the governed model. The CLI and MCP server enforce a small safe subset; a full policy engine and database migration layer do not exist yet.

Zettel writing and minting lifecycle rules are documented in:

```text
specs/zettel-lifecycle.md
specs/archive-identity.md
specs/archive-lineage.md
specs/source-bindings.md
plans/phase-7-ownership-transfer-plan.md
plans/next-thread-prompt-ownership-lineage.md
zettel-kasten/zettel-rules.yml
```

Beginner-facing operation docs:

```text
docs/docker-first-bootstrap.md
docs/external-imports.md
docs/one-command-setup.md
docs/phase-2-quickstart.md
docs/security-hardening.md
docs/security-audit-2026-05-21.md
docs/new-user-flow.md
docs/source-maps.md
docs/platform-support.md
docs/server-blueprint.md
```

## Minimal CLI

v0.2 includes a small local CLI:

```text
cli/archive.py
```

Current commands:

```text
onboard
  Plan or apply first archive setup. Dry-run writes nothing; --approve creates the archive, provider-bindings.yml, and runs strict doctor.

doctor
  Inspect an archive for missing files, invalid frontmatter, schema problems, manifest problems, unsafe zettel references, and minting-rule warnings.

profile-list
  List a local WOM profile registry without writing files. Local registry and archive paths are redacted by default.

profile-resolve
  Resolve a requested WOM profile by exact profile id, label, or alias before runtime-context or draft work.

profile-wallet
  Preview wallet-ready WOM profile/node identity metadata. Dry-run only; never generates keys, signs data, stores secrets, or calls blockchain/provider APIs.

runtime-context
  Print read-only JSON context for terminal-capable AI runtimes. It confirms archive id, archive type/scope, principal/owner summary, AI write policy, safe archive-relative paths, safe actions, and doctor summary. Local absolute paths are redacted by default.

prompt-boundary
  Check untrusted text for obvious prompt-injection and unsafe-agent strings. Dry-run only; never calls LLMs, executes inspected text, approves, mints, or writes files.

github-repo
  Plan GitHub repository setup for a resolved WOM profile. Dry-run writes nothing. Approved mode writes only local provider metadata and a setup receipt; it does not create GitHub repositories, configure remotes, push, or sync.

object-storage
  Plan object storage setup for WOM objets. Dry-run writes nothing. Approved mode writes only local provider metadata and a setup receipt; it does not create buckets, upload, sync, copy, hash, or import source files.

source-intake
  Classify one source/objet locator before draft creation. Dry-run only; returns safe source refs without reading bodies, hashing, copying, uploading, importing, OCR, transcription, extraction, or provider API calls.

block-header
  Preview a derived block header for one draft or canonical zet. Dry-run only; reads the zet file, derives refs/hashes/provenance/policy/receipt metadata, and writes nothing.

foreign-block
  Preview a foreign/shared block-header JSON artifact or Markdown-compatible foreign zet before any trust/import action. Dry-run only; writes nothing and keeps the artifact untrusted.

foreign-block-trust
  Preview whether a foreign-block intake report should be rejected, manually reviewed, or considered eligible for a future explicit attestation workflow. Dry-run only; writes nothing and keeps the artifact untrusted.

foreign-block-attestation
  Preview a human-review attestation packet from a foreign-block trust report. Dry-run only; writes nothing, creates no trust, writes no attestation, and re-reads no original foreign artifact.

foreign-block-quarantine
  Plan future isolated holding for a foreign block from an attestation packet preview. Dry-run only; writes no quarantine files, receipts, attestations, trust, or imports.

quarantine-foreign-block
  Preview or approve a sanitized local quarantine case write from a foreign-block quarantine plan. Approved mode writes only the quarantine case JSON and quarantine write receipt; it never trusts, imports, mints, attests, anchors, delegates, signs, executes, or accepts the foreign block.

quarantine-review
  List and validate existing foreign block quarantine review cases. Read-only; it writes nothing and does not trust, import, mint, attest, anchor, delegate, sign, execute, accept, or apply the foreign block.

quarantine-decision
  Preview a future decision path for one existing foreign block quarantine case. Dry-run only; it writes no decision and does not trust, import, mint, attest, anchor, delegate, sign, execute, accept, or apply the foreign block.

record-quarantine-decision
  Preview or approve recording a local quarantine decision from a saved decision preview. Approved mode writes only the decision JSON and decision receipt; it never trusts, imports, mints, attests, anchors, delegates, signs, executes, accepts, applies, shares, or calls providers.

quarantine-decision-review
  List and validate recorded foreign block quarantine decisions. Read-only; it writes nothing and does not trust, import, mint, attest, anchor, delegate, sign, execute, accept, apply, share, or call providers.

quarantine-decision-outcome
  Plan the next safe non-mutating path for one recorded quarantine decision. Dry-run only; it writes nothing and does not trust, import, attest, mint, anchor, delegate, sign, execute, accept, apply, share, or call providers.

attestation-review-candidate
  Plan a safe human-review candidate from an eligible recorded quarantine decision. Dry-run only; it writes nothing and does not trust, import, attest, sign, mint, share, call providers, or run ZET transport.

init
  Initialize a personal, company, or family archive from a safe template.

validate
  Run strict archive validation.

list-zettels
  List canonical and/or draft zettels.

read-zettel
  Read one zettel by id or archive-relative path.

create-draft
  Create a draft zettel in inbox/. With --dry-run, preview a profile-aware inbox draft zet without writing files. It can consume a validated source-intake plan with --source-intake-plan and a validated prompt-boundary report with --prompt-boundary-report.

mint-zet --dry-run
  Check whether a draft zet can be minted and preview canonical path, mint receipt, and draft snapshot without writing.

mint-zet --approve --reviewed-by
  Mint an inbox draft zet into canonical private archive memory and write a receipt plus draft snapshot.

mint-zettel
  Transitional compatibility alias for mint-zet.

promote --dry-run
  Legacy-compatible name for the older promotion readiness check.

promote --approve --reviewed-by
  Legacy-compatible command that promotes an inbox draft and writes the older promotion receipt.

index
  Build a generated local SQLite search index at db/archive-index.sqlite.

search
  Search zettels, object manifest entries, views, and source map entries through the generated index.

parcel
  Create a portable parcel from a saved view. The v0.2 compatibility path still writes under workpacks/.

pack
  Transitional compatibility alias for parcel.

admit --dry-run
  Preview admitting a parcel/workpack without mutating the target archive.

import --dry-run
  Transitional compatibility alias for admit.

import-external --dry-run
  Preview a Notion or Google Drive export import without mutating the target archive.

import-external --approve --reviewed-by
  Import Notion or Google Drive export items as inbox drafts and write an import receipt.

share --dry-run
  Legacy-compatible dry-run for the older share language. Product language should prefer delegate.

delegate-zet --dry-run
  Preview scoped zet delegation from a saved view and return a delegate capability receipt preview.

delegate-zet --approve --reviewed-by
  Write a local delegate receipt after the same dry-run gates pass.

attest-zet --dry-run
  Preview attestation of a delegated foreign zet receipt without writing files.

anchor-zet --dry-run
  Preview anchoring an attested foreign zet into local meaning without writing metadata.

check-safe-html --path <zet> --dry-run
  Read-only validator that previews whether a v0.2 Markdown-compatible zet is compatible with a future WOM Safe HTML Profile migration. Blocks <script>, <iframe>, <object>, <embed>, javascript: URLs, and inline event handler attributes. Never writes files.

providers
  Summarize provider-bindings.yml and show manual external-provider change readiness without calling provider APIs.

sources
  Summarize source-bindings.yml and show current source map status.

add-source --dry-run
  Preview registering a new source without hand-editing source-bindings.yml.

add-source --approve --reviewed-by
  Register a new source. Actual local roots may be written only to ignored local profiles.

source-mounts
  Show host-native and Docker read-only mount guidance for registered sources.

recovery-plan
  Show local backup and restore readiness without writing files.

restore-drill
  Plan or run a local restore drill before connecting real sources.

pilot-plan
  Plan a safe first real personal/team archive pilot without writing files.

preflight
  Check an archive before connecting real personal or team data.

scan-source --dry-run
  Preview a metadata-only scan from a registered source without writing files or reading file bodies.

scan-source --approve --reviewed-by
  Write source-maps/*.jsonl plus a source scan receipt after the metadata-only dry-run passes.

transfer-ownership --dry-run
  Preview archive ownership transfer with scope, trust, ownership gates, provider change plan, and a receipt draft.

transfer-ownership --approve --reviewed-by
  Apply archive-internal ownership transfer after dry-run gates pass. External provider account changes remain manual.
```

One-command setup from inside `wom-kit/`:

```powershell
.\scripts\setup-windows.ps1 -DryRun
```

macOS/Linux:

```bash
sh scripts/setup-unix.sh --dry-run
```

These setup scripts check Docker, optionally install or guide Docker with user approval, start Docker when possible, prepare `.env`, run a container doctor smoke test, and start archive onboarding.

The Docker runtime is hardened by default: non-root user, read-only root filesystem, dropped Linux capabilities, no-new-privileges, no runtime network, and `/archives` as the only writable mount.

Lower-level Docker-first bootstrap, after Docker is already ready:

```powershell
.\scripts\install-windows.ps1 -DryRun
docker compose run --rm archive-cli doctor examples/fake-life-archive --strict
docker compose run --rm archive-cli onboard --target-root /archives/personal --type personal --archive-id archive:personal:me --principal-id person:me --dry-run
```

macOS/Linux dry-run setup:

```bash
sh scripts/install-unix.sh --dry-run
```

Host-native developer example:

```powershell
python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive
```

Runtime context example:

```powershell
python wom-kit\cli\archive.py runtime-context wom-kit\examples\fake-life-archive --format json
```

Use `--expected-archive-id` and `--expected-type` when an AI runtime should confirm it is operating on a specific archive. Archive id mismatches block. Archive type mismatches warn by default and block with `--strict`. The command is read-only and writes no files.

Profile registry example:

```powershell
python wom-kit\cli\archive.py profile-resolve `
  --registry wom-kit\templates\profiles\wom-profiles.example.yml `
  --target "영희&철수" `
  --format json
```

Use `profile-resolve` before `runtime-context` when the user asks for a named target profile. This prevents the AI runtime from assuming the current/default personal archive is the target. Missing tokens disable direct write availability and return a delegate fallback preview.

Profile wallet preview example:

```powershell
python wom-kit\cli\archive.py profile-wallet wom-kit\examples\fake-life-archive `
  --registry wom-kit\templates\profiles\wom-profiles.example.yml `
  --profile profile:person:wallet-ready-example `
  --dry-run `
  --format json
```

`profile-wallet` treats a WOM profile as wallet-ready identity context: the profile is the human-facing selector, the WOM node is the subject/principal, and the future WOM wallet layer is where signing/capability authority can later live. v0.2.39 does not generate private keys, sign data, store seed phrases, create wallets, or call blockchain/provider APIs.

Object storage / objet setup example:

```powershell
python wom-kit\cli\archive.py object-storage wom-kit\examples\fake-life-archive `
  --dry-run `
  --provider cloudflare-r2 `
  --profile-id profile:personal:HongGilDong `
  --profile-slug HongGilDong `
  --storage-account-ref storage:account:honggildong `
  --format json
```

The planner proposes a private bucket/container, `archives/<archive_id>/objets/` prefix, safe provider binding metadata, local profile hints, manual setup steps, and a provider setup receipt preview. Dry-run writes nothing. Approved mode writes only local metadata and a receipt; it still does not create buckets, authenticate, call provider APIs, upload, sync, copy, hash, or import source files.

From inside `wom-kit/`, the package can also be tested with:

```powershell
python -m unittest discover -s tests
```

For local package-style execution without installing:

```powershell
$env:PYTHONPATH = "src"
python -m wom_kit.archive_cli doctor examples\fake-life-archive
```

The kit still intentionally does not include a web UI. Notion and Google Drive import start as export/manifest based CLI flows, not live API sync.

`archive index` creates a generated search database:

```text
db/archive-index.sqlite
```

This file is a rebuildable map, not the archive itself. The durable archive still lives in zets, YAML files, object manifests, receipts, and original files. In v0.2, zets remain Markdown-compatible; the long-term target is the WOM Safe HTML Profile.

`archive mint-zet --dry-run` checks the minting gate using `minting_rules` in `zettel-kasten/zettel-rules.yml`, with legacy `promotion_rules` as a v0.2 fallback. It reports blockers, warnings, missing human-review items, near duplicates, the proposed canonical path, the proposed mint receipt path, and the proposed draft snapshot path. It writes nothing. `archive mint-zettel` remains a v0.2 compatibility alias.

`archive source-intake --dry-run` is the safe classification step before drafting from a source/objet. It accepts exactly one locator, returns `source_refs_for_draft`, reports object storage context, and writes nothing. It does not read file bodies, hash, copy, upload, import, OCR, transcribe, extract, call provider APIs, create drafts, or mint.

`archive create-draft --source-intake-plan <json-file>` consumes a successful source-intake dry-run JSON file, validates that it is metadata-only and blocker-free, then merges safe `source_refs_for_draft` into draft `source_refs`. The plan file path is not stored in frontmatter, and WOM-kit does not follow local paths inside the plan.

`archive create-draft --dry-run` is the safe preview step after profile resolution, runtime context, and optional source intake. It returns `lifecycle_action: create_draft`, the target archive summary, proposed `inbox/` path, frontmatter preview, body hash, blockers, warnings, and approval replay values. It writes nothing. For profile-bound AI draft writes, replay requires `--draft-approved-by` and `--expected-body-sha256`; this approval only creates an inbox draft and never mints canonical memory.

`archive block-header --dry-run` previews the header for one existing draft or canonical zet. The model is `block = zet + header`: the zet remains the minimum human-supervised text information unit, and the header is derived from refs, hashes, provenance, policy, source refs, objet refs, and receipts. ZET is the later sharing layer for delegate, attest, and anchor flows; it is not the block itself.

`archive foreign-block --dry-run` previews a shared/foreign block or zet artifact before any trust/import action. It supports WOM-kit block-header JSON and Markdown-compatible foreign zet text. Claimed hashes are reported as `not_verified`; the command never imports, trusts, drafts, mints, attests, anchors, applies, calls providers, or writes files.

`archive foreign-block-trust --dry-run` consumes a saved foreign-block intake report and previews the next safe state: `reject`, `manual_review_required`, or `eligible_for_future_attestation`. Even an eligible result remains `untrusted_foreign`; this command never creates trust or writes an attestation.

`archive foreign-block-attestation --dry-run` consumes a saved foreign-block trust report and previews a future human-review packet. It preserves `trust_state: untrusted_foreign`, `attestation_packet_preview.would_attest: false`, `attestation_packet_preview.attestation_status: not_created`, and `would_change: []`. It never creates trust, writes attestations, writes receipts, imports, mints, anchors, delegates, signs, calls providers, executes foreign text, or reads the original foreign artifact again.

`archive foreign-block-quarantine --dry-run` consumes a saved foreign-block attestation packet preview and plans future isolated holding paths under `quarantine/foreign-blocks/<case-id>/...`. It preserves `trust_state: untrusted_foreign`, `quarantine_plan.would_quarantine: false`, `quarantine_write_status: not_created`, and `would_change: []`. It never creates quarantine files, trust, imports, attestations, receipts, mints, anchors, delegates, signs, calls providers, executes foreign text, or reads the original foreign artifact again.

`archive quarantine-foreign-block --dry-run` consumes a saved foreign-block quarantine plan and previews the first approved isolation write. `archive quarantine-foreign-block --approve --reviewed-by <actor-id>` writes only `quarantine/foreign-blocks/<case-id>/quarantine-case.json` and `receipts/quarantine/<case-id>.foreign-block-quarantine.json`. It keeps `trust_state: untrusted_foreign` and does not create trust, imports, attestations, canonical zets, mints, anchors, delegates, signatures, provider calls, or executable actions.

`archive quarantine-review --format json` reads existing `quarantine/foreign-blocks/<case-id>/quarantine-case.json` files and matching quarantine receipts as a review index. Use `--case-id <safe-id>` for one case and `--include-receipts` for sanitized receipt summaries. The index is read-only and does not import, trust, accept, attest, mint, anchor, delegate, sign, execute, or apply the foreign block.

Preview a future quarantine decision path without recording it:

```powershell
python wom-kit\cli\archive.py quarantine-decision wom-kit\examples\fake-life-archive `
  --case-id case-review-001 `
  --dry-run `
  --format json
```

The preview can propose `keep_quarantined`, `reject_and_keep_record`, `eligible_for_attestation_review`, or `needs_more_review`. It is a decision aid only. It writes no decision and does not import, trust, attest, mint, anchor, delegate, sign, execute, accept, or apply the foreign block.

Record an approved local quarantine decision after reviewing a saved decision preview:

```powershell
python wom-kit\cli\archive.py record-quarantine-decision wom-kit\examples\fake-life-archive `
  --decision-preview workbench\foreign-block-quarantine-decision.json `
  --approve `
  --reviewed-by person:me `
  --format json
```

Approved mode writes exactly `quarantine/foreign-blocks/<case-id>/quarantine-decision.json` and `receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json`. The command re-validates the current quarantine case and receipt before writing, stores only review-note summary metadata, and keeps the foreign block untrusted and unimported.

Review recorded quarantine decisions:

```powershell
python wom-kit\cli\archive.py quarantine-decision-review wom-kit\examples\fake-life-archive `
  --format json
```

Use `--case-id <safe-id>` for one recorded decision, `--decision <decision-or-all>` for a displayed decision filter, and `--include-receipts` when the reviewer needs sanitized decision receipt summaries. The index still validates every discovered record before setting top-level `ok`, writes nothing, and keeps every foreign block untrusted.

Plan the next safe path from one recorded quarantine decision:

```powershell
python wom-kit\cli\archive.py quarantine-decision-outcome wom-kit\examples\fake-life-archive `
  --case-id case-review-001 `
  --dry-run `
  --format json
```

The outcome planner re-reads the current quarantine case, original quarantine receipt, decision record, and decision receipt. It only returns `planned_not_applied` routing such as `keep_quarantined`, `reject_and_keep_record`, `needs_more_review`, or `prepare_attestation_review_candidate`.

Plan a human attestation review candidate from an eligible decision:

```powershell
python wom-kit\cli\archive.py attestation-review-candidate wom-kit\examples\fake-life-archive `
  --case-id case-review-001 `
  --expected-decision eligible_for_attestation_review `
  --expected-outcome prepare_attestation_review_candidate `
  --dry-run `
  --format json
```

The candidate planner re-reads the current quarantine case, original quarantine receipt, decision record, and decision receipt. It returns `candidate_status: planned_not_recorded`, `attestation_status: not_created`, and keeps every mutation flag false.

Real minting is CLI-only and intentionally explicit:

```powershell
python wom-kit\cli\archive.py mint-zet wom-kit\examples\fake-life-archive `
  --path inbox\zet_20260519_draft_ai_lunch_note.md `
  --approve `
  --reviewed-by person:me
```

Real minting reuses the dry-run checks as a gate. Blockers always stop the command. Warnings require `--allow-warnings`. The original inbox draft is preserved. The command writes the canonical zettel under `zettels/`, a mint receipt under `receipts/mint/`, and the exact mint-time draft snapshot under `receipts/mint/drafts/`. The older `archive promote` command remains available for compatibility.

`archive parcel` creates a portable slice under `workpacks/` using a saved view. The first implementation copies selected zettel files and writes object manifest metadata, but it does not copy original object files by default. `archive pack` remains a v0.2 compatibility alias.

`archive admit --dry-run` previews target inbox writes, object manifest merges, conflicts, and an admit/import receipt. Real parcel/workpack admit remains unavailable until the dry-run path is proven safer. `archive import --dry-run` remains a v0.2 compatibility alias.

`archive import-external --source notion --export <folder> --dry-run` previews a Notion Markdown export import. `archive import-external --source google_drive --export <manifest.json> --dry-run` does the same for Google Drive exports. Approved imports write inbox drafts and `receipts/import/*.external-import.json`; they do not call Notion or Google Drive APIs or store OAuth secrets.

`archive share --dry-run` is the legacy dry-run for the older share language. It previews a GitHub-like archive share from a saved view, shows which zettels are included or excluded, blocks sensitive categories by default, verifies the target counterparty fingerprint against `archive-identity.yml`, and writes nothing. Product design should prefer `delegate-zet`.

`archive delegate-zet --dry-run` previews scoped zet delegation from a saved view. `archive delegate-zet --approve --reviewed-by <actor>` writes a `dry_run:false` delegate receipt under `receipts/delegate/` after the same gates pass. It does not send data, write attestations, write anchors, or create claim/spent registries.

`archive onboard --dry-run` previews first setup for a new personal, family, or company archive. It shows the folder to create, selected provider profile, keyring guidance, and doctor plan. It writes nothing.

`archive onboard --approve` creates the archive, writes or adjusts `provider-bindings.yml` from the selected provider profile, and runs strict doctor. This is the beginner-friendly setup path used by the Docker-first flow.

`archive pilot-plan` is the bridge from fake examples to real use. It plans a private personal life archive and a separate team/company archive, checks that their roots and ids do not overlap, and suggests first sources for local folders, SSDs, Notion exports, Google Drive exports, and object manifests. It writes nothing.

`archive preflight` is the real-data safety check. It runs doctor diagnostics, checks local profile/source-root risk, catches too-broad source roots such as drive roots or home folders, can compare personal/team archive separation with `--peer-archive`, and can check Docker readiness with `--check-docker`.

`archive recovery-plan` explains what the archive can restore locally and what remains external. `archive restore-drill --approve --reviewed-by <actor>` copies the archive control plane to a clean target, runs strict doctor, rebuilds the SQLite index, performs a basic search smoke test, and writes `receipts/recovery/*.restore-drill.json`. It does not copy PC/SSD/SaaS/object-storage originals.

`archive transfer-ownership --dry-run` previews a family-to-child, company-to-spinout, or similar archive ownership transfer. It verifies the proposed new owner through the trust gate, checks the current owner/operator approval actors through the ownership gate, previews the receipt path under `receipts/lineage/`, includes a `provider_change_plan`, and writes nothing.

`archive transfer-ownership --approve --reviewed-by <actor>` applies the archive-internal ownership transfer after the same gates pass. It updates `archive-identity.yml`, appends compact lineage metadata, and writes a `dry_run:false` receipt. It does not call GitHub, Cloudflare R2, Backblaze B2, Neon, rclone, restic, or KeePassXC APIs; those external account changes remain manual and are listed in the provider change plan.

`archive providers` reads `provider-bindings.yml` and summarizes the external services attached to an archive. Provider bindings store env var names and keyring references only, never token or password values.

Ownership transfer receipt previews are schema-backed by `schemas/ownership-transfer-receipt.schema.json`. `archive doctor` validates `receipts/lineage/*.ownership-transfer.json`, so example receipts can be checked without enabling real transfer.

Keyring/profile support is still a safety baseline, not a full OS keyring integration. Local profile files should live under ignored paths such as `profiles/local/`, `keyrings/local/`, or `.archive-local/`. `archive doctor` warns about missing ignore protection and fails on obvious secret-like files or values.

`archive doctor` includes schema-backed validation for:

```text
archive.yml
archive-identity.yml
provider-bindings.yml
zettel frontmatter
objects/manifests/files.jsonl
views/*.yml
workpacks/*/package.yml
receipts/lineage/*.ownership-transfer.json
receipts/import/*.external-import.json
receipts/recovery/*.restore-drill.json
receipts/mint/*.mint.json
receipts/delegate/*.delegate.json
zettel-kasten/*.yml
```

The schema files live in:

```text
schemas/
```

## Platform Support

WOM-kit is Docker-first hybrid. Non-programmer users can stay on Windows or macOS, while the default runtime runs inside a Linux container through Docker Compose. Host-native Python remains available for developers and backup paths.

Archive-internal paths returned by CLI JSON and MCP tools use stable `/` relative paths such as:

```text
inbox/zet_example.md
objects/manifests/files.jsonl
```

See:

```text
docs/phase-2-quickstart.md
docs/docker-first-bootstrap.md
docs/external-imports.md
docs/one-command-setup.md
docs/real-pilot-preflight.md
docs/security-hardening.md
docs/security-audit-2026-05-21.md
docs/threat-model.md
docs/new-user-flow.md
docs/platform-support.md
```

## Next Implementation Plan

Earlier promotion work is tracked in:

```text
plans/phase-3-implementation-plan.md
plans/phase-4-lineage-trust-plan.md
```

Phase 2 is complete for the safe local toolkit subset. Phase 3 added real promotion. v0.2.8 added the product-facing minting lifecycle with canonical zettel, mint receipt, and draft snapshot outputs. v0.2.9 stabilizes minting terminology while preserving promotion compatibility. v0.2.10 adds dry-run `delegate-zet`, `attest-zet`, and `anchor-zet` lifecycle previews. v0.2.11 adds the delegate capability contract with `counterparty_bound` and `claimable_once` dry-run policies. v0.2.12 adds CLI-only real delegate receipt writes. v0.2.13 adds the WOM naming baseline and compatibility-safe aliases: `mint-zet`, `parcel`, and `admit`. v0.2.14 records the `WOM`/`zet`/`ZET` distinction and defines the WOM Safe HTML Profile as a compatibility-safe documentation baseline. v0.2.15 adds `archive check-safe-html --dry-run` as a read-only CLI validator that previews WOM Safe HTML Profile compatibility for v0.2 Markdown-compatible zets. v0.2.16 adds the read-only WOM AI Runtime Context Layer so terminal-capable AI runtimes can confirm archive identity, type, paths, write policy, and safe actions before drafting or mint approval. v0.2.17 adds the read-only WOM Profile Registry dry-run layer so AI runtimes resolve the requested target profile before assuming the default archive. v0.2.18 adds profile-aware `create-draft --dry-run` and replay-safe inbox draft creation for AI runtimes. v0.2.19 renames the implementation/tooling layer to WOM-kit with `wom-kit/` and `wom_kit`. v0.2.20 adds a dry-run-first GitHub repository setup planner for WOM profiles with local-only approval metadata. v0.2.21 adds a dry-run-first object storage / objet setup planner for WOM profiles with local-only approval metadata. v0.2.22 adds dry-run-only source intake planning before draft creation. v0.2.23 lets `create-draft` consume validated source-intake dry-run plans without re-reading source files. v0.2.24 adds read-only block header previews for `block = zet + header`. v0.2.25 adds the WOM profile wallet concept baseline and read-only `profile-wallet` previews. v0.2.26 adds prompt injection boundary, responsible use, and runtime model guidance plus read-only `prompt-boundary` checks. v0.2.27 lets `create-draft` consume validated prompt-boundary reports and preserve the untrusted-text boundary in draft metadata and mint receipts. v0.2.28 adds read-only foreign block intake previews before any trust/import action. v0.2.29 adds read-only foreign block trust / attestation previews from intake reports. v0.2.30 adds read-only foreign block attestation packet previews for future human review without creating trust or receipts. v0.2.31 adds read-only foreign block quarantine plans for future isolated holding without writing quarantine files. v0.2.32 adds CLI-only approved foreign block quarantine case and receipt writes while keeping the foreign block untrusted and unimported. v0.2.33 adds a read-only foreign block quarantine review index for existing untrusted cases and receipt consistency checks. v0.2.34 adds read-only foreign block quarantine decision previews for candidate future decision paths without recording decisions. v0.2.35 adds CLI-only approved quarantine decision records and receipts while keeping the foreign block untrusted and unimported. v0.2.36 adds a read-only quarantine decision review index for recorded decisions and receipts. v0.2.37 adds a read-only decision outcome planner for one recorded decision without applying trust, import, acceptance, or attestation. v0.2.38 adds a read-only attestation review candidate planner for eligible recorded decisions. v0.2.39 adds CLI-only approved attestation review candidate records and receipts while keeping the foreign block untrusted and without creating attestations or signatures. Phase 4 adds the lineage/trust dry-run baseline and the first owner/operator identity model. Phase 7B adds CLI-only real ownership transfer plus provider change planning. Phase 8B adds one-command setup orchestration above the Docker-first runtime. Phase 8C hardens the local installer and container runtime. Phase 9 starts Notion and Google Drive export import. Real parcel/workpack import, real share/merge/fork, live external provider API sync, OS keyring integration, UI, Markdown-to-WOM-Safe-HTML conversion, profile registration, token storage, wallet creation, real signing, source content import, foreign block import/trust/apply, foreign attestation writes, quarantine review apply/accept, quarantine decision accept/apply/trust, decision outcome apply/accept, attestation review candidate accept/apply, object storage upload/sync, source intake apply/capture, complete prompt-injection prevention, full-auto execution, ZET transport, token mechanics, and CI matrix remain future work.

v0.2.38 adds a read-only attestation review candidate planner for eligible recorded decisions. It prepares human-review metadata only and does not create trust, signatures, attestations, imports, minting, sharing, provider calls, or ZET transport.

v0.2.39 adds CLI-only attestation review candidate recording after a valid v0.2.38 candidate plan. Dry-run writes nothing; approved mode writes exactly one untrusted candidate record and one matching receipt. It still does not create trust, signatures, attestations, imports, minting, sharing, provider calls, or ZET transport.

## Minimal MCP Server

v0.2 includes a minimal stdio MCP server:

```text
src/wom_kit/mcp_server.py
```

Run from inside `wom-kit/` without installing:

```powershell
$env:PYTHONPATH = "src"
python -m wom_kit.mcp_server
```

After editable install:

```powershell
archive-mcp
```

Initial tools:

```text
wom_profile_list
wom_profile_resolve
wom_profile_wallet_check
archive_doctor
archive_runtime_context
prompt_boundary_check
github_repository_setup_plan
object_storage_setup_plan
source_intake_plan
block_header_check
foreign_block_intake_check
foreign_block_trust_check
foreign_block_attestation_packet_check
foreign_block_quarantine_plan
quarantine_foreign_block_check
foreign_block_quarantine_review_index
foreign_block_quarantine_decision_check
record_quarantine_decision_check
foreign_block_quarantine_decision_review_index
foreign_block_decision_outcome_plan
foreign_block_attestation_review_candidate_plan
record_attestation_review_candidate_check
archive_init
list_zettels
read_zettel
create_draft_zettel
list_views
archive_index
archive_search
promotion_check
mint_zettel_check
share_check
delegate_zet_check
attest_zet_check
anchor_zet_check
ownership_transfer_check
```

The MCP server is intentionally local and stdio-only. It exposes `wom_profile_list`, `wom_profile_resolve`, `wom_profile_wallet_check`, `archive_runtime_context`, `prompt_boundary_check`, `github_repository_setup_plan`, `object_storage_setup_plan`, `source_intake_plan`, `block_header_check`, `foreign_block_intake_check`, `foreign_block_trust_check`, `foreign_block_attestation_packet_check`, `foreign_block_quarantine_plan`, `quarantine_foreign_block_check`, `foreign_block_quarantine_review_index`, `foreign_block_quarantine_decision_check`, `record_quarantine_decision_check`, `foreign_block_quarantine_decision_review_index`, `foreign_block_decision_outcome_plan`, `foreign_block_attestation_review_candidate_plan`, and `record_attestation_review_candidate_check` as read-only, and exposes `mint_zettel_check`, legacy `promotion_check`, `share_check`, `delegate_zet_check`, `attest_zet_check`, `anchor_zet_check`, and `ownership_transfer_check` as dry-run only. `create_draft_zettel` can dry-run without writing, can consume structured `source_intake_plan` and `prompt_boundary_report` objects, and normal profile-bound AI writes require draft approval plus expected body hash replay values. It does not expose real profile registration, token registration, wallet registration, key generation, real signing, real minting, block minting, token or coin mechanics, legacy real promotion, real delegate writes, real sharing, real claim registries, real attestation writes, real anchoring writes, real merge, real fork, real ownership transfer, foreign block apply/import/trust/quarantine writes, quarantine review apply/accept, quarantine decision apply/accept/write through MCP, quarantine decision review apply/accept/write through MCP, decision outcome apply/accept/write through MCP, attestation review candidate approve/apply/write through MCP, foreign attestation writes, prompt boundary apply, auto-approve, full-auto, source intake apply/capture/upload/sync, or object storage apply/create/connect/upload/sync tools; AI-created zettels go to `inbox/`. The ownership transfer check includes a provider change plan, but MCP still cannot apply local ownership changes or external provider account changes.

Archive ownership is separate from archive operation. A family, company, or other group can own an archive while named people operate it. For example, parents can operate a child-related archive under a family owner, and a later receipt-backed transfer can move ownership to the child.

## Safety Defaults

- AI writes drafts to `inbox/` by default.
- Canonical zettels live in `zettels/` and require explicit human minting or legacy promotion.
- Zettels reference original files by `object_id`, not provider URLs.
- Object storage providers are replaceable through manifests.
- External provider accounts are described in `provider-bindings.yml` with env/keyring references, not secrets.
- Objet storage setup can be planned locally, but bucket creation, upload, sync, copy, hashing, source intake apply/capture, and source import remain outside WOM-kit v0.2.39.
- Profile wallet readiness can be previewed locally, but private key custody, wallet creation, real signing, blockchain integration, and payment/economic layers remain outside WOM-kit v0.2.39.
- Foreign block intake, trust preview, attestation packet preview, quarantine plan, quarantine review index, quarantine decision preview, quarantine decision review index, decision outcome plan, and attestation review candidate plan are inspect-only; CLI quarantine write records an isolated untrusted case and receipt, CLI quarantine decision write records only an operator-reviewed local decision and receipt, and CLI attestation review candidate write records only an untrusted candidate and receipt. Foreign block import, trust, drafting, minting, attesting, anchoring, applying, quarantine decision acceptance, decision outcome acceptance, attestation review candidate acceptance/apply, transport, and automatic acceptance remain outside WOM-kit v0.2.39.
- Prompt boundary checks and prompt-boundary draft metadata are heuristic guardrails only; complete prompt-injection prevention, LLM classification, provider scanning, OCR/import apply, and full-auto safety guarantees remain outside WOM-kit v0.2.39.
- Ownership transfer can update the archive identity locally, but external provider permissions remain manual until a future explicit integration.
- Provenance and visibility fields are mandatory in shared or derived records.
- Local profiles and secrets are ignored by default.
- Archive sharing requires scope and trust dry-runs before any future real write path.
- `archive doctor` flags common accidental secret files such as `.env`, private keys, credential exports, and secret-like values.
