# Zettel-Kasten MCP Server

This is a minimal stdio MCP server for WOM-kit.

It exposes the local archive through MCP tools so an AI client can inspect and work with a mounted zettel-kasten archive without a web UI.

The MCP tools share zettel listing, reading, draft creation, and view listing logic with the CLI service layer.
Indexing and search also use the same shared service layer.

For the full beginner workflow around CLI plus MCP, see:

```text
docs/new-user-flow.md
```

## Transport

The server uses MCP stdio transport:

```text
JSON-RPC 2.0 messages
UTF-8
one JSON message per line
stdin for client-to-server
stdout for server-to-client
stderr reserved for logs
```

This follows the Model Context Protocol stdio transport rule that stdout must contain only valid protocol messages.

## Run

Docker-first:

```bash
docker compose run --rm archive-mcp
```

From `wom-kit/` without installing.

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m wom_kit.mcp_server
```

macOS/Linux shell:

```bash
PYTHONPATH=src python -m wom_kit.mcp_server
```

After editable install:

```powershell
python -m pip install -e .
archive-mcp
```

## Tools

```text
wom_profile_list
  List WOM profile registry entries. This is read-only and redacts registry/archive local paths by default.

wom_profile_resolve
  Resolve a requested WOM profile by exact profile id, label, or alias before runtime-context or draft work. This never registers profiles or stores tokens.

wom_profile_wallet_check
  Preview wallet-ready WOM profile/node identity metadata. This is read-only and never generates keys, signs data, registers wallets, stores secrets, or calls blockchain/provider APIs.

archive_doctor
  Inspect archive health and policy readiness.

archive_runtime_context
  Return read-only runtime context for a mounted archive. This confirms archive id, type/scope, owner/principal summary, AI write policy, archive-relative paths, safe next actions, and doctor summary before draft, dry-run, or mint approval work. Local paths stay redacted unless AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1 is set on the MCP server.

prompt_boundary_check
  Heuristic dry-run prompt-injection boundary check for untrusted text. This never calls LLMs, executes inspected text, approves, mints, calls providers, or writes files.

github_repository_setup_plan
  Plan a private GitHub repository for a resolved WOM profile. This is read-only and never creates repositories, starts OAuth, calls GitHub APIs, runs `gh`, configures git remotes, pushes, or syncs.

object_storage_setup_plan
  Plan private object storage metadata for WOM objets. This is read-only and never creates buckets/containers, starts OAuth, calls provider APIs, uploads, syncs, copies, hashes, or imports source files.

source_intake_plan
  Classify one source/objet locator and return safe draft refs. This is read-only and never reads file bodies, calculates full hashes, copies, uploads, imports, OCRs, transcribes, extracts, calls provider APIs, creates drafts, or mints.

archive_init
  Initialize a personal/company/family archive from safe defaults.

list_zettels
  List canonical and/or draft zettels.

read_zettel
  Read one zettel by id or path.

block_header_check
  Dry-run preview of the derived header for one draft or canonical zet. This returns `block = zet + header` metadata and hashes without writing, minting, reading referenced objet/source file bodies, or calling providers.

foreign_block_intake_check
  Read-only dry-run intake preview for a foreign/shared block-header JSON artifact or Markdown-compatible foreign zet. This keeps the artifact untrusted and never imports, drafts, mints, attests, anchors, applies, calls providers, or writes files.

foreign_block_trust_check
  Read-only dry-run trust/attestation eligibility preview from a foreign-block intake report. This keeps the artifact untrusted, sets no trust, writes no attestations, and never imports, applies, mints, anchors, calls providers, or writes files.

foreign_block_attestation_packet_check
  Read-only dry-run human-review packet preview from a foreign-block trust report. This keeps `trust_state: untrusted_foreign`, sets no trust, writes no attestation or receipt, re-reads no original foreign artifact, and never imports, applies, mints, anchors, calls providers, or writes files.

foreign_block_quarantine_plan
  Read-only dry-run quarantine placement plan from a foreign-block attestation packet preview. This keeps `trust_state: untrusted_foreign`, writes no quarantine files, sets no trust, writes no attestation or receipt, re-reads no original foreign artifact, and never imports, applies, mints, anchors, calls providers, or writes files.

quarantine_foreign_block_check
  Read-only dry-run check for a CLI-only approved quarantine write. This previews the sanitized case and receipt paths but writes nothing. MCP does not expose quarantine write/apply/import/trust/attest/full-auto tools.

foreign_block_quarantine_review_index
  Read-only review index for existing untrusted foreign block quarantine cases. This lists case summaries and optional sanitized receipt summaries, writes nothing, and never trusts, imports, mints, attests, anchors, delegates, signs, executes, accepts, or applies the foreign block.

create_draft_zettel
  Create an AI draft in inbox/. `dry_run: true` previews the draft path, frontmatter, body hash, blockers, warnings, and approval replay values without writing. It may consume structured `source_intake_plan` and `prompt_boundary_report` objects and merge validated metadata into the draft preview. Normal profile-bound AI writes require draft approval plus expected body hash replay values. This does not mint the zettel.

list_views
  List saved views from views/*.yml.

archive_index
  Build a generated local SQLite search index at db/archive-index.sqlite.

archive_search
  Search zettels, object manifest entries, views, and source map entries through the generated index.

archive_onboarding_plan
  Plan beginner-friendly Docker-first onboarding for a new archive. Returns the target folder, provider profile, keyring guidance, doctor plan, blockers, and warnings. This never creates folders or writes files.

real_pilot_plan
  Plan the first real personal/team archive pilot. Returns separation checks, safe first-source suggestions, and first-loop commands. This never creates folders, scans files, or writes files.

archive_preflight_check
  Check an archive before connecting real personal or team data. Returns doctor summary, source-root risk, peer archive separation, and next safe actions. This is read-only.

recovery_plan
  Show local backup and restore readiness. This never writes files or calls external APIs.

restore_drill_plan
  Plan a local restore drill. This never creates a target folder or writes recovery receipts.

external_import_plan
  Plan a Notion or Google Drive export import. Returns proposed inbox drafts, provenance metadata, and receipt preview. This never writes archive files or calls external APIs.

list_sources
  List registered source bindings and current source map status.

source_scan_plan
  Plan a metadata-only scan from a registered source. This never writes source maps or receipts.

source_registration_plan
  Plan source registration. This never writes source-bindings.yml or local profiles.

source_mount_plan
  Show host-native and Docker read-only mount guidance. This never changes files.

promotion_check
  Legacy dry-run check whether an inbox draft can be promoted. Returns checklist status, duplicate hints, and receipt preview. This never writes canonical memory.

mint_zettel_check
  Dry-run check whether an inbox draft zet can be minted. Returns checklist status, duplicate hints, mint receipt preview, and draft snapshot path. This never writes canonical memory, receipts, or snapshots.

share_check
  Dry-run check whether a saved view can be shared with a trusted counterparty. Returns scope gate, trust gate, and receipt preview. This never writes or sends archive data.

delegate_zet_check
  Dry-run check whether zets from a saved view can be delegated. Returns delegate capability preview, scope gate, trust gate, and hashes. `target_policy` may be `counterparty_bound` or `claimable_once`. This never writes or sends archive data.

attest_zet_check
  Dry-run check whether a delegated foreign zet receipt can be attested. Returns attestation receipt preview. This never writes receipts.

anchor_zet_check
  Dry-run check whether an attested foreign zet can be anchored into local meaning. Returns anchor metadata preview. This never writes metadata.

ownership_transfer_check
  Dry-run check whether archive ownership can be transferred. Returns scope gate, trust gate, ownership gate, provider change plan, and schema-shaped receipt preview. This never changes owners or writes receipts.
```

## Safety Defaults

- The server is local stdio only.
- `wom_profile_list`, `wom_profile_resolve`, and `wom_profile_wallet_check` are read-only. They never register profiles, store tokens, generate keys, sign data, register wallets, scan the disk, or write files. They redact local paths unless `AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1` is set on the MCP server and the caller explicitly disables redaction.
- `prompt_boundary_check` is read-only and dry-run-only. It never exposes prompt boundary apply, auto-approve, full-auto, import apply, or real mint behavior.
- `create_draft_zettel` dry-run writes nothing. Normal mode writes only to `inbox/`.
- `create_draft_zettel` accepts a structured `prompt_boundary_report` object, not a local report file path. `low` risk is recorded as heuristic context, `medium` risk is allowed with warnings, and `high` risk blocks draft creation.
- Profile-bound AI draft writes require `draft_approved_by` and `expected_body_sha256`. That approval scope is `inbox_draft_only`; minting remains a separate CLI approval step.
- `archive_init` refuses non-empty target folders.
- `archive_doctor` is read-only.
- `archive_runtime_context` is read-only, uses archive-relative paths by default, and redacts local absolute paths unless `AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1` is set on the MCP server and the caller explicitly disables redaction.
- `github_repository_setup_plan` is read-only and writes nothing. MCP exposes no GitHub apply/create/connect/push/sync tool.
- `object_storage_setup_plan` is read-only and writes nothing. MCP exposes no object storage apply/create/connect/upload/sync tool.
- `source_intake_plan` is read-only and writes nothing. MCP exposes no source intake apply, objet capture, object storage upload, source scan apply, provider API call, automatic draft creation, or mint tool.
- `block_header_check` is read-only and writes nothing. MCP exposes no block header apply, block mint, token, coin, NFT, staking, transport, relay, or provider apply tool.
- `foreign_block_intake_check` is read-only and writes nothing. MCP exposes no foreign block apply, import, trust, attest, auto-accept, auto-import, transport, or full-auto tool.
- `foreign_block_attestation_packet_check` is read-only and writes nothing. MCP exposes no foreign block attestation apply, receipt write, import, trust, attest, auto-accept, auto-import, transport, or full-auto tool.
- `foreign_block_quarantine_plan` is read-only and writes nothing. MCP exposes no foreign block quarantine apply, quarantine write, receipt write, import, trust, attest, auto-accept, auto-import, transport, or full-auto tool.
- `quarantine_foreign_block_check` is read-only and writes nothing. The approved quarantine write path is CLI-only and requires `--approve --reviewed-by`; MCP exposes no quarantine write/apply/import/trust/attest/full-auto tool.
- `foreign_block_quarantine_review_index` is read-only and writes nothing. MCP exposes no quarantine review apply, accept, import, trust, attest, receipt write, auto-accept, auto-import, transport, or full-auto tool.
- `create_draft_zettel` accepts a structured `source_intake_plan` object, not a local plan file path. The plan must be a successful dry-run, blocker-free, metadata-only source intake result before refs are merged.
- `archive_index` writes only the generated search map at `db/archive-index.sqlite`.
- `archive_onboarding_plan` previews first setup but does not create archive folders, provider bindings, or `.env` files.
- `real_pilot_plan` previews the real-use path but does not create personal/team archive folders.
- `archive_preflight_check` is read-only and does not register sources, scan sources, or edit local profiles.
- `recovery_plan` and `restore_drill_plan` are read-only; real restore drill apply remains CLI-only.
- `external_import_plan` previews Notion/Google Drive import batches but does not write inbox drafts or receipts.
- `source_registration_plan` previews source binding additions but does not write `source-bindings.yml` or ignored local profiles.
- `source_mount_plan` returns Docker/host guidance but does not edit Compose files.
- `source_scan_plan` previews source map entries but does not write `source-maps/` or receipts.
- `promotion_check` previews canonical and receipt paths but does not write either file.
- `mint_zettel_check` previews canonical, mint receipt, and draft snapshot paths but does not write any of them.
- `share_check` previews archive sharing but does not write receipts, create workpacks, merge, fork, or send data.
- `delegate_zet_check`, `attest_zet_check`, and `anchor_zet_check` preview the future zet sharing lifecycle, including claimable-once capability binding previews, but do not write receipts, metadata, zettels, workpacks, claim registries, or transport messages.
- `ownership_transfer_check` previews ownership transfer and external provider changes, but does not write receipts or change `archive-identity.yml`.
- Ownership transfer receipt examples can be validated by `archive_doctor` when they live under `receipts/lineage/*.ownership-transfer.json`.
- Real pilot apply, restore drill apply, real onboarding apply, profile registration, token registration, external import apply, source registration apply, source scan apply, minting/promotion into canonical `zettels/`, real archive sharing, real ownership transfer, quarantine write/apply, quarantine review apply/accept, runtime context apply, object storage apply, and external provider account mutation are intentionally not exposed through MCP.
- In Docker Compose, MCP paths are allowlisted to `/archives` through `AI_ARCHIVE_MCP_ALLOWED_ROOTS=/archives`.
- Tool result paths use archive-relative `/` paths so JSON-RPC output is stable across Windows, macOS, and Linux.
