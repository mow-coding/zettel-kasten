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
Maintenance contract (decision logs v0.3.161 and v0.3.245): per release, update
ONLY (1) the current-baseline line in the code block below, (2) the single
previous-baseline line, (3) the exact wheel version in the stable Quick Start,
and (4) for feature releases, at most ONE thematic bullet under "What Exists
Today". Release history lives in CHANGELOG.md and wom-kit/docs/releases/ - do
not re-grow baseline ladders or tag lists here.
-->

Current public baseline:

```text
v0.4.9
```

Previous public baseline: v0.4.8.

Full release history: see [CHANGELOG.md](CHANGELOG.md) and [wom-kit/docs/releases/](wom-kit/docs/releases/).

This repository is a public showcase and reference implementation workspace. It is not production-ready yet.

Roadmap snapshot: `v0.1.x` was the idea/protocol-language line, `v0.2.x`
was the first local implementation line, `v0.3.x` was the WOM real-use
feedback and safety-hardening line, `v0.4.x` is the current human-control
layer, and `v0.5.x` is planned for ZET real-use feedback. See the
[WOM Product Roadmap](wom-kit/docs/product-roadmap.md) for the phase gates and
future-only boundaries.

## Quick Start

The URL below is the exact release-artifact contract. Install it only after the
matching GitHub Release exists and lists this wheel. The versioned URL alone is
not proof that the asset is available.

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.9/wom_kit-0.4.9-py3-none-any.whl"
archive --version
```

WOM-kit is not published to PyPI yet, so bare `pip install wom-kit` is not an
official install path. Plain `pip` is supported only in a dedicated virtual
environment using the exact release wheel. Installing the Python tool does not
open or change an archive and does not silently edit AI-host settings.

The wheel includes the `wom-archive` Agent Skill. Preview activation for the
current Codex user before approving any host-configuration write:

```powershell
archive runtime-skill-install --dry-run --format json
```

Continue with the [Python tool install guide](wom-kit/docs/python-tool-install.md),
the [Korean install guide](wom-kit/docs/python-tool-install.ko.md), or the
[Agent Skill activation and removal guide](wom-kit/docs/runtime-skill-install.md).

## What Exists Today

Shipped surfaces, grouped by theme. Each bullet is one shipped capability; for
the status-by-capability view (real implementation, read-only preview,
approval-gated write, or docs-only), see the
[WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md).

### Archive core & lifecycle

- a public WOM/zet/ZET design baseline with specs, schemas, fake archives, release notes, and work logs,
- an explicit event-membership workflow with read-only add/removal plans, bounded evidence audits, and dry-run writer/recovery previews. In v0.4.0 every membership add, removal, or recovery approval fails before private target read or mutation with `compound_exact_human_approval_binding_required`; historical snapshots, journals, and receipts remain auditable but grant no current write authority,
- an artifact-first human-memory doctrine: time-situated local artifacts and their chronology outrank regenerable entity/graph projections; matching labels never authorize silent identity merges, `canonical` names the subject-approved current archive state rather than objective truth, and AI may re-infer context while human change remains visible; see [Product Philosophy](wom-kit/docs/concepts/product-philosophy.md) and the claim-by-claim [Philosophy Implementation Evidence](wom-kit/docs/philosophy-implementation-evidence.md),
- a public version-line roadmap that explains how the pre-1.0 minor lines map to idea, implementation, WOM feedback, UI/control-layer, and ZET feedback phases,
- a machine-readable local-sovereignty contract: local reviewed WOM state is canonical, GitHub backs up metadata/version history, object storage backs up objet bytes, and external databases hold regenerable map backups or replicas; runtime/start-here/recovery surfaces share the same offline, conflict, recovery, and receipt boundaries, while read-only `backup-evidence` reports only locally verifiable lane evidence and never turns local commits, declared labels, generated indexes, or receipt-time coverage into a false current-remote or whole-backup claim,
- a read-only observed source-reference audit that keeps current canonical `source_refs` and exact Notion omission-marker coverage separate from local recorded storage evidence, refuses archive access without explicit Python `-B`, and never turns a complete observed scan, a manifest identity, or a historical provider receipt into an archive-wide source or live-byte claim,
- one integrated real-use feedback surface through Letter 117 with collision-safe records, archive-root path authority, bounded source-intake and Objet-capture batches, structured zet-objet links, complete one-based occurrence authority, reviewed static zettel/objet bindings for exact synced/transclusion placeholders, reviewed zettel navigation for strict empty database pairs, protected-literal hardening, navigation-only zettel references that never infer graph edges, exact generated-TOC placeholder removal, ready-only lossless normalization for paired files and reviewed page/audio bindings, and fail-closed callout/unknown-column/unsupported structures; it neither reconstructs transcluded children nor claims live provider behavior; see [Letter 117 Completion](wom-kit/docs/letter117-completion.md),
- v0.4.0 exact human control for supported high-impact single operations: a native Windows TaskDialog shows content-free operation, target, plan, warning, and checklist bindings; confirmation immediately creates one authenticated durable `started` claim before the writer runs, and the workflow alone finalizes it. AI draft/source-fidelity approval, mint, promotion, one-edge write, draft retirement, human-artifact registry transitions, duplicate reconciliation, and append-only approval-integrity repair use this boundary. Authenticated approval links require a matching `succeeded` claim and prove the original effect only when `effect=created`. Compound/batch and rollback operations remain preview-only; the fixed blocker also covers the current approval branches for project update/collision repair, bytecode repair, gitignore repair, runtime-skill install/uninstall, catalog-pass cleanup, saved views, private objet metadata, identity reconciliation, legacy cleanup, migration, markup normalization, Principal registration, objet capture, external import, source registration, ownership transfer, object-storage mutation, Notion recovery, external-locator mutation, source-intake recording/batches, quarantine decisions, and delegation. Affected approvals fail before private target read or mutation with `compound_exact_human_approval_binding_required`; historical receipts do not grant current write authority. Letter 138 is an urgent follow-on: v0.4.0 does not detect or repair historical Notion typed-property loss, and its page-body/location recovery is not a complete source mirror. See [Exact Human Approval Contract](wom-kit/docs/exact-human-approval-contract.md) and [v0.4.0 release notes](wom-kit/docs/releases/v0.4.0.md),
- v0.4.1 reopens only one structured `zettel-objet-link` apply through that exact-human boundary. It binds one reviewed zettel, one manifested Objet, the role and optional label, the exact plan and target set, snapshot/receipt effects, and the stable per-zettel control artifact before mutation. `zettel-objet-link-revert`, every objet-capture write, and project-version update/collision/bytecode-repair writes remain fixed closed. The v0.4.1 canonical fixed-close inventory is 78 commands; the v0.4.0 release record remains the historical 79-command inventory. See [v0.4.1 release notes](wom-kit/docs/releases/v0.4.1.md),
- v0.4.2 adds CLI-only `git-backup-plan` and `git-backup-reconcile-plan` for a bounded, content-free review of the checked-out Git branch and one anonymous HTTPS remote ref. Both require `--dry-run`, expose no approval or MCP writer, keep `ready_for_write: false`, `writer_available: false`, and `would_change: []`, and do not add, commit, fetch, pull, push, delete, or change a ref. This is only Letter 139's read-only planning foundation, not an end-to-end backup; see the [Git Backup Plan](wom-kit/docs/git-backup-plan.md) and [v0.4.2 release notes](wom-kit/docs/releases/v0.4.2.md),
- v0.4.3 adds the shared `ExactOperationManifest v1` execution foundation, exact-approved Git commit/non-force-push with remote-ref re-query, approval-bound project update and PATH-shadow diagnosis, draft-only feedback CAS revision, and the lossless local-mirror `source_properties` audit/backfill for Letter 138. Completion still requires the released wheel, real manifest approval, durable write/resume/revert evidence, independent verification, and verified remote backup; see the [Exact Operation Manifest](wom-kit/docs/exact-operation-manifest-v1.md) and [v0.4.3 release notes](wom-kit/docs/releases/v0.4.3.md),
- v0.4.4 makes native execution confirmation human-centered: WOM verifies counts, hashes, canonical state, completeness, and drift, while the person decides only whether to run the plainly described operation now. Technical bindings remain available under collapsed details and in durable receipts; see the [Exact Human Approval Contract](wom-kit/docs/exact-human-approval-contract.md) and [v0.4.4 release notes](wom-kit/docs/releases/v0.4.4.md),
- v0.4.5 makes that human-centered confirmation usable from a clean Windows wheel install by activating Common Controls v6 and correcting the byte-packed Task Dialog ABI; it does not weaken machine verification or restore a human digest checklist; see the [v0.4.5 release notes](wom-kit/docs/releases/v0.4.5.md),
- v0.4.6 adds exact, resumable R2 recovery inside the existing adoption family: local-only bytes can be content-addressed and independently rehashed without being mislabeled as adopted, while verified non-conflicting key-map entries can be recorded with one final manifest projection and conflicts remain explicit review debt; see the [v0.4.6 release notes](wom-kit/docs/releases/v0.4.6.md),
- v0.4.9 completes the exact single-file intake path from source record through capture selection to verified local bytes, makes doctor progress observable and its object-manifest findings freshness-bound, resolves suggested-command dry-run versus approval availability honestly, and makes object-storage profile requirements explicit without creating a registry or contacting a provider. Batch writers and doctor performance optimization remain separate work, and installing the release changes no client archive; see the [v0.4.9 release notes](wom-kit/docs/releases/v0.4.9.md),
- a Windows-native, spawned-child credential-intake and authenticated lifecycle plus historical v0.3.320 Notion-recovery evidence: the one-use capability, pre-secret-read authenticated claim, endpoint/scope/budget checks, and three-way content-free evidence remain auditable. In v0.4.0 Notion recovery approval is fixed fail-closed before credential read, provider call, or archive mutation with `compound_exact_human_approval_binding_required`; the read-only plan and verified local replay remain available. WOM never accepts a PAT through argv/stdin/environment, searches a workspace broadly, writes to Notion, or rewrites canonical zets; see [Letters 118 and 119](wom-kit/docs/letter118-119-credential-continuity-and-notion-page-recovery.md) and the [Credential Capability Contract](wom-kit/docs/credential-capability-contract.md),
- one fail-closed current-index authority for protected search, structured `view-zets`, and mint planning; `mint-zet --progress` now emits content-free start and heartbeat evidence to stderr while reserving stdout for the final result, and the separate operator-feedback body companion uses an exact six-section private request plus digest-bound human approval and lifecycle checking without submitting externally or proving real-archive repair; see [Letters 120 and 123](wom-kit/docs/letter120-123-index-lifecycle-and-feedback-body.md),
- a private source-fidelity gate for every new AI-assisted or AI-generated draft: one manifested content-addressed source, explicit `verbatim`, `faithful_summary`, or `sanitized_derivative` mode, dry-run hashes, and attributed human replay are required before a write; `private_self` verbatim preserves personal source data while credential secrets block, declared AI provenance cannot downgrade to the human route, mint re-verifies the private receipt, and audience metadata never shares or exports anything; see [Source Fidelity And Private Verbatim Preservation](wom-kit/docs/source-fidelity-and-private-verbatim.md),
- historical v0.3.316 project-update cache recovery evidence: `project-version-update-collision --action inspect-all` still classifies the complete opaque collision set and the repair planner remains read-only. In v0.4.0 update, collision-mutation, and `project-bytecode-repair` approvals are fixed fail-closed before private project read or mutation; see [Project Version Update](wom-kit/docs/project-version-update.md), [Upgrade Guide](UPGRADE.md), and [v0.3.316 release notes](wom-kit/docs/releases/v0.3.316.md),
- v0.3.319 replaces the rejected terminal-input prototypes with a separate native Windows credential popup in an isolated spawned child. A standard password EDIT keeps ordinary editing and paste behavior, but an opaque sibling hides the value, mask, caret, count, and length; WOM never reads the clipboard. The closed `CredentialPopupInputIntent` makes the blue `실제 자격 증명 등록` production banner and red `합성 입력 테스트 · 실제 키 입력 금지` acceptance banner impossible to confuse programmatically. The popup child detaches before live work, acknowledges that boundary, and the parent accepts only acknowledgement → final mapping → EOF. The human synthetic row remains failed and is not repeated as a recovery prerequisite; actual registration remains `not_performed` and may begin only under a verified published runtime after the person confirms the blue live-registration banner. See [Letter 132 Native Credential Popup And Causal Evidence](wom-kit/docs/letter132-credential-console-keyboard-readiness-and-causal-evidence.md), [Upgrade Guide](UPGRADE.md), and [v0.3.319 release notes](wom-kit/docs/releases/v0.3.319.md),
- a bounded read-only artifact lifecycle inventory over fixed archive-owned scratch, staging, draft, workpack, generated-index, and local content-addressed object surfaces, with independent per-root coverage, content-free stable review refs, strict manifest candidate reconciliation, expiry review without deletion inference, and presence-only protection for non-canonical in-root original storage,
- WOM-kit local CLI and MCP tooling under `wom-kit/`, importing as `wom_kit`,
- an exact installed-wheel resource integrity gate: release checking rejects
  duplicate or unsafe ZIP members, malformed or duplicate-key manifests,
  undeclared resources, and any manifest, byte-count, SHA-256, or packaged
  mirror mismatch before a wheel is accepted,
- a self-contained v0.3.242 Python wheel whose exact GitHub release artifact carries the runtime schemas, templates, base rules, and release identity needed for clean-environment onboarding and strict Doctor; isolated `uv tool install` is recommended, a dedicated `pip` virtual environment is supported, and PyPI publication remains explicitly future work,
- private archive lifecycle tools for doctor checks, draft creation (with forward-only draft-id hygiene so a titleless or Hangul-only title no longer yields a misleading `_draft` id, and draft-time `--kind` validation that warns and lists valid kinds), minting with dry-run checklist guidance and an attributed `--affirm` flag that satisfies the two human-review checklist items via an audited, reviewer-attributed CLI act instead of a raw YAML edit (recorded in the mint receipt, inert without `--reviewed-by`, never overriding machine-enforced items), verified minted-draft retirement, delegation, receipts, search, and metadata review,
- read-only `archive remint-reconcile --dry-run` and `archive retire-draft-reconcile --dry-run` keep the strict `format_drift` / `content_change` classifier, full-field checks, content-free `body_diff_diagnostic`, `human_review_plan`, `review_plan_sha256`, `--strip-bom` preview parity, and redacted `--diagnostic-only` inspection. In v0.4.0 their approval branches fail before private target read or mutation with `compound_exact_human_approval_binding_required`; they rewrite no receipt or canonical byte and create no audit receipt. Historical v0.3.162-v0.3.230 reconcile evidence remains readable,
- historical v0.3 reconcile receipts report `status: reconcile_applied` with doctor verification next-actions; v0.4.0 keeps that evidence readable but grants no reconcile approval authority,
- object-storage Doctor accepts historical same-key `skipped_remote_same` coverage and validates existing reconcile receipts. In v0.4.0 `object-storage-wom-location-reconcile` is preview-only; approval is fixed closed before private manifest/receipt reads and writes no manifest binding or audit receipt,
- generated-index-backed duplicate checks, metadata-backed mint staleness fast paths, clean rollback-mode generated-index inspection/writes, and standard-id source-path fast resolution for large archives,
- scoped `validate --since` / `validate --scope` checks with generated-index body SHA cache support and optional `--progress`, plus stage/count progress output for long `doctor --strict`, large `object-storage-adopt-existing`, and `staged-cleanup-check` runs; large adopt plan resolution now uses a per-run manifest index, explicit `--skip-existing-wom-uploaded` resume helper, read-only `--stop-after-plan` diagnostics, resume-gap counts for matching `declared_uploaded` versus `wom_uploaded` locations, same-provider nonmatching store/key diagnostics, and same-store `wom_uploaded` raw-vs-gating counts, doctor reuses per-run file SHA/frontmatter caches and reports deeper `mint-receipts` target-frontmatter, mint-link, receipt-completion progress, every-receipt heartbeat, every-receipt file-ref liveness, target file-ref drilldown, target edge-receipt index lifecycle plus aggregate source/candidate/cache-hit heartbeats and a final summary, hash start/end liveness, retired-source skips, local-profile secret-safety liveness, early ETA warm-up, compact default `--progress`, opt-in verbose tracing, JSONL progress logs, full result capture with archive-relative `--output`, compact summaries, stdout severity filters, output/progress-log path-policy metadata, and staged cleanup can show content-free walk/verify/hash progress while remaining report-only; per-source edge candidate details stay in verbose/JSONL output instead of flooding compact stderr, while `ai-start-here`, `upgrade-check`, and CLI `zet-catalog` share content-free progress, 10-second heartbeat, and scratch-scoped full-result output; `zet-catalog-pass` completes all strict pages in one process with ephemeral memory reuse and final local revalidation before publishing one SHA-pinned private scratch JSONL, `zet-catalog-pass-read` validates that whole artifact before returning one bounded page, and `zet-catalog-pass-cleanup` deletes only the matching complete scratch file after preview and explicit human approval,
- completed full-Doctor handoffs retain bounded ERROR/WARN items, complete code counts, and suggested commands instead of collapsing actionable findings to severity totals; a BOM finding now fills its reconcile dry-run with the validated canonical zet id and omits the command when that id is absent or unsafe instead of emitting an unresolved placeholder; compact heartbeat prioritizes the current local-profile secret-safety file/content/profile counts over a preserved older edge aggregate, and the regular-file safety walk reuses its checked directory boundary while keeping strict symlink escape checks,
- read-only `archive zet-quality-check --dry-run` for entity-term, document-type, OCR/parse metadata, table-structure, correction-event, source-rights, audience, and derived-artifact dependency risks before mint; optional `zet-quality-rules.yml` project rules can make forbidden entity aliases mint blockers without echoing matched terms,
- read-only `archive zet-title-remap-plan --dry-run`, `archive zet-title-remap-receipt-audit --dry-run`, `archive zet-title-remap-recovery-plan --dry-run`, `archive zet-title-remap-revert-plan --dry-run`, and `archive zet-title-remap-revert-recovery-plan --dry-run` still inspect reviewed proposals and historical evidence. In v0.4.0, `zet-title-remap-write`, `zet-title-remap-recover`, `zet-title-remap-revert`, and `zet-title-remap-revert-recover` are dry-run only; approval fails before private target read or mutation with `compound_exact_human_approval_binding_required` and writes no canonical, snapshot, journal, lock, receipt, or cleanup evidence. Historical v0.3.269, v0.3.270, v0.3.271, v0.3.272, v0.3.273, and v0.3.274 evidence remains readable,
- historical v0.3.275 revert-recovery plans and v0.3.276 recovery receipts remain auditable, but neither `zet-title-remap-recover` nor `zet-title-remap-revert-recover` has a live approval path in v0.4.0; `manual_forensic_hold` remains non-executable,
- read-only `archive status-board --dry-run` for beginner-facing archive state counts across canonical zets, active drafts, minted drafts pending retire, document/audience metadata gaps, source metadata gaps, derived-artifact sync gaps, and optional body-inspecting quality counts without echoing titles, bodies, source values, provider URLs, or local paths,
- frontmatter-only `archive first-read-readiness --dry-run` and MCP `first_read_readiness` separate ordinary archive health from AI memory-reconstruction readiness: every non-redacted canonical zet needs an explicit abstract and every selected zet needs a uniquely resolvable safe id before the gate says `ready`; compatibility text and bounded content-free repair candidates remain visible without echoing titles, abstracts, bodies, duplicate-id values, absolute paths, provider values, or secrets; `create-draft` may still preserve an incomplete idea without an abstract, while `mint-zet`, `mint-zettel`, and legacy `promote` require and revalidate one explicit safe abstract before any canonical publication write; read-only `archive abstract-freshness --dry-run` and MCP `abstract_freshness` then compare each current abstract/body hash pair with retained human-review evidence, distinguish `fresh`, `stale`, `unverified`, `missing`, `unreadable`, and policy-excluded zets in one receipt-index plus one canonical pass, and never echo text or auto-rewrite memory; read-only `archive zet-revision-plan --dry-run` and MCP `zet_revision_plan` bind one private full-zet correction proposal under `.wom-scratch/revisions/` to the exact current canonical bytes, freeze identity/lifecycle/creator metadata, and return only hashes plus fixed change categories; CLI-only `archive zet-revision-write --dry-run` still derives the exact writer candidate without mutation, but v0.4.0 blocks its `--approve` path with `compound_exact_human_approval_binding_required` until a complete revision effect-set binding exists; read-only CLI `archive zet-revision-receipt-audit --dry-run` orders historical ordinary corrections and exact restores as one strictly chained event history, verifies prior-byte snapshots and their manifest records, permits evidence-complete repeated states such as `A -> B -> A`, and classifies leftover transaction locks without deleting them or echoing private content; CLI-only `archive zet-revision-restore-proposal-from-snapshot --dry-run|--approve` can still create an independent content-addressed private review proposal from a verified v0.2 prior-byte snapshot without changing canonical memory; CLI-only `archive zet-revision-restore-plan --dry-run` binds separately recovered complete old zet bytes to the actual latest receipt event and reapplies current policy, while `archive zet-revision-restore-write --dry-run` previews the exact restore effect and its `--approve` path is likewise blocked in v0.4.0 before private target read or mutation; this is one layer of WOM's answer to **the Memento Problem**: a new AI session should rebuild, correct, and when necessary plan evidence-backed recovery of durable context through reviewed local artifacts instead of trusting a fading chat session or editing memory without evidence; since v0.3.240, first-read diagnostic completion is separate from readiness, freshness opens only current evidence candidates without a persistent cache, two-stage progress names the remaining phase, and a large legacy gap starts with a three-zet human pilot rather than bulk automatic backfill; since v0.3.241, freshness scans bounded frontmatter through at most eight workers and opens complete body bytes only for valid explicit-abstract targets,
- read-only `archive derived-artifact-staleness --dry-run` for checking whether declared `derived_artifacts` may be stale because a source zet is newer than the artifact's last reviewed sync. It writes nothing, opens no external report, and does not echo artifact refs, titles, bodies, provider URLs, or local paths,
- a v0.2.x freeze / v0.3.0 entry boundary document plus a narrow v0.3.0 write boundary that stays local-first and body-safe,

### Capture & intake

- human-guided project intake planning, decision receipts, source-intake context, and objet-capture receipt gates,
- a normative AI intake protocol on every runtime-visible surface (AGENTS.md templates, the runtime SKILL.md, and the skill/plugin layer doc),
- source-intake dry-run BEFORE physically copying any local file into the archive or an objet store, with in-archive `staging/incoming/` capture staging as the canonical intake location (D2),
- reviewed selection and prehashed-ledger evidence remain capture-authority inputs, not current write permission. In v0.4.0 selection, capture, and prehashed-ledger approval branches are fixed closed before private reads and publish nothing,
- two additive read-only doctor guards (`archive_objets_layout_noncanonical` for a raw in-root `objets/` folder with a documented migration guide, and `workspace_objet_store_git_exposure` when an objet byte store may be tracked by an enclosing git working tree) plus the anchored `/objets/` `.gitignore` safe default,
- paired transcript intake planning through `archive objet-capture-selection --derived-text-staged-path`: dry-run validates one staged original plus its already-extracted transcript (raw-byte `approved_text_sha256` commitment and staged-path-parity confinement), but v0.4.0 approval is fixed closed before private staged-byte reads or writes,
- dry-run `archive objet-capture` validation for the original/derived pair. In v0.4.0 approval returns `compound_exact_human_approval_binding_required` before private receipt/selection/staged-byte reads or mutation and publishes no object, derived text, manifest row, or receipt; historical item/run `status_class` evidence remains auditable,
- BOM-aware derive-text decoding (BOM-marked UTF-8/UTF-16 stored as BOM-less UTF-8 with raw-byte provenance; UTF-32 and BOM-less non-UTF-8 block deterministically),
- read-only real-archive objet capture enablement eligibility through `archive objet-capture-enable --dry-run`; enable, revoke, and re-enable approval are fixed closed in v0.4.0 before private archive reads or mutation and create no `ops/capture-enablement.yml` record or receipt,
- historical never-touch acknowledgment/revocation evidence and doctor visibility remain readable, but an old consent record grants no v0.4.0 capture authority,
- read-only derived-text coverage/toolchain/doctor/agent-contract gates, manifest-scoped completeness signals, and manifest-quality checks that block false complete claims when `tool_version` or required extraction metadata is missing,
- existing derived-text records as a fallback textual signal for older prehashed manifests, plus non-echoed tool-hint paths for PATH-missing local extractors,
- dry-run single-file and JSONL derived-text capture planning; any route that depends on blocked objet capture authority remains preview-only in v0.4.0 and publishes no derived record or receipt,
- dry-run external upload evidence validation plus read-only upload evidence auditing remain available for historical object-storage receipts. In v0.4.0 `object-storage-upload-evidence --approve` is fixed closed before private ledger/archive reads and adds no receipt or manifest location; the audit never checks a provider or grants current upload authority,

### Retrieval & views

- read-only `action_routing` in runtime-context, ai-start-here, operational-context, and canonical entrypoints tells an AI which official WOM command handles search, checked-layer objet rediscovery before any global absence claim, local version truth, inbox pipeline-shape audit, draft creation, minting, typed edges, source capture, operating-context updates, and saved-view planning; generated AGENTS templates start with `ai-start-here`, raw grep/SQL are not authoritative WOM search, and direct AI Markdown writes to `inbox/` or persistent `views/*.yml` are forbidden. In v0.4.0 `archive saved-view-write` and `saved-view-revert` remain dry-run only: approval fails before private request/target reads or mutation with `compound_exact_human_approval_binding_required` and writes no view, journal, or receipt. Local version output is not remote release freshness proof, and checked-layer rediscovery never upgrades an index-only zero result into global absence; see [Objet Rediscovery Plan](wom-kit/docs/objet-rediscovery-plan.md), [AI Command-Path Routing](wom-kit/docs/ai-command-path-routing.md), [Saved-View Write And Exact Revert](wom-kit/docs/saved-view-write.md), and [Inbox Pipeline Audit](wom-kit/docs/inbox-pipeline-audit.md),
- closed private objet source-metadata and audience-safe label schemas plus a pure Unicode 17 normalization/projection reference module. The plan, index-health envelope, and bounded exact private alias lookup remain read-only. In v0.4.0 `objet-source-metadata-write` approval is fixed fail-closed before private intake/target read or mutation with `compound_exact_human_approval_binding_required`; it appends no row or receipt and publishes no new private-index projection. Historical v0.3 evidence remains auditable; see [Private Objet Finder](wom-kit/docs/private-objet-finder.md),
- read-only preview layers cover runtime context, profiles, source/objet intake, overview-first zet reading, `zet-catalog`, and exact-hash `read-zettel`. `zet-abstract-backfill-plan`, `zet-abstract-backfill-receipt-audit`, and `zet-abstract-backfill-recovery-plan` remain read-only, while `zet-abstract-backfill-write`, `zet-abstract-backfill-revert`, and `zet-abstract-backfill-recover` are dry-run only in v0.4.0. Their approval branches fail before private target read or mutation with `compound_exact_human_approval_binding_required` and create no canonical, snapshot, journal, lock, receipt, guard, or cleanup evidence. Historical v0.3.218-v0.3.220 and v0.3.265-v0.3.267 evidence remains readable; public output still omits ids, paths, bodies, abstracts, and reviewer values,
- generated index health checks, saved view health, facet role diagnostics, saved view recommendations,
- read-only objet reference resolution, presigned URL planning, and zettel objet link previews for mapping `sha256:<hex>` refs to safe local/external candidates,

### Sharing & ZET previews

- read-only previews for foreign block review, projection planning with supported-surface help, shared update review/index, shared update route pointers, and ZET would-transport planning,
- approval-gated local write paths for selected private archive, foreign-block review records, and the first v0.3.0 shared update attestation/review record,

### Privacy & redaction

- zet self-contained checks, AI scratch lifecycle management, and read-only AI artifact inventory introduced in v0.3.187 pre-release: public external citation URLs may stay in zet bodies or `source_refs`, private provider locators and original-file locations still require durable WOM refs, `.wom-scratch/`, `workbench/ai-scratch/`, `staging/ai/inbox/`, and `staging/ai/reviewed/` are treated as bounded AI artifact/scratch surfaces, `archive ai-artifact-inventory --dry-run` can list candidate fates without reading file bodies, echoing paths by default, writing files, deleting files, creating zets, or calling providers, and approved mint can remove explicit scratch refs from the canonical zet while consuming those scratch files through a cleanup receipt,
- read-only `archive secret-signal-taxonomy --dry-run` for AI operators that need to distinguish harmless secret/credential/token concept words and safe refs from actual secret-like values, private locators, account identifiers, or unknown sensitive context,

### AI-operator contracts & runtime handoff

- defensive local coordination quarantine that keeps `collab/` and legacy `/.mow-harness/` state outside default archive discovery and public Git surfaces. The exact-root, content-free `legacy-coordination-cleanup` dry-run remains available, but v0.4.0 approval is fixed fail-closed before workspace read or mutation with `compound_exact_human_approval_binding_required`; it deletes or creates nothing. The v0.3.307 Windows mutation contract is historical evidence, not a current run instruction; see [Legacy Coordination Cleanup](wom-kit/docs/legacy-coordination-cleanup.md),
- a CLI-only local Agent Skill host lifecycle: read-only `runtime-skill-status`, digest-bound `runtime-skill-install --dry-run|--approve`, and manifest-verified `runtime-skill-uninstall --dry-run|--approve` use current Codex user/repository `.agents/skills` locations or one explicit custom root, redact paths by default, require a reviewer plus the exact preview digest before writes, and never overwrite or remove unmanaged/human-edited skill directories; Python installation itself still writes no host configuration and no MCP write surface is added,
- a standards-compatible `wom-archive` Agent Skill package with a 104-line first-read `SKILL.md`, six focused task references, one preserved complete operator contract, and a release-gated validator for metadata, link/path safety, discovery, context budgets, approval/privacy boundaries, artifact primacy, and no-silent-identity-merge guidance; AI operators load only the reference needed for the current goal, treat canonical as reviewed state rather than objective truth, preserve human change, and never install themselves silently,
- read-only WOM-kit version truth-source checks through `archive --version`, `archive version --format json`, parent-project installed-version pin discovery, runtime-context metadata, and `project-version-update` dry-run planning. Since v0.3.291 the read-only alignment result has distinguished the running import from a verified project mirror and pin. Historical v0.3 update/collision evidence preserves the atomic-fetch, tracked-tree materialization, pin, rollback, Windows quiescence, exact-Git-object bridge, and restart contracts; in v0.4.0 every update/collision mutation approval is fixed closed before private project reads and writes no project byte, pin, lock, or receipt,
- read-only `archive capabilities --machine` for AI operators that need a stable `ok/state/summary/data/blockers/warnings` envelope listing the executable local CLI commands, aliases, required positionals, options, nested subcommands, and local release identity without calling GitHub or providers,
- read-only `archive operator-feedback-plan --dry-run` and approval-gated `archive operator-feedback-record --approve` for tracking operator-generated tool feedback under `ops/feedback/` with draft/delivered/acknowledged/resolved/archived lifecycle metadata, plus read-only `archive operator-feedback-ledger --dry-run` (aliases `feedback-ledger`, `feedback-board`) that aggregates delivery-status counts + a pending list and approval-gated `archive operator-feedback-mark-delivered --approve` that batches the draft->delivered boundary with a `delivered_at` stamp and a single receipt, all without reading feedback bodies, echoing feedback refs/titles, submitting externally (metadata only; `delivered` is the operator's own mark, not proof of external delivery), or mixing feedback lifecycle state into user knowledge `objets/`,
- read-only `archive approval-handoff-plan --dry-run` and approval-gated `archive approval-handoff-record --approve` for AI-to-human approval handoff metadata under `ops/approval-handoffs/`, so sensitive operations can stop at a clear needs_review/approved_once/denied/superseded/resolved state without executing the operation, reading private material, calling providers, or echoing target/action values,
- read-only `archive approval-handoff-audit --dry-run` for structurally checking legacy handoff metadata. Its result is always `legacy_unbound`/advisory with `future_operation_authorized: false`; it never grants future-operation authority, executes the operation, or echoes target/action values,
- read-only `archive operation-status-taxonomy --dry-run` for AI operators that need to distinguish succeeded/preview/written/no_change from partial/truncated/blocked/failed results before telling a human that work is complete,
- read-only `archive input-provenance-taxonomy --dry-run` for AI operators that need to distinguish tool-discovered and receipt-verified inputs from caller-supplied, AI-generated, fixture, environment-inferred, or unknown inputs before treating them as source truth,
- read-only `archive ai-response-contract --dry-run` for AI operators that need a conversational status-board contract before answering a human: outcome, evidence basis, privacy/approval boundary, remaining work, and no web UI requirement,
- core read-only operator commands now expose top-level `status_class`, `input_provenance_class`, `secret_signal_class`, and `operator_envelope` fields so AI operators can apply the response contract without inferring those classes from prose,
- runtime-context canonical entrypoint metadata so AI runtimes can see which archive-relative files/directories to treat as start-here and authoritative sources, plus machine-readable `ai_runtime_order`, `recommended_first_commands`, and `material_link_routes` that hand off from `runtime-context` to `AGENTS.md` and `ai-response-concept-guide`,
- read-only `archive ai-start-here <archive-root> --dry-run --format markdown|json` and quick-default CLI/MCP `runtime-context` project identity, canonical entrypoints, authority, operational context, and cross-file identity consistency without walking every zet or receipt; complete Doctor work is explicit through `--full-doctor`, its edge-receipt evolution check builds one filename-only index and opens only receipts belonging to the mismatched zet while reporting separate content-free index/load counts, start-here marks runtime-context as already included while exposing separate `completed_commands` and `next_commands`, new archives replace template identity metadata during initialization, and existing same-principal template/display mismatches route to the value-free `identity-reconcile --dry-run` plus an explicit three-digest-bound approval instead of a silent metadata rewrite,
- AI operational context rehydration through `ops/operational-context.yml`, runtime-context field `operational_context`, and approval-gated `archive operational-context` updates with receipts, so an AI runtime can recover mission, scope, state, gotchas, reviewed decisions, and next actions after context compression without reading broad archive bodies first,
- receipt-backed `archive session-handoff-checkpoint` for closing an AI session without trusting chat memory: it binds the exact approved operational-context bytes and a content-free AI artifact inventory into a stale-safe digest, requires explicit conversation review before approval, and becomes stale when either archive surface changes; it never reads the host chat or AI artifact bodies and is not remote backup proof,
- AI token usage observability through read-only `archive ai-usage-plan --dry-run`, approval-gated `archive ai-usage-record --approve`, and read-only `archive ai-usage-report --dry-run`, so WOM can estimate explicit context packs, record non-secret runtime token counters, and aggregate bottlenecks without storing prompts or responses,
- read-only `archive ai-response-concept-guide --dry-run` for beginner-facing AI explanation cards about sha256 object identity vs location, manifests vs zets, the objet -> derived text -> zet layer split, operational term translations for edge types, lifecycle states, and connection kinds including `contains` for structural child page/database containment, plus safe routing to Notion import material-clue audits, source-map material-link planning, connection import planning, nested tree recovery planning, and ancestor crawl request planning when provider locators were omitted from imported zettel bodies or structural relations need model review, without overclaiming upload, availability, stronger tie meaning, or forced edge-type mappings,
- `ai-response-concept-guide --topic operator_vocabulary --locale ko-KR`, a read-only vocabulary layer for AI operators that uses user-confirmed product terms (`WOM`, `zet`, `ZET`, `objet`, `receipt` as `영수증`, `mint` as `발행하다`, `canonical` as `정본`, `node` as `노드`, `edge` as `엣지`, `tie` as `타이`, `archive` as `아카이브 폴더`, `ai_start_here` as `AI 스타팅 메뉴얼`, `frontmatter` as `초록 데이터`) and confirmed operator terms such as `object_id` as `오브제 아이디`, `doctor` as `검진`, `provider` as `외부 서비스`, `containment` as `포함 관계`, `safe_preview` as `미리보기`, `approved_write` as `승인 후 쓰기`, `external_report` as `공개용 문서`, and `private_working_note` as `비공개 문서`,
- a normative plain-language convention on the operator-facing runtime surfaces (`AGENTS.md` templates, the runtime skill, and the plugin-layer doc) telling an operator AI to translate git/infrastructure/WOM-internal jargon into everyday language for humans while keeping the exact term in parentheses or logs, backed by a read-only `ai-response-concept-guide --topic git_infra_terms` lookup layer; it is guidance the AI applies in human-facing prose only, not a WOM-enforced check,
- a normative AI-Operator Discipline section on the same runtime surfaces stating three behavioral norms an operator AI applies: record the source the human actually encountered and never silently substitute a "more authoritative" one (with a matching source-substitution axis in the provenance hierarchy), enumerate the installed/available tools before declaring a task impossible or degrading it, and carry forward already-established/approved state instead of re-asking; it is guidance the AI applies, not a check WOM validates or enforces,

### Provider integrations

Tiro:

- read-only Tiro meeting transcript import planning from archive-internal manifests, preserving meeting metadata, speaker turns, timestamps, confidence, and optional audio objet refs without echoing transcript text, participant names, source URLs, audio filenames, local paths, account ids, emails, tokens, or secrets,
- read-only Tiro full-data lossless recovery planning plus content-free fetch/capture dry-runs. In v0.4.0 both approval branches fail before credential, provider, private bundle, manifest, or target reads with `compound_exact_human_approval_binding_required`; they call no Tiro endpoint and write no bundle, objet, manifest row, or receipt,

Notion:

- Notion nested recovery human-step guidance that translates low-level ancestor/fetch/fixture/merge terms into location-oriented user language for a content-free dry-run preview; v0.4.0 stops before any credential, provider, fixture, or receipt access,
- `archive notion-recover --dry-run` as the only executable beginner wrapper path in v0.4.0; its implicit executor and approval branch return `compound_exact_human_approval_binding_required` before credential/private target reads or provider calls,
- `archive notion-connection-plan --dry-run` for the one-click Notion connection product contract, and `archive notion-oauth-connection-preflight --dry-run` for validating the secret-blind local OAuth runtime contract before any future browser/callback/token exchange flow,
- Notion provider failure classification into action categories such as token, permission/page-share, rate-limit, network, or provider-availability without raw error echo, while live browser OAuth, callback servers, token exchange, and keyring/vault token storage remain future adapter boundaries,
- read-only human artifact store planning for WordPress, Joplin, Notion, Obsidian, Evernote, generic Markdown, and generic workspace surfaces,
- text-first external export planning with explicit large-media trap detection before broad workspace/database downloads,
- read-only external-import preview that validates explicit safe object refs, safe `source_refs`, safe facets, and safe zettel id overrides. In v0.4.0 `import-external` approval fails before archive/export reads or mutation with `compound_exact_human_approval_binding_required` and writes no draft or receipt,
- read-only Notion connection import planning for typed-edge candidates with base connection edge vocabulary including `contains` for structural child page/database/view containment and model-gap escalation when no active edge type fits,
- read-only link-type migration and revert previews for stale archive-local `types.yml`; v0.4.0 `migrate` approval is fixed closed before private archive reads or mutation and writes no type, revert, or receipt,
- a read-only connection evidence parser contract before real export parsing, and a sanitized fixture parser that emits candidate edge previews without writes,
- read-only relation review that reserves `continues` for the next week/installment of the same course or work and activates manual-only `sequence` for a generic process's next step; `sequence` and `format_variant` cannot be auto-written through `zettel-edge-batch`, recurrence remains a coordinate rather than an edge, and Principal registration/unregistration approval is fixed closed in v0.4.0 while existing reviewed Principals remain valid single-edge targets,
- read-only connection edge intelligence planning that separates relationship meaning from source mechanism, distinguishes ambiguous candidates from human-review-required candidates, recommends `supersedes` for sanitized version-chain hints plus `contains` for sanitized containment hints, and recognizes active manual-only meanings without inferring them from titles, filenames, provider mechanisms, or the existing corpus; since v0.3.290 the shared single-edge gate also fails closed unless the resolved `Zettel`/`OriginalObject`/`Principal` endpoint satisfies the selected active `types.yml` record's non-empty `from` and `to` entity-type lists,
- read-only Notion nested tree recovery planning that assigns leaf pages to known generation roots, derives safe content classes from node kinds when needed, blocks oversized nested-tree fixtures instead of returning partial success, and reports untraceable parent chains instead of guessing from partial mirrors,
- read-only Notion ancestor crawl request planning with generation/ref scope filters and a recursive fetch adapter execution contract, plus documentation that untraceable leaf recovery should be scoped by leaf/root/ancestor refs rather than generation id when the generation is still unknown,
- dry-run Notion ancestor adapter planning. `notion-ancestor-fetch-adapter-run` approval is fixed closed in v0.4.0 before credential/private target reads, provider calls, or writes and creates no ancestor fixture or execution receipt; historical v0.3 evidence remains auditable,
- local nested-tree recovery tooling that builds nested tree fixture previews from reviewed block mirror metadata, merges sanitized ancestor result nodes with immediate after-merge replanning, verifies client nested-tree issues from sanitized local fixture bundles, and packages the minimal sanitized fixture request contract for client follow-up,
- documented Notion page snapshot and `store-ref` boundaries for page/block JSON exports,
- one-zettel plus archive-wide Notion provider locator to manifested objet link planning and reviewed rewrite planning without echoing provider URLs or creating provider URLs,
- import material-clue auditing plus scaled source-map/ledger based Notion material-link planning for imported zets whose body locators were already omitted, the CLI-only read-only `notion-import-locator-loss-audit` census that compares current omission markers with import-time counts and verifies private `source_page_id` join-key presence without echoing values or reading source mirrors, and the v0.3.287 CLI-only read-only `notion-import-locator-evidence-plan` that validates a human-reviewed private source-occurrence-to-marker mapping against exact current canonical bytes while returning no page id, locator, fingerprint, zet identity, path, title, body, or context and performing no restoration,
- dry-run Notion objet manifest locator fingerprint labeling and link conversion previews. In v0.4.0 both approval branches fail before private manifest/zettel reads or mutation with `compound_exact_human_approval_binding_required` and write no manifest row, edge, locator-label receipt, or conversion receipt,

Zettel edge writes:

- approval-gated single-edge zettel edge writes for reviewed zet-to-zet or zet-to-objet links including safe `zet:notion:<id>` target resolution,
- dry-run policy batch zettel-edge planning that classifies high-confidence candidates but grants no batch authority; `zettel-edge-batch --approve` fails before private target read or mutation and writes no item or batch receipt,
- dry-run `revert-edge` and `revert-batch` previews only; their approval branches return `compound_exact_human_approval_binding_required` before private target read or mutation and delete no edge or receipt,

Object storage:

- manifest-aware object-storage recommendation matching with surfaced bucket names, exact next commands, and Cloudflare R2 setup field guidance,
- object-storage adapter readiness planning, operation request packaging, upload execution-contract planning, and presigned URL planning,
- dry-run external upload-evidence registration and read-only evidence auditing. In v0.4.0 registration approval is fixed closed before private ledger/archive reads and writes no receipt or manifest location,
- historical v0.3 AWS SigV4 R2/S3 single-PUT, multipart, force-reupload, adopt-existing, key-map, tier, and verification evidence remains auditable. In v0.4.0 every object-storage setup/upload/adopt/reconcile approval returns `compound_exact_human_approval_binding_required` before credential, provider, object, manifest, receipt, or target reads; it performs no network call or mutation and writes no receipt,

IMAP:

- read-only IMAP mailbox source planning, operation request packaging, and schema-validated adapter manifest previews. In v0.4.0 adapter-manifest approval fails before private input/archive reads with `compound_exact_human_approval_binding_required` and writes no config or receipt,
- IMAP adapter readiness checks, mailbox selection planning, adapter audit receipt previews, approval-gated local adapter audit receipt writes, adapter preflight checks, and adapter execution-contract planning,
- a content-free IMAP header metadata scan preflight for Gmail, Naver, and generic IMAP account refs. In v0.4.0 approval fails before manifest, receipt, credential, provider, mailbox, or target reads with `compound_exact_human_approval_binding_required`; it opens no connection, reads no headers, and writes no execution receipt. Existing non-secret execution receipts remain offline-auditable,
- read-only material selection, capture request, capture execution-contract planning, and material capture approval audits, plus approval-gated non-secret material selection records and approval-gated material capture approval receipts before future body/attachment/derived-text work,

### Credentials & setup guidance

- a read-only beginner setup manual with KeePassXC first-vault field walkthroughs, KeePassXC CSV bulk migration import/merge guidance, and Cloudflare R2 bucket/API-token field walkthroughs with Korean/English label hints and S3 credential-pair guidance,
- connected accounts bridge with separate credential-catalog status,
- read-only credential reference planning, inventory, and external store recommendation including account recovery and break-glass redundancy scenarios,
- vault onboarding planning, credential semantic extraction recipe with recovery-code/break-glass routing hints, and plaintext migration planning,
- future access broker planning, local approval receipt preview/write, credential policy checking, and KeePassXC command preflight,
- a CLI-only KeePassXC command-shape preview. In v0.4.0 write approval fails before approval-receipt, credential, database, or provider reads with `compound_exact_human_approval_binding_required`; it invokes no vault process and writes no execution receipt,
- credential adapter readiness planning, adapter manifest preview, and adapter audit receipt preview for mail, OpenAI API, OCR API, provider, object storage, and backup secrets,

### Hygiene & release tooling

- archive-root boundary warnings in `archive doctor` for top-level web/app development artifacts and incomplete `.git` markers, plus `.gitignore` safe defaults for `node_modules/`, `.next/`, and `.vercel/`,
- approval-gated `.gitignore` repair for missing WOM-kit safe defaults,
- local public-release hygiene tools for links, Korean product language, privacy, release readiness, and branch-protection planning.

## What Does Not Exist Yet

- production-grade installation and platform support,
- real OS keyring read/write adapters, including Tiro credential retrieval, secret retrieval for other providers, OAuth flows, OpenAI API calls, or paid OCR API calls,
- broad live provider sync beyond the supported operation-specific paths; the historical Notion ancestor adapter is preview-only and fixed closed for approval in v0.4.0,
- live IMAP ingestion, including header scanning, OAuth login, keyring/password-manager retrieval, mailbox selection, message body capture, attachment capture, or email-derived text extraction; the v0.4.0 header-scan surface is preflight-only and approval is fixed closed,
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
- [First-Read Readiness](wom-kit/docs/first-read-readiness.md)
- [Explicit Abstract Publication Gate](wom-kit/docs/explicit-abstract-publication.md)
- [Abstract Freshness Check](wom-kit/docs/abstract-freshness.md)
- [Three-zet Abstract Backfill Pilot](wom-kit/docs/abstract-backfill-pilot.md)
- [Derived Artifact Staleness](wom-kit/docs/derived-artifact-staleness.md)
- [zet Quality Check](wom-kit/docs/zet-quality-check.md)
- [Version Truth Source](wom-kit/docs/version-truth-source.md)
- [Project Version Update](wom-kit/docs/project-version-update.md)
- [zet Catalog One-Process Pass](wom-kit/docs/zet-catalog-one-process-pass.md)
- [Runtime Canonical Entry Points](wom-kit/docs/runtime-canonical-entrypoints.md)
- [AI Command-Path Routing](wom-kit/docs/ai-command-path-routing.md)
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
- [zet Frontmatter Viewer Contract](wom-kit/docs/zet-frontmatter-viewer-contract.md)
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
- [Notion Import Locator-Loss Audit](wom-kit/docs/notion-import-locator-loss-audit.md)
- [Notion Import Locator Evidence Plan](wom-kit/docs/notion-import-locator-evidence-plan.md)
- [Notion Objet Source Map Link Plan](wom-kit/docs/notion-objet-source-map-link-plan.md)
- [Notion Objet Link Rewrite Plan](wom-kit/docs/notion-objet-link-rewrite-plan.md)
- [Notion Objet Link Convert](wom-kit/docs/notion-objet-link-convert.md)
- [Notion Objet Manifest Locator Label](wom-kit/docs/notion-objet-manifest-locator-label.md)
- [View Health](wom-kit/docs/view-health.md)
- [View Recommendation Plan](wom-kit/docs/view-recommendation-plan.md)
- [Saved-View Write And Exact Revert](wom-kit/docs/saved-view-write.md)
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
v0.4.9 (current checkpoint)
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
PYTHONPATH=wom-kit/src python -m unittest discover -s wom-kit/tests
PYTHONPATH=wom-kit/src python -m wom_kit.archive_cli doctor wom-kit/examples/fake-life-archive --strict
```

Expected result:

```text
tests pass
doctor reports 0 errors and 0 warnings
```

The direct `wom-kit/cli/archive.py` wrapper is a verified bridge and pristine
checkout recovery entrypoint, not the normal development launcher. Use the
module form above in an active source tree, including after tests have created
bytecode caches.

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
