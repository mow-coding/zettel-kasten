# Zettel-Kasten MCP Server

This is a minimal stdio MCP server for WOM-kit.

It exposes the local archive through MCP tools so an AI client can inspect and work with a mounted zettel-kasten archive without a web UI.

The MCP tools share zettel listing, reading, draft creation, and view listing logic with the CLI service layer.
Indexing and search also use the same shared service layer.

v0.2.48 radio-frequency recommendation is documentation and sanitized examples only. MCP exposes no recommendation fetch, rank, feed update, selector execution, provider, projection, receipt, or ZET transport tool.

v0.2.49 public release link hygiene is a local development script and test guardrail only. MCP exposes no link checking, GitHub Release editing, network URL fetching, provider, projection, receipt, or archive mutation tool for this batch.

v0.2.56 shared update record review preview exposes only a read-only dry-run MCP tool. MCP cannot write review records, update feeds, trust/import/attest/sign/anchor shared updates, call providers, publish, or run ZET transport.

v0.2.58 shared update record review index exposes only a read-only dry-run MCP tool. MCP requires boolean `dry_run: true`, scans only direct-child local JSON records under an archive-relative directory, and cannot write review indexes, update feeds, trust/import/attest/sign/anchor shared updates, call providers, publish, or run ZET transport.

v0.2.59 ZET transport would-plan exposes only a read-only dry-run MCP tool. MCP requires boolean `dry_run: true`, reuses the single-record review policy, and cannot send/deliver/publish, create keys, create radio-frequency access, create mirroring payloads, write receipts, start queues/workers, update feeds, trust/import/attest/sign/anchor shared updates, call providers, or run ZET transport.

v0.2.60 is a documentation, version, and test checkpoint for the v0.2.x freeze and proposed v0.3.0 entry boundary. MCP exposes no new tool for this boundary and still cannot perform receiver-side renewal writes, real ZET transport, public proof anchoring, DID/wallet/key custody, provider sync, trust mutation, or full-auto behavior.

v0.3.0 adds a CLI-only shared update attestation/review write boundary. MCP intentionally exposes no write/apply/approve sibling tool for this boundary. MCP may still use the existing read-only `zet_shared_update_record_review_preview` and `zet_shared_update_record_review_index` tools.

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

foreign_block_quarantine_decision_check
  Read-only decision-path preview for one existing foreign block quarantine case. This writes no decision and never trusts, imports, mints, attests, anchors, delegates, signs, executes, accepts, or applies the foreign block.

record_quarantine_decision_check
  Read-only dry-run check for a CLI-only quarantine decision record write. It validates a decision preview and current case/receipt state, returns the two paths an approved CLI command would write, and writes nothing.

foreign_block_quarantine_decision_review_index
  Read-only review index for recorded quarantine decisions. This lists safe summaries and optional sanitized decision receipt summaries, writes nothing, and never trusts, imports, mints, attests, anchors, delegates, signs, executes, accepts, applies, shares, or calls providers.
  The `decision` argument filters only the displayed decision summaries. The tool still validates every discovered decision record, decision receipt, current quarantine case, and original quarantine receipt before setting top-level `ok`. `cases` is a case-level projection, not a duplicate of `decisions`.

foreign_block_decision_outcome_plan
  Read-only outcome planner for one recorded quarantine decision. This returns the next safe non-mutating path, writes nothing, and never trusts, imports, mints, attests, anchors, delegates, signs, executes, accepts, applies, shares, calls providers, creates attestations, or runs ZET transport.

foreign_block_attestation_review_candidate_plan
  Read-only candidate planner for human attestation review from an eligible recorded quarantine decision. This writes nothing and never trusts, imports, mints, attests, signs, accepts, shares, calls providers, or runs ZET transport.

record_attestation_review_candidate_check
  Read-only dry-run check for the CLI-only attestation review candidate record write. It validates a candidate plan and current quarantine/decision state, returns the two paths an approved CLI command would write, and writes nothing.

foreign_block_attestation_review_candidate_index
  Read-only review index for recorded foreign block attestation review candidates. It lists safe summaries, validates matching candidate receipts plus upstream quarantine/decision records, writes nothing, and never trusts, imports, mints, attests, signs, accepts, applies, shares, calls providers, or runs ZET transport.

foreign_block_attestation_statement_draft_preview
  Read-only non-binding statement draft preview for one recorded attestation review candidate. It re-reads current candidate, receipt, quarantine, and decision state, writes nothing, and never creates trust, import, attestation, signatures, receipts, minting, sharing, provider calls, or ZET transport.

record_attestation_statement_draft_check
  Read-only dry-run check for the CLI-only attestation statement draft record write. It validates a draft preview and current candidate/quarantine/decision state, returns the two paths an approved CLI command would write, and writes nothing.

foreign_block_attestation_statement_draft_review_index
  Read-only review index for recorded foreign block attestation statement drafts. It lists safe summaries, validates matching statement draft receipts plus upstream candidate/quarantine/decision records, writes nothing, and never trusts, imports, mints, attests, signs, accepts, applies, shares, calls providers, or runs ZET transport.

foreign_block_attestation_statement_draft_decision_preview
  Read-only decision-route preview for one recorded foreign block attestation statement draft. It revalidates the current statement draft review index and upstream metadata chain, writes nothing, records no decision, accepts no draft, and never trusts, imports, mints, attests, signs, publishes, shares, calls providers, or runs ZET transport.

zet_projection_plan_check
  Read-only dry-run projection plan preview for one local zet and one operator-declared surface kind. It writes nothing, emits no full body text, creates no projection receipt, calls no provider, publishes nothing, and runs no ZET transport.

zet_shared_update_record_review_preview
  Read-only dry-run preview for one local archive-contained ZET shared update record JSON before receiver-side renewal. `dry_run` must be boolean `true`; the tool writes nothing, echoes no body text or local absolute paths, blocks true mutation/write/transport/provider/trust flags, and never updates feeds, trusts, imports, attests, signs, anchors, calls providers, writes receipts, projects, or runs ZET transport.

zet_shared_update_record_review_index
  Read-only dry-run review index for direct-child local ZET shared update record JSON files under an archive-relative directory. `dry_run` must be boolean `true`; the tool writes nothing, ignores non-JSON files, reuses the single-record review policy, echoes no body text or local absolute paths, and never updates feeds, trusts, imports, attests, signs, anchors, calls providers, writes receipts, projects, or runs ZET transport.

zet_transport_would_plan
  Read-only dry-run ZET would-transport plan for one local shared update record and one future method: `key-sharing`, `radio-frequency`, or `mirroring`. `dry_run` must be boolean `true`; the tool reuses the single-record review policy, writes nothing, creates no keys, sends nothing, creates no receipts, calls no providers, starts no queues/workers, and never updates feeds, trusts, imports, attests, signs, anchors, mirrors, publishes, or runs ZET transport.

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
- `foreign_block_quarantine_decision_check` is read-only and writes nothing. MCP exposes no quarantine decision apply, write, accept, import, trust, attest, receipt write, auto-accept, auto-import, transport, or full-auto tool.
- `record_quarantine_decision_check` is read-only and writes nothing. Approved quarantine decision recording is CLI-only and requires `--approve --reviewed-by`; MCP exposes no quarantine decision write/apply/accept/import/trust/attest/receipt-write/full-auto tool.
- `foreign_block_quarantine_decision_review_index` is read-only and writes nothing. Its decision filter does not relax consistency validation, and included receipt booleans use direct meanings such as `trust_granted: false` and `provider_api_called: false`. MCP exposes no quarantine decision review apply, write, accept, import, trust, attest, receipt write, auto-accept, auto-import, transport, or full-auto tool.
- `foreign_block_decision_outcome_plan` is read-only and writes nothing. MCP rejects any `dry_run` value other than boolean `true` and exposes no decision outcome apply, write, accept, import, trust, attest, receipt write, auto-accept, auto-import, transport, or full-auto tool.
- `foreign_block_attestation_review_candidate_plan` is read-only and writes nothing. MCP rejects any `dry_run` value other than boolean `true` and exposes no candidate apply, write, accept, import, trust, attest, sign, receipt write, auto-accept, auto-import, transport, or full-auto tool.
- `record_attestation_review_candidate_check` is read-only and writes nothing. Approved attestation review candidate recording is CLI-only and requires `--approve --reviewed-by`; MCP exposes no candidate approve/write/apply/accept/import/trust/attest/sign/receipt-write/full-auto tool.
- `foreign_block_attestation_review_candidate_index` is read-only and writes nothing. Its filters do not relax consistency validation, and included receipt summaries are sanitized. MCP rejects any `dry_run` value other than boolean `true` and exposes no candidate review apply, write, approve, accept, import, trust, attest, sign, receipt write, auto-accept, auto-import, transport, or full-auto tool.
- `foreign_block_attestation_statement_draft_preview` is read-only and writes nothing. MCP rejects any `dry_run` value other than boolean `true` and exposes no statement draft write/apply, foreign block attest/sign/trust/import/accept, receipt write, auto-accept, auto-import, transport, or full-auto tool.
- `record_attestation_statement_draft_check` is read-only and writes nothing. Approved attestation statement draft recording is CLI-only and requires `--approve --reviewed-by`; MCP exposes no statement draft approve/write/apply, foreign block attest/sign/trust/import/accept, mint, anchor, provider sync, or full-auto tool.
- `foreign_block_attestation_statement_draft_review_index` is read-only and writes nothing. Its style and scope filters do not relax consistency validation, `case_id` scopes the verdict to one case, and included receipt summaries are sanitized. MCP rejects any `dry_run` value other than boolean `true` and exposes no statement draft review apply, write, approve, accept, import, trust, attest, sign, receipt write, auto-accept, auto-import, transport, or full-auto tool.
- `foreign_block_attestation_statement_draft_decision_preview` is read-only and writes nothing. MCP rejects any `dry_run` value other than boolean `true`, treats review notes as preview context only, and exposes no decision write/apply, statement draft accept, import, trust, attest, sign, receipt write, WordPress publishing, provider sync, auto-accept, auto-import, transport, or full-auto tool.
- `zet_projection_plan_check` is read-only and requires `dry_run: true`. MCP exposes no projection-plan apply/write, projection receipt write, WordPress publishing, provider publishing, ZET transport, or automatic posting tool.
- `zet_transport_would_plan` is read-only and requires `dry_run: true`. MCP exposes no ZET transport apply/write/send/deliver/publish, key creation, radio-frequency access creation, mirroring delivery, queue/worker, receipt write, provider, trust/import/attest/sign/anchor, or full-auto tool.
- v0.2.48 radio-frequency recommendation is documentation-only. MCP exposes no recommendation fetch/rank/update, selector execution, provider, projection, receipt, or feed mutation tool.
- v0.3.0 shared update attestation/review recording is CLI-only. MCP exposes no boundary apply/write/approve, receiver-side renewal write, public proof anchor, DID/wallet/key custody, transport, provider sync, trust mutation, token, governance, or full-auto tool.
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
- Real pilot apply, restore drill apply, real onboarding apply, profile registration, token registration, external import apply, source registration apply, source scan apply, minting/promotion into canonical `zettels/`, real archive sharing, real ownership transfer, quarantine write/apply, quarantine review apply/accept, quarantine decision write/apply/accept, quarantine decision review write/apply/accept, decision outcome write/apply/accept, attestation review candidate approve/write/apply, attestation review candidate index apply/accept, attestation statement draft write/apply, attestation statement draft review write/apply/approve/accept, attestation statement draft decision write/apply/approve/accept, runtime context apply, WordPress publishing, object storage apply, and external provider account mutation are intentionally not exposed through MCP.
- In Docker Compose, MCP paths are allowlisted to `/archives` through `AI_ARCHIVE_MCP_ALLOWED_ROOTS=/archives`.
- Tool result paths use archive-relative `/` paths so JSON-RPC output is stable across Windows, macOS, and Linux.
