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

<!--
Maintenance contract (decision log 2026-07-03, v0.3.161): per release, update
ONLY (1) the current-baseline line in the code block below, (2) the single
previous-baseline line, and (3) for feature releases, at most ONE thematic
bullet under "What Exists Today". Release history lives in CHANGELOG.md and
wom-kit/docs/releases/ - do not re-grow baseline ladders or tag lists here.
-->

Current public baseline:

```text
v0.3.170 pre-release
```

Previous public baseline: v0.3.169 pre-release.

Full release history: see [CHANGELOG.md](CHANGELOG.md) and [wom-kit/docs/releases/](wom-kit/docs/releases/).

This repository is a public showcase and reference implementation workspace. It is not production-ready yet.

Roadmap snapshot: `v0.1.x` was the idea/protocol-language line, `v0.2.x`
was the first local implementation line, `v0.3.x` is the current WOM real-use
feedback and safety-hardening line, `v0.4.x` is planned for the custom UI
control layer, and `v0.5.x` is planned for ZET real-use feedback. See the
[WOM Product Roadmap](wom-kit/docs/product-roadmap.md) for the phase gates and
future-only boundaries.

## What Exists Today

Shipped surfaces, grouped by theme. Each bullet is one shipped capability; for
the status-by-capability view (real implementation, read-only preview,
approval-gated write, or docs-only), see the
[WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md).

### Archive core & lifecycle

- a public WOM/zet/ZET design baseline with specs, schemas, fake archives, release notes, and work logs,
- a public version-line roadmap that explains how the pre-1.0 minor lines map to idea, implementation, WOM feedback, UI/control-layer, and ZET feedback phases,
- WOM-kit local CLI and MCP tooling under `wom-kit/`, importing as `wom_kit`,
- private archive lifecycle tools for doctor checks, draft creation (with forward-only draft-id hygiene so a titleless or Hangul-only title no longer yields a misleading `_draft` id, and draft-time `--kind` validation that warns and lists valid kinds), minting with dry-run checklist guidance and an attributed `--affirm` flag that satisfies the two human-review checklist items via an audited, reviewer-attributed CLI act instead of a raw YAML edit (recorded in the mint receipt, inert without `--reviewed-by`, never overriding machine-enforced items), verified minted-draft retirement, delegation, receipts, search, and metadata review,
- honest `archive remint-reconcile` (and the sibling `archive retire-draft-reconcile` for retire receipts) that re-issues a receipt's recorded sha256 after a zet drifts on disk (a CRLF/BOM re-checkout or a human content edit): it classifies the drift as newline/BOM-only `format_drift` or `content_change` even when the draft snapshot itself drifted — checking every content frontmatter field (a full-field reconstruction plus an `id`/`title` cross-check against the mint receipt) so an edit to any field, or a content-tampered snapshot, can never anchor `format_drift` — always shows the on-disk content, requires a reviewer to approve, offers an opt-in `--strip-bom` that never bypasses the content-change ack gate, never masks corruption, and writes both an in-place receipt update and a separate immutable audit receipt,
- generated-index-backed duplicate checks, metadata-backed mint staleness fast paths, SQLite busy-timeout/WAL hardening for generated-index write paths, and standard-id source-path fast resolution for large archives,
- scoped `validate --since` / `validate --scope` checks with generated-index body SHA cache support and optional `--progress`,
- read-only `archive zet-quality-check --dry-run` for entity-term, document-type, OCR/parse metadata, table-structure, correction-event, source-rights, audience, and derived-artifact dependency risks before mint; optional `zet-quality-rules.yml` project rules can make forbidden entity aliases mint blockers without echoing matched terms,
- read-only `archive status-board --dry-run` for beginner-facing archive state counts across canonical zets, active drafts, minted drafts pending retire, document/audience metadata gaps, source metadata gaps, derived-artifact sync gaps, and optional body-inspecting quality counts without echoing titles, bodies, source values, provider URLs, or local paths,
- read-only `archive derived-artifact-staleness --dry-run` for checking whether declared `derived_artifacts` may be stale because a source zet is newer than the artifact's last reviewed sync. It writes nothing, opens no external report, and does not echo artifact refs, titles, bodies, provider URLs, or local paths,
- a v0.2.x freeze / v0.3.0 entry boundary document plus a narrow v0.3.0 write boundary that stays local-first and body-safe,

### Capture & intake

- human-guided project intake planning, decision receipts, source-intake context, and objet-capture receipt gates,
- a normative AI intake protocol on every runtime-visible surface (AGENTS.md templates, the runtime SKILL.md, and the skill/plugin layer doc),
- source-intake dry-run BEFORE physically copying any local file into the archive or an objet store, with in-archive `staging/incoming/` capture staging as the canonical intake location (D2),
- reviewed selection -> approved capture as the only capture authority, plus prehashed-ledger evidence for bulk external stores,
- two additive read-only doctor guards (`archive_objets_layout_noncanonical` for a raw in-root `objets/` folder with a documented migration guide, and `workspace_objet_store_git_exposure` when an objet byte store may be tracked by an enclosing git working tree) plus the anchored `/objets/` `.gitignore` safe default,
- paired transcript intake through `archive objet-capture-selection --derived-text-staged-path`: one reviewed selection manifest approves both a staged original and its already-extracted transcript (raw-byte `approved_text_sha256` commitment, full staged-path-parity confinement),
- one `archive objet-capture` run that publishes the original and registers the derived text bound to the minted object_id, with additive item/run `status_class` (`partial` = original durable, derived retriable),
- BOM-aware derive-text decoding (BOM-marked UTF-8/UTF-16 stored as BOM-less UTF-8 with raw-byte provenance; UTF-32 and BOM-less non-UTF-8 block deterministically),
- owner-approved real-archive objet capture enablement through `archive objet-capture-enable`: a read-only dry-run eligibility report and an approval-gated singleton `ops/capture-enablement.yml` consent record with a receipt trail, so a real (non-sandbox) archive can run local objet capture only after explicit, receipted, revocable owner consent,
- explicit never-touch name acknowledgment, forward-only revocation with `--reenable` protection, and doctor visibility for that consent record; the record is a consent marker in the same write-trust domain, not a security boundary,
- read-only derived-text coverage/toolchain/doctor/agent-contract gates, manifest-scoped completeness signals, and manifest-quality checks that block false complete claims when `tool_version` or required extraction metadata is missing,
- existing derived-text records as a fallback textual signal for older prehashed manifests, plus non-echoed tool-hint paths for PATH-missing local extractors,
- approval-gated single-file and JSONL batch derived text capture for registering already extracted parser/OCR/ASR/vision text against source objets,

### Retrieval & views

- read-only preview layers for runtime context, profiles, source/objet intake, overview-first zet reading, block headers with first-read summaries, and prompt boundaries,
- generated index health checks, saved view health, facet role diagnostics, saved view recommendations,
- read-only objet reference resolution, presigned URL planning, and zettel objet link previews for mapping `sha256:<hex>` refs to safe local/external candidates,

### Sharing & ZET previews

- read-only previews for foreign block review, projection planning with supported-surface help, shared update review/index, shared update route pointers, and ZET would-transport planning,
- approval-gated local write paths for selected private archive, foreign-block review records, and the first v0.3.0 shared update attestation/review record,

### Privacy & redaction

- zet self-contained checks and AI scratch lifecycle management: public external citation URLs may stay in zet bodies or `source_refs`, private provider locators and original-file locations still require durable WOM refs, `.wom-scratch/` and `workbench/ai-scratch/` are ignored scratch areas, and approved mint can remove explicit scratch refs from the canonical zet while consuming those scratch files through a cleanup receipt,
- read-only `archive secret-signal-taxonomy --dry-run` for AI operators that need to distinguish harmless secret/credential/token concept words and safe refs from actual secret-like values, private locators, account identifiers, or unknown sensitive context,

### AI-operator contracts & runtime handoff

- read-only WOM-kit version truth-source checks through `archive --version`, `archive version --format json`, parent project installed-version pin discovery from archive roots, and runtime-context version metadata,
- read-only `archive capabilities --machine` for AI operators that need a stable `ok/state/summary/data/blockers/warnings` envelope listing the executable local CLI commands, aliases, required positionals, options, nested subcommands, and local release identity without calling GitHub or providers,
- read-only `archive operator-feedback-plan --dry-run` and approval-gated `archive operator-feedback-record --approve` for tracking operator-generated tool feedback under `ops/feedback/` with draft/delivered/acknowledged/resolved/archived lifecycle metadata, plus read-only `archive operator-feedback-ledger --dry-run` (aliases `feedback-ledger`, `feedback-board`) that aggregates delivery-status counts + a pending list and approval-gated `archive operator-feedback-mark-delivered --approve` that batches the draft->delivered boundary with a `delivered_at` stamp and a single receipt, all without reading feedback bodies, echoing feedback refs/titles, submitting externally (metadata only; `delivered` is the operator's own mark, not proof of external delivery), or mixing feedback lifecycle state into user knowledge `objets/`,
- read-only `archive approval-handoff-plan --dry-run` and approval-gated `archive approval-handoff-record --approve` for AI-to-human approval handoff metadata under `ops/approval-handoffs/`, so sensitive operations can stop at a clear needs_review/approved_once/denied/superseded/resolved state without executing the operation, reading private material, calling providers, or echoing target/action values,
- read-only `archive approval-handoff-audit --dry-run` for checking a handoff record before a future operation uses it as approval evidence, without executing the operation or echoing target/action values,
- read-only `archive operation-status-taxonomy --dry-run` for AI operators that need to distinguish succeeded/preview/written/no_change from partial/truncated/blocked/failed results before telling a human that work is complete,
- read-only `archive input-provenance-taxonomy --dry-run` for AI operators that need to distinguish tool-discovered and receipt-verified inputs from caller-supplied, AI-generated, fixture, environment-inferred, or unknown inputs before treating them as source truth,
- read-only `archive ai-response-contract --dry-run` for AI operators that need a conversational status-board contract before answering a human: outcome, evidence basis, privacy/approval boundary, remaining work, and no web UI requirement,
- core read-only operator commands now expose top-level `status_class`, `input_provenance_class`, `secret_signal_class`, and `operator_envelope` fields so AI operators can apply the response contract without inferring those classes from prose,
- runtime-context canonical entrypoint metadata so AI runtimes can see which archive-relative files/directories to treat as start-here and authoritative sources, plus machine-readable `ai_runtime_order`, `recommended_first_commands`, and `material_link_routes` that hand off from `runtime-context` to `AGENTS.md` and `ai-response-concept-guide`,
- AI operational context rehydration through `ops/operational-context.yml`, runtime-context field `operational_context`, and approval-gated `archive operational-context` updates with receipts, so an AI runtime can recover mission, scope, state, gotchas, reviewed decisions, and next actions after context compression without reading broad archive bodies first,
- AI token usage observability through read-only `archive ai-usage-plan --dry-run`, approval-gated `archive ai-usage-record --approve`, and read-only `archive ai-usage-report --dry-run`, so WOM can estimate explicit context packs, record non-secret runtime token counters, and aggregate bottlenecks without storing prompts or responses,
- read-only `archive ai-response-concept-guide --dry-run` for beginner-facing AI explanation cards about sha256 object identity vs location, manifests vs zets, the objet -> derived text -> zet layer split, operational term translations for edge types, lifecycle states, and connection kinds including `contains` for structural child page/database containment, plus safe routing to Notion import material-clue audits, source-map material-link planning, connection import planning, nested tree recovery planning, and ancestor crawl request planning when provider locators were omitted from imported zettel bodies or structural relations need model review, without overclaiming upload, availability, stronger tie meaning, or forced edge-type mappings,
- a normative plain-language convention on the operator-facing runtime surfaces (`AGENTS.md` templates, the runtime skill, and the plugin-layer doc) telling an operator AI to translate git/infrastructure/WOM-internal jargon into everyday language for humans while keeping the exact term in parentheses or logs, backed by a read-only `ai-response-concept-guide --topic git_infra_terms` lookup layer; it is guidance the AI applies in human-facing prose only, not a WOM-enforced check,
- a normative AI-Operator Discipline section on the same runtime surfaces stating three behavioral norms an operator AI applies: record the source the human actually encountered and never silently substitute a "more authoritative" one (with a matching source-substitution axis in the provenance hierarchy), enumerate the installed/available tools before declaring a task impossible or degrading it, and carry forward already-established/approved state instead of re-asking; it is guidance the AI applies, not a check WOM validates or enforces,

### Provider integrations

Tiro:

- read-only Tiro meeting transcript import planning from archive-internal manifests, preserving meeting metadata, speaker turns, timestamps, confidence, and optional audio objet refs without echoing transcript text, participant names, source URLs, audio filenames, local paths, account ids, emails, tokens, or secrets,
- read-only Tiro full-data lossless recovery planning, approval-gated live Tiro REST fetch into a private raw bundle from `env:` or Windows Credential Manager-backed `keyring:` / `credential-manager:` refs, and approval-gated raw Tiro recovery bundle capture into WOM objets, preserving private raw bundle bytes while reporting only hashes, counts, archive-relative paths, and gap categories,

Notion:

- Notion nested recovery human-step guidance that translates low-level ancestor/fetch/fixture/merge terms into location-oriented user language before one-time approval and live structure fetch handoff,
- `archive notion-recover` with a local `file:<path>` token-file fallback that echoes neither the file path nor the token,
- `archive notion-connection-plan --dry-run` for the one-click Notion connection product contract, and `archive notion-oauth-connection-preflight --dry-run` for validating the secret-blind local OAuth runtime contract before any future browser/callback/token exchange flow,
- Notion provider failure classification into action categories such as token, permission/page-share, rate-limit, network, or provider-availability without raw error echo, while live browser OAuth, callback servers, token exchange, and keyring/vault token storage remain future adapter boundaries,
- read-only human artifact store planning for WordPress, Joplin, Notion, Obsidian, Evernote, generic Markdown, and generic workspace surfaces,
- text-first external export planning with explicit large-media trap detection before broad workspace/database downloads,
- approved external imports that preserve explicit safe object refs, safe `source_refs`, safe facets, and safe zettel id overrides from manifests into imported drafts, plus optional Notion body locator conversion to reviewed `objet:` refs,
- read-only Notion connection import planning for typed-edge candidates with base connection edge vocabulary including `contains` for structural child page/database/view containment and model-gap escalation when no active edge type fits,
- approval-gated link type migration for stale archive-local `types.yml`, plus receipt-backed safe `link-types-v0.3` migration revert when the migration receipt says which edge types were added and those types remain unused and unchanged from the base template,
- a read-only connection evidence parser contract before real export parsing, and a sanitized fixture parser that emits candidate edge previews without writes,
- read-only connection edge intelligence planning that separates relationship meaning from source mechanism, distinguishes ambiguous candidates from human-review-required candidates, flags provisional candidates before human approval, and recommends `supersedes` for sanitized version-chain hints plus `contains` for sanitized containment hints,
- read-only Notion nested tree recovery planning that assigns leaf pages to known generation roots, derives safe content classes from node kinds when needed, blocks oversized nested-tree fixtures instead of returning partial success, and reports untraceable parent chains instead of guessing from partial mirrors,
- read-only Notion ancestor crawl request planning with generation/ref scope filters and a recursive fetch adapter execution contract, plus documentation that untraceable leaf recovery should be scoped by leaf/root/ancestor refs rather than generation id when the generation is still unknown,
- the first approval-gated local Notion ancestor structure fetch adapter, which writes only sanitized ancestor fixtures plus non-secret receipts after credential approval, while Notion media byte fetch and page body capture stay behind separate future gates,
- local nested-tree recovery tooling that builds nested tree fixture previews from reviewed block mirror metadata, merges sanitized ancestor result nodes with immediate after-merge replanning, verifies client nested-tree issues from sanitized local fixture bundles, and packages the minimal sanitized fixture request contract for client follow-up,
- documented Notion page snapshot and `store-ref` boundaries for page/block JSON exports,
- one-zettel plus archive-wide Notion provider locator to manifested objet link planning and reviewed rewrite planning without echoing provider URLs or creating provider URLs,
- import material-clue auditing plus scaled source-map/ledger based Notion material-link planning for imported zets whose body locators were already omitted,
- approval-gated Notion objet manifest locator fingerprint labels so reviewed manifests can match later locator plans without storing raw provider locator text, and approval-gated Notion locator conversion to reviewed `embed` edges without rewriting zettel body text,

Zettel edge writes:

- approval-gated single-edge zettel edge writes for reviewed zet-to-zet or zet-to-objet links including safe `zet:notion:<id>` target resolution,
- approval-gated policy batch zettel edge writes that route only high-confidence policy matches through the single-edge gate, reuse one preloaded object-manifest index for objet targets and one zettel id/path index for zet-target batches, leave the rest in a human review queue, resolve batch plans archive-relative first, and can skip already-written edge rows on explicit request,
- receipt-based `revert-edge` and `revert-batch` commands for approved edge rollback without deleting original receipts,

Object storage:

- manifest-aware object-storage recommendation matching with surfaced bucket names, exact next commands, and Cloudflare R2 setup field guidance,
- object-storage adapter readiness planning, operation request packaging, upload execution-contract planning, and presigned URL planning,
- approval-gated external upload evidence registration and read-only upload evidence auditing before live provider adapters,
- Stage 2 of the live upload adapter: a real hand-rolled AWS SigV4 R2/S3 transport behind a single networking seam (no new dependency), with a bounded retry loop (single-PUT and multipart), a hard cumulative PUT ceiling, whole-object integrity verified by re-download-and-hash (no dependence on any provider checksum surface), orphan cleanup, and a tiered tiny-first gate; the capability is now real but a live `--approve` still fails closed without env credentials, a met tiered gate, and endpoint/bucket, and stays `unproven_against_live_provider` until the first human-run live object,
- a selectable, recorded upload key strategy (`--key-strategy sha256_content_addressed|prefix`, default unchanged) plus a safe `object-storage-adopt-existing` command: objects already stored under an operator's own key layout are adopted only on a live HEAD proving presence + size-match at the recorded key, and under a live transport the executor always re-HEADs that recorded key before any skip (a 404 re-uploads, never a silent skip),

IMAP:

- read-only IMAP mailbox source planning, operation request packaging, schema-validated adapter manifest previews, and approval-gated local adapter manifest writes,
- IMAP adapter readiness checks, mailbox selection planning, adapter audit receipt previews, approval-gated local adapter audit receipt writes, adapter preflight checks, and adapter execution-contract planning,
- a first approval-gated local IMAP header metadata scan for Gmail, Naver, and generic IMAP account refs, plus an offline audit checkpoint for those header scan execution receipts,
- read-only material selection, capture request, capture execution-contract planning, and material capture approval audits, plus approval-gated non-secret material selection records and approval-gated material capture approval receipts before future body/attachment/derived-text work,

### Credentials & setup guidance

- a read-only beginner setup manual with KeePassXC first-vault field walkthroughs, KeePassXC CSV bulk migration import/merge guidance, and Cloudflare R2 bucket/API-token field walkthroughs with Korean/English label hints and S3 credential-pair guidance,
- connected accounts bridge with separate credential-catalog status,
- read-only credential reference planning, inventory, and external store recommendation including account recovery and break-glass redundancy scenarios,
- vault onboarding planning, credential semantic extraction recipe with recovery-code/break-glass routing hints, and plaintext migration planning,
- future access broker planning, local approval receipt preview/write, credential policy checking, and KeePassXC command preflight,
- CLI-only KeePassXC write execution with non-secret execution receipts,
- credential adapter readiness planning, adapter manifest preview, and adapter audit receipt preview for mail, OpenAI API, OCR API, provider, object storage, and backup secrets,

### Hygiene & release tooling

- archive-root boundary warnings in `archive doctor` for top-level web/app development artifacts and incomplete `.git` markers, plus `.gitignore` safe defaults for `node_modules/`, `.next/`, and `.vercel/`,
- approval-gated `.gitignore` repair for missing WOM-kit safe defaults,
- local public-release hygiene tools for links, Korean product language, privacy, release readiness, and branch-protection planning.

## What Does Not Exist Yet

- production-grade installation and platform support,
- broad real OS keyring read/write adapters beyond the narrow approval-gated Tiro Windows Credential Manager read, secret retrieval for other providers, OAuth flows, OpenAI API calls, or paid OCR API calls,
- broad live provider sync beyond the first approval-gated local IMAP header scan and the first approval-gated local Notion ancestor structure fetch,
- broad IMAP ingestion beyond the first approval-gated header metadata scan: OAuth login, keyring/password-manager retrieval, non-inbox mailbox selection, message body capture, attachment capture, or email-derived text extraction,
- production `ZET` transport, sharing service, feed update, or mirroring delivery,
- real wallet creation, private-key custody, cryptographic signing, token mechanics, payments, staking, consensus, or blockchain integration,
- recommendation fetching, ranking, automatic neighbor feed updates, or provider-backed recommendation services,
- projection-plan apply/write behavior, projection receipts, WordPress publishing, or provider-specific publishing,
- real foreign block import/trust/apply, signed attestation statements, receiver-side acceptance, or automatic shared-block renewal,
- broad archive-wide AI scratch sweeps, complete prompt-injection prevention, full-auto execution, model training, backpropagation, Redis, queues, or background workers,
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
- [WOM Product Roadmap](wom-kit/docs/product-roadmap.md)
- [Korean Product Language Baseline](wom-kit/docs/concepts/korean-product-language-baseline.ko.md)
- [Korean Product Language Hygiene](wom-kit/docs/korean-product-language-hygiene.md)
- [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md)
- [Agent Operator Capabilities Manifest](wom-kit/docs/agent-operator-capabilities.md)
- [Operator Feedback Lifecycle](wom-kit/docs/operator-feedback-lifecycle.md)
- [Approval Handoff Lifecycle](wom-kit/docs/approval-handoff-lifecycle.md)
- [Approval Handoff Audit](wom-kit/docs/approval-handoff-audit.md)
- [Operation Status Taxonomy](wom-kit/docs/operation-status-taxonomy.md)
- [Input Provenance Taxonomy](wom-kit/docs/input-provenance-taxonomy.md)
- [Secret Signal Taxonomy](wom-kit/docs/secret-signal-taxonomy.md)
- [AI Response Contract](wom-kit/docs/ai-response-contract.md)
- [Operator Envelope Classes](wom-kit/docs/operator-envelope-classes.md)
- [Objet Capture Enablement](wom-kit/docs/capture-enablement.md)
- [Archive Status Board](wom-kit/docs/archive-status-board.md)
- [Derived Artifact Staleness](wom-kit/docs/derived-artifact-staleness.md)
- [zet Quality Check](wom-kit/docs/zet-quality-check.md)
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
- [Notion Connection Plan](wom-kit/docs/notion-connection-plan.md)
- [Notion OAuth Connection Preflight](wom-kit/docs/notion-oauth-connection-preflight.md)
- [Notion Recover](wom-kit/docs/notion-recover.md)
- [Tiro Import Plan](wom-kit/docs/tiro-import-plan.md)
- [Tiro Lossless Recovery](wom-kit/docs/tiro-lossless-recovery.md)
- [zet Markdown Style Guide](wom-kit/docs/zet-markdown-style-guide.md)
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
- [Connection Import Plan](wom-kit/docs/connection-import-plan.md)
- [Connection Evidence Parser Contract](wom-kit/docs/connection-evidence-parser-contract.md)
- [Connection Evidence Fixture Parser](wom-kit/docs/connection-evidence-fixture-parser.md)
- [Connection Edge Intelligence Plan](wom-kit/docs/connection-edge-intelligence-plan.md)
- [Zettel Edge Write](wom-kit/docs/zettel-edge-write.md)
- [Zettel Edge Batch](wom-kit/docs/zettel-edge-batch.md)
- [Object Storage Recommendations](wom-kit/docs/object-storage-recommendations.md)
- [Object Storage Adapter Readiness Plan](wom-kit/docs/object-storage-adapter-readiness-plan.md)
- [Object Storage Operation Request Plan](wom-kit/docs/object-storage-operation-request-plan.md)
- [Object Storage Adapter Execution Contract](wom-kit/docs/object-storage-adapter-execution-contract.md)
- [Object Storage Upload Evidence](wom-kit/docs/object-storage-upload-evidence.md)
- [Object Storage Upload Evidence Audit](wom-kit/docs/object-storage-upload-evidence-audit.md)
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
- [IMAP Mailbox Material Capture Approval Audit](wom-kit/docs/imap-mailbox-material-capture-approval-audit.md)
- [Notion Page Snapshot Model](wom-kit/docs/notion-page-snapshot-model.md)
- [Objet Ref Resolution](wom-kit/docs/objet-ref-resolution.md)
- [Presigned URL Plan](wom-kit/docs/presigned-url-plan.md)
- [Zettel Objet Links](wom-kit/docs/zettel-objet-links.md)
- [Notion Objet Link Plan](wom-kit/docs/notion-objet-link-plan.md)
- [Notion Objet Link Index](wom-kit/docs/notion-objet-link-index.md)
- [Notion Objet Import Clue Audit](wom-kit/docs/notion-objet-import-clue-audit.md)
- [Notion Objet Source Map Link Plan](wom-kit/docs/notion-objet-source-map-link-plan.md)
- [Notion Objet Link Rewrite Plan](wom-kit/docs/notion-objet-link-rewrite-plan.md)
- [Notion Objet Link Convert](wom-kit/docs/notion-objet-link-convert.md)
- [Notion Objet Manifest Locator Label](wom-kit/docs/notion-objet-manifest-locator-label.md)
- [View Health](wom-kit/docs/view-health.md)
- [View Recommendation Plan](wom-kit/docs/view-recommendation-plan.md)
- [Index Health](wom-kit/docs/index-health.md)
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
v0.3.162 (current checkpoint)
```

Public releases from `v0.2.5` onward are tagged as compatibility checkpoints.
The full release history lives in [CHANGELOG.md](CHANGELOG.md) and the
[GitHub releases page](https://github.com/mow-coding/zettel-kasten/releases);
[VERSIONING.md](VERSIONING.md) explains the versioning policy.

Notable compatibility checkpoints in the v0.3.x line include the
v0.3.137 pre-release, v0.3.134 pre-release,
v0.3.133 pre-release, v0.3.123 pre-release, v0.3.122 pre-release,
v0.3.117 pre-release, and v0.3.116 pre-release baselines, the
v0.3.109 pre-release edge-write baseline, and the v0.3.87 pre-release
compatibility checkpoint. The v0.2.x line closed at v0.2.60, with v0.2.57,
v0.2.56, v0.2.55, and v0.2.54 as the late v0.2.x checkpoints before the
freeze.

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
