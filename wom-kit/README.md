# WOM-kit v0.3 Draft

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
docs/concepts/korean-product-language-baseline.ko.md
docs/korean-product-language-hygiene.md
docs/concepts/wom-safe-html-profile.md
docs/concepts/wom-safe-html-profile.ko.md
docs/product-roadmap.md
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
docs/ai-response-concept-guide.md
docs/connection-import-plan.md
docs/connection-evidence-parser-contract.md
docs/connection-evidence-fixture-parser.md
docs/connection-edge-intelligence-plan.md
docs/notion-nested-tree-plan.md
docs/notion-ancestor-crawl-plan.md
docs/notion-ancestor-fetch-adapter-execution-contract.md
docs/notion-ancestor-fetch-adapter-run.md
docs/notion-connection-plan.md
docs/notion-oauth-connection-preflight.md
docs/notion-recover.md
docs/notion-media-fetch-adapter-execution-contract.md
docs/notion-media-result-verification-plan.md
docs/notion-block-mirror-tree-fixture-plan.md
docs/notion-ancestor-merge-plan.md
docs/notion-client-issue-verification-plan.md
docs/notion-client-fixture-request-plan.md
docs/tiro-import-plan.md
docs/tiro-lossless-recovery.md
docs/zet-markdown-style-guide.md
docs/zettel-edge-write.md
docs/zettel-edge-batch.md
docs/project-intake-session.md
docs/project-intake-cookbook.md
docs/derived-text-coverage-and-toolchain.md
docs/derived-text-completeness-signal.md
docs/human-artifact-store-contract.md
docs/object-storage-recommendations.md
docs/object-storage-adapter-readiness-plan.md
docs/object-storage-operation-request-plan.md
docs/object-storage-adapter-execution-contract.md
docs/object-storage-upload-evidence.md
docs/object-storage-upload-evidence-audit.md
docs/imap-mailbox-source.md
docs/imap-mailbox-operation-request-plan.md
docs/imap-mailbox-adapter-manifest-plan.md
docs/imap-mailbox-adapter-manifest-write.md
docs/imap-mailbox-adapter-readiness-plan.md
docs/imap-mailbox-selection-plan.md
docs/imap-mailbox-adapter-audit-plan.md
docs/imap-mailbox-adapter-audit-write.md
docs/imap-mailbox-adapter-preflight-plan.md
docs/imap-mailbox-adapter-execution-contract.md
docs/imap-mailbox-header-metadata-scan.md
docs/imap-mailbox-header-scan-receipt-audit.md
docs/imap-mailbox-material-selection-plan.md
docs/imap-mailbox-material-selection-record.md
docs/imap-mailbox-material-capture-request-plan.md
docs/imap-mailbox-material-capture-execution-contract.md
docs/imap-mailbox-material-capture-approval-plan.md
docs/imap-mailbox-material-capture-approval-audit.md
docs/version-truth-source.md
docs/project-version-update.md
docs/ai-start-here.md
docs/archive-identity-reconcile.md
docs/zet-catalog-one-process-pass.md
docs/runtime-canonical-entrypoints.md
docs/operational-context.md
docs/connected-accounts.md
docs/credential-semantic-extraction-recipe.md
docs/credential-keepassxc-command-plan.md
docs/credential-keepassxc-write.md
docs/zet-surface-prototypes.md
docs/notion-source-export-three-store-example.md
docs/notion-page-snapshot-model.md
docs/objet-ref-resolution.md
docs/presigned-url-plan.md
docs/zettel-objet-links.md
docs/notion-objet-link-plan.md
docs/notion-objet-link-index.md
docs/notion-objet-import-clue-audit.md
docs/notion-objet-source-map-link-plan.md
docs/notion-objet-link-rewrite-plan.md
docs/notion-objet-link-convert.md
docs/notion-objet-manifest-locator-label.md
docs/view-health.md
docs/view-recommendation-plan.md
docs/index-health.md
docs/source-maps.md
docs/platform-support.md
docs/server-blueprint.md
docs/capability-matrix.md
docs/v02x-freeze-v03-entry-boundary.md
docs/shared-update-attestation-review-write.md
```

## Minimal CLI

v0.2 includes a small local CLI:

```text
cli/archive.py
```

Current commands:

```text
version
  Print the running WOM-kit CLI version and optional project pin/source mirror status. When an archive root is inspected, the command can also find a parent project installed-version pin and .zettel-kasten/source mirror, including source version and latest fetched tag drift when available. JSON output is available for AI/runtime checks and redacts local paths by default.

project-version-update --dry-run|--approve --target vX.Y.Z
  Preview locally, then approval-gate one configured-origin fetch, exact annotated-tag/main-ancestry/version verification, detached source-mirror checkout, recognized pin alignment, and schema-backed project receipt. Dirty or ambiguous state blocks; post-checkout failure rolls source and pins back. It never writes archive knowledge and requires a new process plus `archive version` verification after success. v0.3.215 is the one-time bootstrap boundary for older installs.

onboard
  Plan or apply first archive setup. Dry-run writes nothing; --approve creates the archive, provider-bindings.yml, and runs strict doctor.

doctor
  Inspect an archive for missing files, invalid frontmatter, schema problems, manifest problems, unsafe zettel references, and minting-rule warnings. Use `--progress` for long real-archive checks. Compact edge-receipt progress now keeps index lifecycle plus aggregate source/candidate/cache-hit heartbeats and one final summary; use `--progress-detail verbose` or `--progress-log` for each source candidate batch.

profile-list
  List a local WOM profile registry without writing files. Local registry and archive paths are redacted by default.

profile-resolve
  Resolve a requested WOM profile by exact profile id, label, or alias before runtime-context or draft work.

profile-wallet
  Preview wallet-ready WOM profile/node identity metadata. Dry-run only; never generates keys, signs data, stores secrets, or calls blockchain/provider APIs.

runtime-context
  Print quick read-only JSON context for terminal-capable AI runtimes. It confirms archive id, archive type/scope, principal/owner summary, cross-file identity consistency, AI write policy, safe archive-relative paths, canonical entrypoint metadata, AI guide handoff order, material-link routes, safe actions, WOM-kit version, and local-sovereignty storage authority without constructing Doctor by default. Add `--full-doctor --progress` only for a complete archive health check. A completed full run retains bounded ERROR/WARN items, complete code counts, and suggested commands in `doctor_findings`; INFO remains count-only. Compact heartbeat reports current local-profile secret-safety file/content/profile counts instead of letting a preserved older edge aggregate hide the active stage. Local absolute paths are redacted by default.

ai-start-here --dry-run
  Print one compact first-read map for an entering AI operator without scanning every zet or receipt. The result marks runtime-context already included, surfaces identity consistency, routes a mismatch to the read-only identity-reconcile preview, and separates `completed_commands` from executable `next_commands` so an AI does not repeat the handoff. Add `--full-doctor` only when a complete archive health check is needed. Optional `--progress` reports de-duplicated counts, work units, stage elapsed time, rate, ETA, and count-bearing heartbeats on stderr; a long mint receipt heartbeat also uses a fixed safe phase such as `file_hash` or `edge_receipt_index`, while edge source-load progress is aggregated into content-free source/candidate/cache-hit counts. Optional `--output .wom-scratch/diagnostics/<name>.json` stores the full result as private local scratch and leaves a compact stdout summary.

identity-reconcile --dry-run|--approve
  Compare the principal declaration in `archive.yml` with the identity and ownership core in `archive-identity.yml`. Dry-run returns only field names and current/proposed SHA-256 digests. Same-principal display metadata and a missing or template-like identity id can be repaired only through a reviewed, three-digest-bound approval; principal conflicts fail closed. Approval edits only `archive-identity.yml`, writes a value-free receipt, and restores exact prior bytes on handled receipt failure.

local-sovereignty --dry-run
  Report the machine-readable authority model: local WOM is canonical, GitHub backs up metadata/version history, object storage backs up objet bytes, and external databases hold regenerable map backups or replicas. It performs no live audit, provider/network call, secret read, or write.

prompt-boundary
  Check untrusted text for obvious prompt-injection and unsafe-agent strings. Dry-run only; never calls LLMs, executes inspected text, approves, mints, or writes files.

github-repo
  Plan GitHub repository setup for a resolved WOM profile. Dry-run writes nothing. Approved mode writes only local provider metadata and a setup receipt; it does not create GitHub repositories, configure remotes, push, or sync.

object-storage
  Plan object storage setup for WOM objets. Dry-run writes nothing. Approved mode writes only local provider metadata and a setup receipt; it does not create buckets, upload, sync, copy, hash, or import source files.

object-storage-recommendation
  Recommend an object storage provider path before setup planning. Dry-run only; writes nothing, calls no providers, performs no live price lookup, checks no bucket availability, uploads nothing, creates no presigned URLs, and returns the proposed bucket name, setup manual command, and next object-storage dry-run command shape.

object-storage-operation-request-plan
  Compose a future object-storage operation approval request package. Dry-run only; combines provider readiness, object target validation, presigned URL planning or objet-ref resolution, and credential policy checks without calling providers, reading secrets, creating presigned URLs, uploading, downloading, or writing files.

object-storage-adapter-execution-contract
  Preview the future object-storage upload adapter execution contract. Dry-run only; defines sha256 content-addressed keys, approval re-verification, local SHA-256 verification, provider HEAD/idempotency checks, bounded retry/resume ledger, non-secret receipts, and manifest update rules without calling providers, reading object bytes, uploading, writing ledgers or receipts, or updating manifests.

object-storage-upload-evidence
  Preview or approve-register reviewed external object-storage upload evidence for existing manifest objects. Dry-run reads UTF-8 JSONL upload evidence ledgers, matches successful sha256 rows against objects/manifests/files.jsonl, and previews object_storage locations without echoing ledger paths or row values. Approved mode requires --reviewed-by and --store-ref, writes one non-secret receipt, and updates manifest locations while still calling no providers, reading no object bytes, checking no remote availability, uploading nothing, downloading nothing, syncing nothing, and reading no secrets.

object-storage-upload-evidence-audit
  Audit one upload evidence receipt against objects/manifests/files.jsonl. Dry-run only; validates receipt schema, non-secret privacy guards, no-provider closed actions, linked object_storage locations, declared_uploaded availability, sha256 key hints, and receipt/location count consistency without writing files, calling providers, reading object bytes, checking remote availability, uploading, downloading, syncing, creating provider URLs, or retrieving secrets.

object-storage-adopt-existing
  Adopt objects already stored under your own key layout so a later upload does not re-PUT them (the false-skip fix). Takes the explicit key strategy (--key-strategy prefix --key-prefix <literal> [--key-append-extension]). A verified adopt (--approve + live credentials) HEADs each computed remote_key and adopts ONLY on presence + Content-Length size-match (--content-hash-verify opts one in to a full re-hash per object); a 404 or size-mismatch is not adopted, so a wrong prefix/extension simply re-uploads. A declared adopt (--accept-unverified-adopt, distinct from --approve) records a NON-gating declared_uploaded location that never skips a PUT. It reports adopted-vs-total, echoes no bucket names, prefixes, provider URLs, local paths, exact credential refs, tokens, or secret values, and the companion object-storage-upload/-plan/-verify commands accept the same --key-strategy family (default sha256_content_addressed, unchanged) and record the actual remote_key next to the content-addressed key_hint.

external-export-plan
  Plan a text-first Notion, Google Drive, or generic workspace export before large media downloads. Dry-run only; detects the broad workspace/database export trap, returns safe text-only and targeted first-pass command shapes, starts no export, calls no providers, reads no files, downloads no attachments, writes nothing, and echoes no provider URLs or local paths.

connection-import-plan
  Plan Notion connection evidence import into WOM typed-edge candidates. Dry-run only; maps relation properties, synced block references, database view/filter snapshots, internal links, page mentions, comment context, objet embeds, and notion_containment child page/database/view nesting to the base connection edge vocabulary including contains, with model-gap escalation instead of forced edge-type coercion, without calling Notion, reading exports, writing zets, writing edges, writing receipts, or echoing provider URLs or local paths.

connection-evidence-parser-contract
  Preview the future Notion connection evidence parser contract. Dry-run only; defines accepted input lanes, candidate edge record fields, static snapshot requirements, parser stages, and redaction rules without calling Notion, reading exports, reading comments, downloading media, executing a parser, writing candidate records, writing zets, writing edges, writing receipts, updating manifests, or echoing provider URLs, local paths, page titles, comment bodies, account ids, emails, tokens, or secret values.

connection-evidence-parse-fixture
  Parse a sanitized archive-internal Notion connection evidence fixture into candidate edge previews. Dry-run only; reads only an archive-relative fixture JSON such as workbench/connection-evidence.sample.json, emits not-written candidate previews, and never reads real exports, calls Notion, reads comments, downloads media, writes candidate records, writes zets, writes edges, writes receipts, updates manifests, or echoes provider URLs, local paths, page titles, comment bodies, account ids, emails, tokens, or secret values.

connection-edge-intelligence-plan
  Plan meaning/mechanism classification for sanitized connection fixture candidates. Dry-run only; separates relationship meaning from source mechanism, flags ambiguity and parsimony review needs, reports provisional labels such as format_variant/responds_to/fulfills/enabling/sequence, and never reads real exports, source bodies, derived-text bodies, comment bodies, calls providers or LLMs, writes candidate records, zets, edges, receipts, or manifests, or echoes provider URLs, local paths, page titles, comment bodies, account ids, emails, tokens, or secret values.

notion-nested-tree-plan
  Plan nested Notion child-page recovery from a sanitized tree fixture. Dry-run only; walks safe parent refs to assign each leaf to a known generation root, separates live content leaves from structure/template/view containers, reports untraceable leaves instead of guessing from a partial mirror, and never reads real exports, page titles, page bodies, comments, calls providers, writes zets, mints pages, writes edges, writes receipts, or echoes provider URLs or local paths.

notion-ancestor-crawl-plan
  Plan missing Notion ancestor crawl requests from a sanitized nested tree fixture. Dry-run only; groups missing parent records and rootless leaves into a crawl_request_queue for a future credential-bounded adapter, supports generation/root/ancestor/leaf scope filters for broad workspace queues, warns that generation-id scope can miss generation-unknown untraceable leaves, and never calls providers, reads real exports, page titles, page bodies, comments, downloads media, merges fixtures, writes zets, mints pages, writes edges, writes receipts, or echoes provider URLs or local paths.

notion-ancestor-fetch-adapter-execution-contract
  Preview the read-only execution and actor contract a future credential-bounded Notion ancestor fetch adapter must satisfy. Dry-run only; reuses the scoped crawl request planner, requires future live adapter execution to recurse up the parent chain until a stop condition, defines sanitized input/output fields, clarifies that the future live fetch subject is a WOM local credential-bounded adapter process rather than the AI chat runtime, treats client-supplied ancestor fixtures as sanitized safe-origin fallback input rather than required hand-rolled provider crawling, reports credential ref presence without echoing exact refs, and never calls providers, retrieves secrets, reads page titles or bodies, downloads media, writes fixtures, writes receipts, writes zets, or writes edges.

notion-media-fetch-adapter-execution-contract
  Preview the read-only execution and actor contract a future credential-bounded Notion media byte fetch adapter must satisfy. Dry-run only; reuses nested-tree planning to scope candidate content leaf pages, defines sanitized media result fixture fields, requires byte hashing before preservation claims, reports already_preserved/newly_preserved/fetch_failed as the preservation states, and never calls providers, retrieves secrets, refreshes signed URLs, downloads media bytes, hashes bytes, writes fixtures, updates object manifests, writes receipts, zets, or edges, or echoes provider URLs or media bytes.

notion-media-result-verification-plan
  Verify a sanitized notion_media_result_fixture against objects/manifests/files.jsonl. Dry-run only; checks fixture kind, source, object_id/sha256 agreement, preservation status, and manifest presence without calling providers, refreshing signed URLs, downloading media bytes, hashing bytes, reading object bytes, updating manifests, writing receipts, or echoing provider URLs, local paths, page titles, comments, tokens, secret values, or media bytes.

notion-block-mirror-tree-fixture-plan
  Build a sanitized nested tree fixture preview from reviewed Notion block mirror metadata. Dry-run only; derives safe refs and content classes from structural metadata, runs a nested-tree plan preview, and never calls providers, reads page titles or bodies, writes fixtures, writes zets, writes edges, or echoes provider URLs or local paths.

notion-ancestor-merge-plan
  Merge sanitized ancestor result nodes into a nested tree fixture preview and replan in memory. Dry-run only; reports merge conflicts and after-merge recovery/hold queues without writing fixtures, calling providers, reading page titles or bodies, writing zets, writing edges, or writing receipts.

notion-client-issue-verification-plan
  Verify a client Notion nested-tree issue from sanitized local fixtures. Dry-run only; orchestrates tree planning, optional block-mirror preview, missing ancestor crawl requests, and optional sanitized ancestor merge/replan, then returns a verdict without calling providers, reading page titles or bodies, writing fixtures, writing zets, writing edges, or writing receipts.

notion-client-fixture-request-plan
  Package the sanitized fixture request contract for client Notion issue verification. Dry-run only; lists accepted fixture kinds, required safe fields, redaction rules, and next verification commands without sending messages, calling providers, reading page titles or bodies, writing fixtures, writing zets, writing edges, or writing receipts.

zettel-edge
  Preview or approve one typed edge from a source zet to one verified target zet or manifested objet. Dry-run previews first; approve requires --reviewed-by and writes only one source zettel frontmatter edge plus one receipts/edges/*.zettel-edge.json receipt. `revert-edge` can later remove that exact edge from the receipt and write receipts/edges/reverts/*.zettel-edge-revert.json while preserving the original write receipt. It is not a bulk connection importer, exposes no MCP write tool, calls no providers, reads no real exports, writes no candidate records, updates no object manifests, and echoes no zettel body text, zettel titles, provider URLs, local paths, page titles, comment bodies, account ids, emails, tokens, or secret values.

zettel-edge-batch
  Preview or approve policy-gated typed edge batches from a reviewed JSON plan. Dry-run validates policy-writable rows through the single-edge gate without writing and preloads the object manifest once when batch rows target manifested objets. --plan resolves archive-relative first, then CWD-relative for compatibility. Approve requires --reviewed-by, writes only policy-matching new edges, writes receipts/edges/*.zettel-edge.json plus one receipts/edges/batches/*.zettel-edge-batch.json receipt when new rows are written, returns low-confidence or policy-mismatched rows in human_review_queue, and --skip-existing can separate already-written rows into skipped_existing_edges. `revert-batch` can later replay the batch receipt in reverse, remove all listed edges, write per-edge revert receipts plus one receipts/edges/batches/reverts/*.zettel-edge-batch-revert.json receipt, and preserve the original write receipts. It is not a real export parser, exposes no MCP write tool, calls no providers, reads no real exports, writes no candidate records, updates no object manifests, and echoes no zettel body text, zettel titles, provider URLs, local paths, page titles, comment bodies, account ids, emails, tokens, or secret values.

revert-edge
  Preview or approve removing one previously approved edge using receipts/edges/*.zettel-edge.json. Approve requires --reviewed-by, removes the matching edge_id from source zettel frontmatter, updates updated_at, writes receipts/edges/reverts/*.zettel-edge-revert.json, preserves the original edge receipt, exposes no MCP write tool, calls no providers, reads no real exports or zettel bodies, and echoes no zettel body text, zettel titles, provider URLs, local paths, page titles, comment bodies, account ids, emails, tokens, or secret values.

revert-batch
  Preview or approve removing all edges listed in receipts/edges/batches/*.zettel-edge-batch.json. Approve requires --reviewed-by, routes each item through the single edge revert gate, writes per-edge revert receipts and one batch revert receipt, preserves original write receipts, restores touched files if a batch revert fails partway through, exposes no MCP write tool, calls no providers, reads no real exports or zettel bodies, and echoes no zettel body text, zettel titles, provider URLs, local paths, page titles, comment bodies, account ids, emails, tokens, or secret values.

imap-mailbox-plan
  Plan a Gmail, Naver, or generic IMAP mailbox source with safe account, username, mailbox, and credential refs. Dry-run only; opens no connection, logs into nothing, reads no headers/bodies/attachments, sends no mail, changes no flags, stores no secrets, and writes no files.

imap-mailbox-operation-request-plan
  Compose a future IMAP mailbox operation approval request package. Dry-run only; combines IMAP source planning and credential policy checks without connecting, logging in, selecting mailboxes, reading headers/bodies/attachments, retrieving secrets, starting OAuth, or writing files.

imap-mailbox-adapter-readiness-plan
  Check readiness for a future IMAP mailbox adapter. Dry-run only; combines the IMAP operation request package with local runtime module checks without connecting, logging in, reading headers/bodies/attachments, retrieving secrets, starting OAuth, or writing files.

imap-mailbox-selection-plan
  Plan a future read-only IMAP mailbox message selection rule. Dry-run only; combines the IMAP operation request package with safe selector labels without connecting, logging in, selecting/searching a mailbox, listing message ids, reading headers/bodies/attachments, retrieving secrets, starting OAuth, or writing files.

imap-mailbox-adapter-manifest-plan
  Preview and schema-check a non-secret future IMAP adapter manifest. Dry-run only; writes no manifests and does not connect, log in, select/search a mailbox, list message ids, read headers/bodies/attachments, retrieve secrets, start OAuth, or call providers.

imap-mailbox-adapter-manifest-write
  Preview or approve writing a schema-checked, non-secret IMAP adapter manifest plus a write receipt. CLI-only; MCP exposes no live write tool. Does not connect, log in, select/search a mailbox, list message ids, read headers/bodies/attachments, retrieve secrets, start OAuth, or call providers.

imap-mailbox-adapter-audit-plan
  Preview a non-secret future IMAP adapter audit receipt. Dry-run only; combines the mailbox selection plan with safe receipt metadata without connecting, logging in, selecting/searching a mailbox, listing message ids, reading headers/bodies/attachments, retrieving secrets, starting OAuth, or writing files.

imap-mailbox-adapter-audit-write
  Preview or approve writing one non-secret IMAP adapter audit receipt under receipts/imap/adapter-audits/. CLI-only; MCP exposes no live write tool. Does not connect, log in, select/search a mailbox, list message ids, read headers/bodies/attachments, retrieve secrets, start OAuth, or call providers.

imap-mailbox-adapter-preflight-plan
  Compose readiness, manifest status, approval receipt verification, mailbox selection, and audit receipt preview into one final read-only gate before any future IMAP adapter execution. Dry-run only; writes nothing, connects to no mailbox, reads no mail, retrieves no secrets, starts no OAuth, and calls no providers.

imap-mailbox-adapter-execution-contract
  Print the read-only future execution contract for a local IMAP adapter. Dry-run only; wraps preflight, defines future inputs/output/receipt rules, writes nothing, connects to no mailbox, reads no mail, retrieves no secrets, starts no OAuth, and calls no providers.

imap-mailbox-header-metadata-scan
  Run the first approval-gated local IMAP header metadata scan. Dry-run previews without reading secrets; approved mode requires the manifest, approval receipt, execution contract, env username/app-password refs, and writes only a non-secret execution receipt. It reads no bodies or attachments and echoes no usernames, passwords, env var names, raw UIDs, subjects, senders, headers, local paths, or IMAP host values.

imap-mailbox-header-scan-receipt-audit
  Audit one IMAP header metadata scan execution receipt. Dry-run validates the receipt without writing; approved mode writes a non-secret audit receipt under receipts/imap/adapter-execution-audits/. It opens no IMAP connection, reads no environment variables, opens no keyring/password manager, reads no headers/bodies/attachments, and echoes no execution receipt path or candidate refs.

imap-mailbox-material-selection-plan
  Plan the next human message-material review lane from one IMAP header metadata scan execution receipt. Dry-run only; writes no queue files, opens no IMAP connection, reads no environment variables, opens no keyring/password manager, reads no headers/bodies/attachments, creates no derived text, and echoes no execution receipt path or candidate refs.

imap-mailbox-material-selection-record
  Preview or approve writing one non-secret material selection receipt from one-based candidate indexes. CLI-only; writes under receipts/imap/material-selections/ on approve, records no candidate refs or message material, opens no IMAP connection, reads no environment variables, opens no keyring/password manager, reads no headers/bodies/attachments, and echoes no execution receipt path or candidate refs.

imap-mailbox-material-capture-request-plan
  Plan a future body, attachment, or derived-text capture request from one non-secret material selection receipt. Dry-run only; reads no original execution receipt, writes nothing, opens no IMAP connection, reads no environment variables, opens no keyring/password manager, reads no headers/bodies/attachments, creates no derived text, and echoes no material selection receipt path, execution receipt path, or candidate refs.

imap-mailbox-material-capture-execution-contract
  Print the future execution contract for body, attachment, or derived-text capture from one non-secret material selection receipt. Dry-run only; reuses the capture request validation, writes nothing, opens no IMAP connection, reads no environment variables, opens no keyring/password manager, reads no headers/bodies/attachments, creates no derived text, and echoes no material selection receipt path, execution receipt path, or candidate refs.

imap-mailbox-material-capture-approval-plan
  Preview or approve writing one non-secret material capture approval receipt. CLI-only; writes under receipts/imap/material-capture-approvals/ on approve, records no material selection receipt path, candidate refs, execution receipt path, or message material, opens no IMAP connection, reads no environment variables, opens no keyring/password manager, reads no headers/bodies/attachments, and creates no derived text.

imap-mailbox-material-capture-approval-audit
  Audit one non-secret material capture approval receipt against its material selection receipt. Dry-run only; writes nothing, reads no original execution receipt, opens no IMAP connection, reads no environment variables, opens no keyring/password manager, reads no headers/bodies/attachments, creates no derived text, and echoes no approval receipt path, material selection receipt path, execution receipt path, or candidate refs.

human-artifact-store
  Plan a user-facing note/workspace/publication surface such as WordPress, Joplin, Notion, Obsidian, Evernote, or generic Markdown. Dry-run only; writes nothing, calls no providers, creates no notes, publishes no posts, and keeps system/AI artifacts separate from human-readable artifacts.

zet-surface-prototype
  Preview a user-selected ZET surface prototype for WordPress, Joplin, Notion, or Obsidian. Dry-run only; writes nothing, calls no providers, requests no tokens, creates no notes, publishes no posts, writes no vault files, mints no zets, and runs no ZET transport.

prehashed-objet-ledger
  Preview or approve-register one or more already-hashed external content-addressed object/objet ledgers. Dry-run counts sha256/byte-size rows, optional safe MIME values through --mime-field, skipped null-sha rows, cross-ledger duplicates, and planned manifest writes without reading blob bytes. Approved mode appends external manifest records and writes a receipt. MCP exposes only the read-only preview as prehashed_objet_ledger_preview.

object-storage-upload-evidence
  Preview or approve-register reviewed external object-storage upload evidence for existing manifest objects. Approved mode writes one receipt under receipts/providers/object-storage-upload-evidence/ and appends object_storage locations with declared_uploaded availability. It does not prove remote availability by itself and does not call providers, read object bytes, compute local hashes, upload, download, sync, create provider URLs, or retrieve secrets. MCP exposes no write tool for this surface.

object-storage-upload-evidence-audit
  Check a reviewed upload evidence receipt against local manifest locations. Dry-run only; it writes no audit receipt, performs no remote availability check, and echoes no receipt path, manifest path, object ids, location records, provider URLs, bucket names, account ids, emails, tokens, or secret values. MCP exposes no tool for this surface.

resolve-objet-ref
  Resolve one sha256 objet reference to safe local archive-relative candidates and external store labels. Dry-run only; reads the object manifest, writes nothing, echoes no absolute local paths or provider URLs, calls no providers, creates no presigned URLs, downloads nothing, and hashes no object bytes.

zettel-objet-links
  Preview safe local-client objet link candidates referenced by one zettel. Dry-run only; scans sha256 and objet:sha256 refs, writes nothing, echoes no body text, frontmatter values, absolute local paths, provider URLs, or object bytes, and calls no providers.

notion-objet-link-plan
  Plan Notion provider locator to manifested objet links for one zettel. Dry-run only; groups provider locators by opaque fingerprint, matches reviewed manifest metadata, writes nothing, echoes no provider URLs, zettel body text, frontmatter values, page titles, absolute local paths, or object bytes, and calls no providers.

notion-objet-link-index
  Index Notion provider locator to manifested objet link candidates across non-redacted zettels. Dry-run only; writes nothing, echoes no provider URLs, zettel body text, frontmatter values, page titles, absolute local paths, or object bytes, and calls no providers.

notion-objet-import-clue-audit
  Audit imported Notion zettels for preserved material clues after provider locator omission. Dry-run only; writes nothing, reads no zettel body text, rewrites no body text, writes no edges or receipts, reads no object bytes, calls no providers, and echoes no provider URLs, provider locator text, page titles, frontmatter values, absolute local paths, account ids, emails, tokens, or secret values.

notion-objet-source-map-link-plan
  Plan zettel-to-objet material-link candidates from source maps and optional download/retrieval ledgers when imported zettel bodies no longer contain provider locators. Dry-run only; writes nothing, rewrites no body text, writes no edges or receipts, reads no object bytes, calls no providers, and echoes no provider URLs, provider locator text, page titles, zettel body text, frontmatter values, absolute local paths, account ids, emails, tokens, or secret values.

notion-objet-link-rewrite-plan
  Validate one reviewed locator_fingerprint and object_id pair before an approved conversion. Dry-run only; writes nothing, rewrites no body text, writes no edges, echoes no provider URLs, zettel body text, frontmatter values, page titles, absolute local paths, or object bytes, and calls no providers.

notion-objet-link-convert
  Preview or approve converting one reviewed locator/object match into an embed edge. Approve requires --reviewed-by and --expected-occurrence-count, re-runs the rewrite plan, writes through the zettel-edge gate, and creates a conversion receipt. It does not rewrite body text, replace provider locator text, expose an MCP write tool, call providers, read object bytes, or echo provider URLs, body text, titles, frontmatter values, account ids, emails, tokens, or secret values.

notion-objet-manifest-locator-label
  Preview or approve adding one reviewed non-secret Notion locator fingerprint to one object manifest record. Approve requires --reviewed-by and writes only objects/manifests/files.jsonl plus a receipt under receipts/objects/notion-locator-labels/. It stores no raw provider locator text, exposes no MCP write tool, reads no zettel bodies or object bytes, rewrites no zettels, writes no edges, calls no providers, and echoes no provider URLs, zettel body text, zettel titles, page titles, account ids, emails, tokens, or secret values.

view-health
  Diagnose saved view hit counts and facet distributions against the generated local index. Dry-run only; writes nothing, rebuilds no index, rewrites no views or facets, reads no zettel bodies or object bytes, echoes no zettel titles, absolute local paths, or provider URLs, and calls no providers.

index-health
  Check generated index drift before index-backed navigation. Dry-run only; writes nothing, rebuilds no index, edits no zettels, reads no object bytes, echoes no zettel body text, zettel titles, absolute local paths, or provider URLs, and calls no providers.

credential-keepassxc-command-plan
  Verify a credential access approval receipt through the policy gate, then preview a safe KeePassXC CLI add command shape. Dry-run only; runs no keepassxc-cli, opens no vault, stores no .kdbx path, passes no secret through argv or stdin, writes no vault entry, and echoes no exact credential ref.

credential-keepassxc-write
  Execute a minimal KeePassXC CLI add after verifying a credential access approval receipt. Dry-run previews first; approved mode is CLI-only, requires a local .kdbx path, invokes keepassxc-cli add --password-prompt, writes a non-secret execution receipt, blocks replay with the same approval receipt, and echoes no secret value, exact credential ref, database path, username, email, token, provider URL, or raw adapter output.

beginner-setup-manual
  Print beginner-friendly secret vault, KeePassXC CSV bulk migration, Cloudflare R2 object-storage setup, Notion nested recovery, and derived-text tool setup steps. Dry-run only; explains what to do in external UIs and local terminals, including R2 Korean/English label hints, the Access Key ID plus Secret Access Key pair used by S3-compatible clients, and a plain-language Notion location-recovery flow before one-time approval and live structure fetch handoff. It shows safe non-secret labels and dry-run commands, writes nothing, opens no vault/provider dashboard, reads no CSV, imports or merges no database, creates no bucket/API token, writes no approval receipt, runs no Notion location fetch, installs no tools, runs no extraction, deletes no temporary files, and echoes no secret values or local paths.

ai-response-concept-guide
  Print beginner-facing AI explanation cards for sha256 object identity vs location, manifests vs zets, and the objet -> derived text -> zet layer split. Dry-run only; returns safe scripts, analogies, routing hints, and overclaim guardrails without reading source bytes or derived-text bodies, writing manifests or receipts, drafting or minting zets, uploading objects, calling providers, or echoing source filenames, local paths, provider URLs, account ids, emails, tokens, or secret values.

connected-accounts
  Summarize provider/source account metadata and credential store types. Dry-run only; reads metadata from provider bindings, source bindings, and ignored local credential inventory, writes nothing, opens no vault/keyring/browser store, calls no providers, opens no IMAP connection, and echoes no exact credential refs or secret values.

credential-semantic-extraction-recipe
  Print a read-only semantic recipe for splitting complex credential notes before plaintext migration. Dry-run only; reads no plaintext file, detects no secret values, opens no password manager/keyring/browser store, writes nothing, calls no providers, and returns no secret values to AI.

derive-text-coverage
  Check derived-text coverage for textual or plausibly textual objets without reading source bodies. Dry-run only; compares files.jsonl to derived-text.jsonl, classifies missing/encrypted items, can use existing derived-text records as a fallback textual signal for older prehashed manifests, returns manifest_quality so missing or unknown tool_version/tool metadata blocks false complete claims, echoes no source filenames or local paths, and writes nothing.

derive-text-toolchain
  Recommend a derived-text extraction route for one extension or MIME hint. Dry-run only; suggests parser/OCR/ASR/vision routing for PDF, Office, HWP/HWPX, images, audio, and text formats without running tools or calling providers.

derive-text-doctor
  Check local derived-text extraction tool readiness without echoing executable paths or import paths. Dry-run only; reports boolean readiness for parser/OCR/conversion/ASR route families and writes nothing. Optional --tool-hints accepts a local JSON file for PATH-missing executables without echoing the hint file path or executable paths.

derive-text-agent-contract
  Print the derived-text agent operating contract. Dry-run only; encodes the maximum textual coverage default and required preflight order without reading source bytes or writing files.

source-intake
  Classify one source/objet locator before draft creation. Dry-run only; returns safe source refs without reading bodies, hashing, copying, uploading, importing, OCR, transcription, extraction, or provider API calls. It can optionally validate a project-intake decisions receipt as session context only.

tiro-import-plan
  Plan Tiro meeting transcript and audio-objet import from an archive-internal manifest. Dry-run only; preserves meeting metadata, speaker turns, timestamps, confidence, and optional audio objet refs as structure, but echoes no transcript text, participant names, source URLs, audio filenames, local paths, account ids, emails, tokens, or secrets. It calls no Tiro API, reads no audio bytes, writes no derived text, drafts no zets, and mints nothing.

source-intake-record
  Validate and record a reviewed source-intake dry-run JSON plan under receipts/sources/. Dry-run previews first; approved mode writes one redacted plan record only.

objet-capture-selection
  Build a reviewed selection manifest for one staged file after source-intake recording. Dry-run hashes the staged file and previews the manifest; approved mode writes only the selection JSON for a later, separate objet-capture dry-run/approve step.

derive-text capture
  Register an already extracted UTF-8 text file as a provenance-aware derived text record for one existing object_id. Dry-run previews first; approved mode stores the text body, appends objects/manifests/derived-text.jsonl, and writes a receipt. Batch manifest rows require source_object_id, text_file, derivation_kind, tool_name, tool_version, and review_status; the item schema lives at schemas/derived-text-capture-manifest-item.schema.json. It does not run OCR, ASR, parser, LLM vision, provider APIs, drafting, or minting.

project-intake-plan
  Plan one staged project folder intake session. Dry-run only; reports top-level counts, next session questions, staging-convention status, and would_change: [] without reading file bodies, exposing child names, hashing, copying, uploading, drafting, minting, or deleting.

project-intake-unpack-queue
  Queue top-level staged items for human-guided unpacking. Dry-run only; returns opaque item refs, coarse kind/extension/size hints, and the next human selection question without exposing entry names or local paths, reading file bodies, hashing, copying, uploading, drafting, minting, or cleaning.

project-intake-unpack-choice
  Record one human-confirmed unpack choice after the queue step. Dry-run validates only; approved mode writes a receipt under receipts/project-intake-unpack without exposing staged entry names, local paths, file bodies, or choice notes in command output.

project-intake-session-guide
  Show the next safe human-guided project intake step from either a project slug, staged folder, or existing decisions receipt. Dry-run only; writes nothing, echoes no decision values, reads no bodies, captures nothing, drafts nothing, mints nothing, uploads nothing, and cleans nothing.

project-intake-decisions
  Validate and record human-reviewed project intake checklist decisions. Dry-run validates only; approved mode writes a receipt under receipts/project-intake. It does not run source intake, capture objets, create drafts, mint zets, call providers, or clean staged folders.

project-intake-record-answer
  Append one human-reviewed project intake answer to a new or existing intake session. Dry-run validates only; approved mode writes a new decisions receipt without echoing current or previous answer values, and without running source intake, capture, drafting, minting, provider calls, or cleanup.

project-intake-status
  Review a recorded project intake decisions receipt. Dry-run only; reports checklist coverage, receipt integrity, and next safe actions without echoing answer text or authorizing automatic execution.

block-header
  Preview a derived block header for one draft or canonical zet. Dry-run only; reads the zet file, derives refs/hashes/provenance/policy/receipt metadata, and writes nothing.

shared-update-record-review
  Preview one local archive-contained ZET shared update record JSON before receiver-side renewal. Dry-run only; writes nothing and does not update feeds, trust, import, attest, sign, anchor, call providers, write receipts, project, or run ZET transport.

shared-update-record-review-index
  Preview a compact deterministic index for direct-child local shared update record JSON files under an archive-relative directory. Dry-run only; reuses the single-record review policy, writes nothing, and echoes no body text or local absolute paths.

shared-update-attestation-review
  Approve recording a local shared update attestation/review record and matching receipt after `shared-update-record-review` passes. This writes exactly two JSON files with exclusive-create semantics and keeps trust, import, signatures, anchors, feed updates, provider calls, projection, and real ZET transport closed.

shared-update-route-preview
  Preview the candidate receiver-side route for one local shared update record: delegate, attest, anchor, or none. Dry-run only; reuses the single-record review policy, writes nothing, echoes no unsafe free-form route metadata, and does not authorize or perform the route.

zet-transport-plan
  Preview a planning-only ZET would-transport risk/control model for one local shared update record and one future method. Dry-run only; reuses the single-record review policy, writes nothing, creates no keys, sends nothing, calls no providers, starts no workers, and runs no ZET transport.

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

record-attestation-review-candidate
  Preview or approve recording a local untrusted attestation review candidate from a saved candidate plan. Approved mode writes only the candidate JSON and candidate receipt; it never trusts, imports, attests, signs, mints, accepts, shares, calls providers, or runs ZET transport.

attestation-candidate-review
  List and validate recorded foreign block attestation review candidates. Read-only; it writes nothing and validates candidate records, candidate receipts, quarantine cases/receipts, and decision records/receipts before any later human review.

attestation-statement-draft
  Preview a non-binding attestation statement draft for one recorded candidate. Dry-run only; it writes nothing and never creates trust, import, attestation, signatures, receipts, minting, sharing, provider calls, or ZET transport.

record-attestation-statement-draft
  Preview or approve recording a local untrusted attestation statement draft from a saved draft preview. Approved mode writes only the statement draft JSON and statement draft receipt; it never trusts, imports, attests, signs, mints, accepts, shares, calls providers, or runs ZET transport.

attestation-statement-draft-review
  List and validate recorded foreign block attestation statement drafts. Read-only; it writes nothing and validates statement draft records, statement draft receipts, candidate records/receipts, quarantine cases/receipts, and decision records/receipts before any later human review.

attestation-statement-draft-decision
  Preview one safe next human-review route for a recorded statement draft. Dry-run only; it writes nothing and never records acceptance, trust, import, attestation, signature, mint, sharing, WordPress publishing, provider calls, or ZET transport.

init
  Initialize a personal, company, or family archive from a safe template.

validate
  Run strict archive validation.

list-zettels
  List canonical and/or draft zettels.

zet-catalog --dry-run
  Enumerate every local zet node's available compact frontmatter abstract state and complete edge projection in deterministic pages. `--projection reading --coverage-mode strict` gives compact checksum-chained node coverage. It measures items, compact service-result, and response-envelope cost; optional `--response-envelope-reserve-tokens` partitions a requested total without changing the old items-only default. Keep cursor zero full, then optionally use `--response-profile continuation` to omit repeated scope diagnostics while retaining items, readiness, snapshot, token, and chain evidence. Optional verified-seed order remains exhaustive, and opt-in `routed_reading` adds each item's seed/tie/component reason at a higher token cost. Separate signals report node coverage, first-read availability, and unique-id follow-up, while strict chain hashes distinguish duplicate-id file entries without returning paths. `--progress` reports content-free scan counts and heartbeat on stderr; scratch-scoped `--output` can keep the full JSON off stdout. It ranks nothing, writes no map/state, reads no body, and requires no generated index. A new CLI process still performs its own live scan.

zet-catalog-pass --dry-run --output .wom-scratch/diagnostics/<new-name>.jsonl
  Complete the same strict continuation chain in one CLI process. It parses frontmatter on the first page, reuses only ephemeral process memory for intermediate pages, then revalidates local state before completion. It publishes one private header/pages/footer JSONL only after success, reports the exact output SHA-256, refuses overwrite, removes its new partial on handled failure, bounds output with `--max-output-mib`, and prints no items to stdout. Forced termination may leave a hidden private partial; later runs count but never read or auto-delete it. The file is not a record or receipt: read it incrementally, never commit it, and delete it after use.

zet-catalog-pass-read --dry-run --input <scratch.jsonl> [--page-index <n>] --expected-sha256 <sha256>
  Stream and validate the whole complete artifact before returning at most one selected private page. Broken schemas, page/cursor continuity, snapshot, final coverage, projection fields, body-exclusion guards, or SHA-256 block without returning a page. It writes nothing and offers content-free `--progress`.

zet-catalog-pass-cleanup --input <scratch.jsonl> --expected-sha256 <sha256> --dry-run|--approve --reviewed-by <actor>
  Preview or approve deletion of one complete matching private scratch JSONL after consumption. It never deletes hidden partials or archive records, writes no receipt, and echoes no reviewer value.

zet-revision-plan --zettel-id <safe-id> --proposal .wom-scratch/revisions/<private>.md --dry-run
  Validate one complete private correction proposal against the exact current canonical zet before any canonical write. It freezes identity, creation, lifecycle, and original creator metadata; checks explicit abstract, body locator, edges, provenance, visibility, quality blockers, and semantic change; and returns hashes plus fixed change categories without echoing the actual id, path, filename, title, abstract, body, custom frontmatter value, or secret. A green plan grants no write authority; the atomic approved writer is a later capability.

zet-abstract-backfill-plan --proposal .wom-scratch/abstract-backfill/<private>.jsonl --dry-run
  Validate bounded missing-abstract proposals against exact current canonical file bytes. It checks the shipped row schema, identity/status, hash, first-read absence, safe abstract shape, and a byte-preserving one-field insertion. It returns only row indexes, counts, and hashes; writes nothing and echoes no ids, paths, bodies, abstracts, or proposal filename.

zet-abstract-backfill-write --proposal .wom-scratch/abstract-backfill/<private>.jsonl --expected-proposal-sha256 <sha256> --dry-run|--approve
  Preview first. A new approved write also requires `--reviewed-by` and `--affirm-abstracts-reviewed`. It reruns the plan, revalidates every exact canonical hash, adds only `frontmatter.abstract`, and writes one hash-evidence receipt. Any runtime item/receipt failure restores all attempted canonical bytes. A matching receipt makes retries no-write `already_applied`. Per-file and batch byte limits bound rollback memory; forced termination has no crash-recovery journal.

zet-abstract-backfill-revert --receipt receipts/revisions/abstract-backfill/<digest>.zet-abstract-backfill.json --expected-receipt-sha256 <sha256> --dry-run|--approve
  Dry-run audits the immutable applied receipt, every current after/body/abstract hash, and deterministic removal back to the exact recorded before hash. A new approved revert also requires `--reviewed-by` and `--affirm-abstract-removal-reviewed`. It preserves the source receipt, writes one text-free revert receipt last, restores the applied state on runtime failure, and returns no-write `already_reverted` on a matching retry. Any later canonical edit blocks; forced termination remains outside the in-process rollback guarantee.

zet-abstract-backfill-receipt-audit --dry-run --max-receipts 5000 --max-locks 5000 --max-problems 100
  Audit every bounded apply/revert receipt lifecycle and recognized leftover transaction lock. Healthy applied/reverted lifecycles become counts plus one audit digest; only bounded hash/index problem records are returned. Completed-lock residue is a warning, while a lock without its matching receipt blocks as an unresolved transaction. The command reads lock names but never lock content, echoes no private receipt/zet/text/reviewer/path value, and writes or deletes nothing.

read-zettel
  Read one zettel by id or archive-relative path. Use `--section overview` for the compact first read; MCP `read_zettel` accepts the same section values while keeping `body` as its compatibility default. Non-redacted results include exact canonical file SHA-256 and decoded returned-body SHA-256 so a private revision proposal can bind to the version actually read; redacted hashes are suppressed.

tools/benchmark_zet_catalog.py
  Build a temporary synthetic 1,000- or 10,000-zet archive, exhaustively page the live catalog in full/reading, page/strict, and path/seeded order modes, verify unique coverage and strict claim readiness, and report order, scan, timing, cache, and heuristic workload evidence. It reads no real archive and persists no fixture.

create-draft
  Create a draft zettel in inbox/. Optional --abstract stores a bounded compact first read. With --dry-run, preview a profile-aware inbox draft zet without writing files. It can consume a validated source-intake plan with --source-intake-plan and a validated prompt-boundary report with --prompt-boundary-report.

mint-zet --dry-run
  Check whether a draft zet can be minted and preview canonical path, mint receipt, and draft snapshot without writing.

mint-zet --approve --reviewed-by
  Mint an inbox draft zet into canonical private archive memory and write a receipt plus draft snapshot.

mint-zet-batch --plan --dry-run
  Preview minting many reviewed draft zets from one JSON plan in one WOM-kit process. Aliases include bulk-mint and bulk-mint-zet.

mint-zet-batch --plan --approve --reviewed-by
  Mint plan-approved draft zets, keep per-item mint receipts, and write one batch receipt without per-item shell process loops.

retire-draft --dry-run
  Verify that an inbox draft is already backed by canonical mint artifacts before cleanup. Writes nothing and deletes nothing.

retire-draft --approve --reviewed-by
  Remove a verified already minted inbox draft and write a retired-draft receipt while preserving the canonical zet, mint receipt, and draft snapshot.

retire-draft-batch --plan --dry-run
  Preview retiring many already minted inbox drafts from one JSON plan in one WOM-kit process. Aliases include bulk-retire and bulk-retire-draft.

retire-draft-batch --plan --approve --reviewed-by
  Remove verified plan-approved inbox drafts, keep per-item retire receipts, and write one batch receipt without per-item shell process loops.

mint-zettel
  Transitional compatibility alias for mint-zet.

promote --dry-run
  Legacy-compatible name for the older promotion readiness check.

promote --approve --reviewed-by
  Legacy-compatible command that promotes an inbox draft and writes the older promotion receipt.

index
  Build a generated local SQLite search index at db/archive-index.sqlite.

search
  Search zettels, object manifest entries, derived text records, views, and source map entries through the generated index.

parcel
  Create a portable parcel from a saved view. The v0.2 compatibility path still writes under workpacks/.

pack
  Transitional compatibility alias for parcel.

admit --dry-run
  Preview admitting a parcel/workpack without mutating the target archive.

import --dry-run
  Transitional compatibility alias for admit.

import-external --dry-run
  Preview a Notion or Google Drive export import without mutating the target archive. Manifest items that contain safe object refs, source refs, facets, or zettel id overrides report counts and routing metadata without echoing private values.

import-external --approve --reviewed-by
  Import Notion or Google Drive export items as inbox drafts and write an import receipt. Explicit safe metadata from the manifest is preserved in draft source_refs and facets; use --provider-locator-policy object-ref to convert supported Notion body locators to a reviewed objet ref when exactly one object source ref is present.

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

upgrade-check --dry-run
  Check Doctor, recovery, restore-drill, and manual-upgrade readiness. Optional `--progress` emits content-free liveness to stderr; optional scratch-scoped `--output` stores the full JSON and prints a compact stdout summary.

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

`profile-wallet` treats a WOM profile as wallet-ready identity context: the profile is the human-facing selector, the WOM node is the subject/principal, and the future WOM wallet layer is where signing/capability authority can later live. v0.2.43 does not generate private keys, sign data, store seed phrases, create wallets, or call blockchain/provider APIs.

Object storage / objet setup example:

```powershell
python wom-kit\cli\archive.py object-storage wom-kit\examples\fake-life-archive `
  --dry-run `
  --provider cloudflare-r2 `
  --profile-id profile:personal:username `
  --profile-slug username `
  --storage-account-ref storage:account:username `
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

`archive mint-zet --dry-run` checks the minting gate using `minting_rules` in `zettel-kasten/zettel-rules.yml`, with legacy `promotion_rules` as a v0.2 fallback. It reports blockers, warnings, missing human-review items, near duplicates, `duplicate_check` metadata, the proposed canonical path, the proposed mint receipt path, and the proposed draft snapshot path. When `db/archive-index.sqlite` is current, duplicate checks use the generated index instead of rereading every canonical zet body; otherwise the command falls back to the live scan. It writes nothing. `archive mint-zettel` remains a v0.2 compatibility alias.

`archive retire-draft --dry-run|--approve` closes the lifecycle gap after a draft has already been minted. Dry-run verifies that the inbox draft, canonical zet, mint receipt, draft snapshot, archive-relative paths, and SHA-256 evidence all agree. It can also accept a mint target SHA that changed only through approved post-receipt zettel-edge writes. Approved mode requires `--reviewed-by`, removes only that verified inbox draft, writes `receipts/mint/retired-drafts/*.retire-draft.json`, and preserves the canonical zet, original mint receipt, and draft snapshot.

`archive mint-zet-batch --plan <json> --dry-run|--approve` and `archive retire-draft-batch --plan <json> --dry-run|--approve` are the batch-safe forms for large WOM real-use runs. They consume archive-relative JSON plans, run inside one WOM-kit process, keep the same single-item gates for each item, support `--skip-existing` and `--max-items`, return `failed_items` for partial failures, and write one batch receipt under `receipts/mint/batches/` or `receipts/mint/retired-drafts/batches/`. For post-edge canonical zets, retired-draft batch validation builds one edge receipt index for the batch and approved writes reuse the verified plan with current-file SHA replay checks. They do not spawn one shell process per item, rescan edge receipts once per item, call providers, read unrelated source files, or echo zettel body text.

`archive source-intake --dry-run` is the safe classification step before drafting from a source/objet. It accepts exactly one locator, returns `source_refs_for_draft`, reports object storage context, and writes nothing. It does not read file bodies, hash, copy, upload, import, OCR, transcribe, extract, call provider APIs, create drafts, or mint.

`archive tiro-import-plan --manifest workbench/tiro-meeting.sample.json --dry-run` is the meeting-specific planning step before derived-text capture or drafting from a Tiro transcript. It reads only a reviewed archive-internal JSON manifest, checks meeting metadata, speaker turns, timestamps, transcript segment shape, confidence fields, and optional audio objet refs, then returns counts and safe source refs without echoing meeting titles, participant display names, transcript text, source URLs, audio filenames, local paths, account ids, emails, tokens, or secrets. It writes nothing and calls no Tiro API.

`archive derive-text capture` is the safe registration step after an external parser, OCR tool, ASR tool, or vision model has already produced a UTF-8 text file. The source object must already exist in `objects/manifests/files.jsonl`. Dry-run writes nothing; approved mode stores the text body under `objects/derived-text/sha256/`, appends `objects/manifests/derived-text.jsonl`, and writes `receipts/derived-text-capture/*.json`.

For `derive-text capture --from-manifest`, each JSONL row must include
`source_object_id`, `text_file`, `derivation_kind`, `tool_name`,
`tool_version`, and `review_status`. See
`schemas/derived-text-capture-manifest-item.schema.json` for the row shape.
`tool_version` is the extractor/parser/OCR/ASR/model/script version that made
the text; for a reviewed one-off script, use a stable local script label rather
than leaving it blank.

`archive derive-text coverage --dry-run` also checks existing
`objects/manifests/derived-text.jsonl` records through `manifest_quality`.
Coverage is not considered complete when derived-text rows are missing
`tool_version`, use weak labels such as `unknown`, or lack required extraction
metadata.

```powershell
python wom-kit\cli\archive.py derive-text capture .\tmp-my-archive `
  --text-file .\workbench\example-extracted.txt `
  --source-object-id sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa `
  --derivation-kind parser `
  --tool-name example-parser `
  --tool-version 1.0.0 `
  --review-status unreviewed `
  --dry-run `
  --format json
```

The first implemented vocabulary is deliberately small: `derivation_kind` is one of `parser`, `ocr`, `asr`, or `llm_vision`; `review_status` is one of `unreviewed` or `human_corrected`. The command does not extract text by itself, call providers, create drafts, mint zets, or store the local source text path in the manifest.

`archive project-intake-plan --dry-run` is the safe planning step before a user and AI inspect one staged project folder together. It reports only top-level counts, staging-convention status, concrete next-session questions, and `would_change: []`. It does not expose child names, read file bodies, recurse through the folder, hash, copy, upload, import, create drafts, mint, or delete the staged folder.

`archive project-intake-session-guide --project-slug <slug>|--staged-folder <folder>|--receipt <receipt> --dry-run` is the one-screen guide for the human-guided intake loop. It points to the next safe human turn and next command without doing the work. It never creates folders, writes decisions, echoes previous answer values, reads file bodies, calculates content hashes, captures objets, creates drafts, mints zets, uploads, or cleans staged folders.

`archive project-intake-unpack-queue --staged-folder <folder> --dry-run` is the first unpacking queue. It lists top-level staged items as opaque `item-0001` style refs with kind, safe extension, and coarse size bucket only. Optional `--receipt <project-intake-receipt>` lets the queue report whether the session is ready for item selection. It does not expose entry names or local paths, read bodies, hash content, classify automatically, run source-intake, capture, draft, mint, upload, or clean.

`archive project-intake-unpack-choice --choice <json-file> --receipt <project-intake-receipt> --staged-folder <folder> --dry-run|--approve` records exactly one human-confirmed queue choice after the project-intake checklist is complete. The choice JSON must use `schema: wom-kit/project-intake-unpack-choice/v0.1`, an opaque `item_ref` such as `item-0001`, an allowed `intended_action`, and `human_confirmed: true`. Dry-run validates the choice, completed receipt, and current queue; approved mode writes `receipts/project-intake-unpack/*.project-intake-unpack-choice.json`. Command output includes the item ref, intended action, and queue digest only. It does not expose staged entry names, local paths, file bodies, or choice notes, and it does not run source-intake, capture, draft, mint, provider sync, or cleanup.

`archive project-intake-decisions --decisions <json-file> --dry-run|--approve` is the first persistence step after that conversation. The JSON file must use `schema: wom-kit/project-intake-decisions/v0.1`, include a safe `session_id`, and contain reviewed `decisions` keyed by the checklist ids from `project-intake-plan`. Dry-run reads and validates the decision file but prints only counts, checklist ids, a decision hash, blockers, warnings, and the proposed receipt path. Approved mode also requires `--reviewed-by <actor>` and writes `receipts/project-intake/*.project-intake-decisions.json`. It records the reviewed answers as local archive evidence but still does not inspect staged file bodies, run source-intake, capture objets, derive text, create drafts, mint zets, call providers, or approve cleanup.

`archive project-intake-record-answer --answer <json-file> --session-id <id>|--receipt <receipt> --dry-run|--approve` is the one-question-at-a-time persistence path for the human-guided loop. The answer JSON must use `schema: wom-kit/project-intake-answer/v0.1`, include exactly one checklist id, and contain only the human-reviewed answer for the current prompt. Dry-run validates the new answer and, when continuing, the previous receipt; approved mode writes a new `project-intake-decisions` receipt that can be checked by `project-intake-status`. Console output includes counts, checklist ids, hashes, and paths only. It does not echo current or previous answer values, inspect staged file bodies, run source-intake, capture objets, derive text, create drafts, mint zets, call providers, or approve cleanup.

`archive project-intake-status --receipt <receipt> --dry-run` reads one approved project-intake decision receipt and reports whether the receipt is intact, which checklist ids are answered, which ids are still missing, and what the next safe actions are. When checklist ids are missing, it also returns `next_review_prompts` so an AI can ask the user the next human-review questions without inventing answers. It does not echo the recorded answer values and never turns the receipt into automatic execution authority.

`archive source-intake --project-intake-receipt <receipt> --dry-run` can carry that reviewed session receipt into a one-locator metadata plan. The receipt must pass the same status check, and the resulting `project_intake_context` includes only receipt path, session id, reviewer metadata, decision hash, checklist coverage, and readiness. It does not include answer values and does not approve source capture, draft creation, minting, provider calls, or cleanup.

`archive source-intake-record --source-intake-plan <json-file> --dry-run|--approve` validates a reviewed `source-intake --dry-run` JSON file and, with approval, stores the redacted plan under `receipts/sources/` for later capture evidence. It blocks unredacted local paths, provider URLs, tokens, and secrets. It does not read file bodies, calculate content hashes, capture objets, create drafts, mint zets, call providers, upload, or clean.

`archive objet-capture --project-intake-receipt <receipt> --dry-run|--approve` can carry the same reviewed session receipt into an explicit capture selection. A selection manifest may also include `project_intake_receipt_path`; if both are present they must match. Invalid or tampered intake receipts block before staged bytes are read. The context is recorded in the capture result and approved capture receipt, but it still does not approve drafting, minting, provider calls, or cleanup.

For external project migrations, the intended manual spine is:
`project-intake-plan -> project-intake-next-question -> project-intake-decision-template -> project-intake-record-answer -> project-intake-status -> project-intake-unpack-queue -> project-intake-unpack-choice -> source-intake --project-intake-receipt -> source-intake-record -> objet-capture-selection -> objet-capture --project-intake-receipt -> derive-text capture when text already exists -> create-draft --source-intake-plan -> mint-zet after approval -> staged-cleanup-check`. This is not one automatic bulk importer; every arrow is still a review boundary.

`archive human-artifact-store --surface-kind <kind> --dry-run` previews the contract for a user-facing human artifact app or surface. Supported kinds are `wordpress`, `joplin`, `notion`, `obsidian`, `evernote`, `generic_markdown`, and `generic_workspace`. The command keeps three roles separate: raw/original data, human-readable artifacts, and system/AI artifacts such as manifests, source maps, receipts, indexes, hashes, and version history. It writes nothing, calls no providers, starts no OAuth, creates or updates no notes, publishes no posts, uploads no files, mints no zets, and runs no ZET transport.

MCP exposes the same read-only preview as `human_artifact_store_plan`.

`archive zet-surface-prototype --surface-kind <kind> --surface-ref <safe-ref> --dry-run` previews a ZET surface prototype for `wordpress`, `joplin`, `notion`, or `obsidian`. It reports the surface role, integration family, safe settings schema preview, risks, receipt requirements, and next future adapter steps. It is still only a planning surface: it writes nothing, calls no provider, starts no OAuth, asks for no token, creates no note, publishes no post, writes no vault file, creates no projection receipt, mints no zet, and runs no ZET transport. MCP exposes the same read-only preview as `zet_surface_prototype_plan`.

`archive prehashed-objet-ledger --ledger <jsonl> --dry-run` previews one or more already-hashed external content-addressed store ledgers, including Notion source-export ledgers. `--ledger` may be repeated so retrieval, deep, and workspace download ledgers can be deduped in one run. By default it expects `sha256`, `bytes`, and optional `mime` fields; use `--mime-field <field>` if the ledger uses another safe MIME field name. It counts valid, skipped, invalid, duplicate, MIME-present, and total declared bytes, and echoes no row values, filenames, URLs, or local paths. Rows with null or empty `sha256` are skipped for aid-dedup style ledgers; malformed sha strings remain invalid. `--approve --reviewed-by <actor> --store-ref <safe-label>` appends external manifest records to `objects/manifests/files.jsonl` and writes a receipt under `receipts/prehashed-objet-ledger/` without reading blob bytes, copying objects, uploading, drafting, minting, or cleaning. MCP exposes only the read-only preview as `prehashed_objet_ledger_preview`. `objet-capture` still verifies bytes itself from staged files; this is a separate manifest-registration path for externally verified stores.

For Notion page/block exports, `recordMap` or `blocks` JSON is treated as a provider page snapshot source objet. Extracted readable block text is a derived text record, and a human conclusion is a later draft or minted zet. See `docs/notion-page-snapshot-model.md`. In prehashed ledgers, `object_id` identifies the bytes, `store_kind` names the storage family, and `store_ref` is only a reviewed safe external-store label. It is not a raw path, URL, token, or proof of byte availability.

`archive resolve-objet-ref --object-id sha256:<hex> --dry-run` resolves one object manifest reference for reading UX. It returns existing local candidates as archive-relative paths and external candidates as safe provider/store labels. It writes nothing, echoes no absolute local paths or provider URLs, reads no object bytes, re-hashes no object bytes, calls no providers, creates no presigned URLs, downloads nothing, uploads nothing, and does not decide whether local originals can be deleted. MCP exposes the same read-only flow as `resolve_objet_ref`.

`archive zettel-objet-links --path <zet.md>|--zettel-id <id> --dry-run` scans one non-redacted zettel for stable `sha256:<hex>` and `objet:sha256:<hex>` refs and resolves them into safe local/external manifest candidates. It writes nothing, echoes no body text, frontmatter values, absolute local paths, provider URLs, or object bytes, calls no providers, creates no presigned URLs, and blocks redacted zettels. MCP exposes the same read-only flow as `zettel_objet_links`.

`archive notion-objet-link-plan --path <zet.md>|--zettel-id <id> --dry-run` scans one non-redacted zettel for Notion provider locator fingerprints and matches them against reviewed metadata in `objects/manifests/files.jsonl`. It is the bridge for imported Notion zets that still contain provider locators instead of stable `objet:sha256:<hex>` refs. It writes nothing, rewrites no body text, echoes no provider URLs, page titles, zettel body text, frontmatter values, absolute local paths, account ids, emails, tokens, or secret values, reads no object bytes, calls no providers, creates no presigned URLs, and blocks redacted zettels. MCP exposes the same read-only flow as `notion_objet_link_plan`.

`archive notion-objet-link-index <archive-root> --dry-run` scans non-redacted zettels across the archive for Notion provider locator fingerprints and reports safe counts for locator rows with or without manifested objet candidates. `archive notion-objet-link-rewrite-plan --path <zet.md>|--zettel-id <id> --locator-fingerprint sha256:<hex> --object-id sha256:<hex> --dry-run` validates one reviewed locator/object pair, target mode, and optional occurrence-count drift guard. They write nothing, rewrite no body text, write no edges, echo no provider URLs, page titles, zettel body text, frontmatter values, absolute local paths, account ids, emails, tokens, or secret values, read no object bytes, call no providers, and create no presigned URLs. MCP exposes the same read-only flows as `notion_objet_link_index` and `notion_objet_link_rewrite_plan`. `archive notion-objet-manifest-locator-label --object-id sha256:<hex> --locator-fingerprint sha256:<hex> --dry-run|--approve` is the separate CLI-only write path for adding a reviewed non-secret locator fingerprint to one manifest record, so later index/plan runs can match without storing provider locator text. `archive notion-objet-link-convert --path <zet.md>|--zettel-id <id> --locator-fingerprint sha256:<hex> --object-id sha256:<hex> --target-mode embed_edge --expected-occurrence-count <n> --dry-run|--approve` is the CLI-only approved conversion path for one reviewed `embed` edge. It re-runs the rewrite plan, uses the existing `zettel-edge` gate, writes edge and conversion receipts on approval, and still keeps body replacement future work.

`archive view-health --dry-run` diagnoses saved view drift against the generated local SQLite index. It reports active, empty, and blocked saved views, per-filter facet match counts, and observed facet value samples for the keys used by saved views. It writes nothing, rebuilds no index, rewrites no `views/*.yml` files or zettel facets, reads no zettel bodies or object bytes, echoes no zettel titles, absolute local paths, provider URLs, account ids, emails, tokens, or secret values, and calls no providers. MCP exposes the same read-only flow as `view_health`.

`archive index-health --dry-run` checks whether `db/archive-index.sqlite` matches live zettel paths and basic frontmatter metadata before index-backed navigation. It reports missing live zets, extra indexed paths, changed `id`/`status`/`kind`, and zettel files modified after the index. It writes nothing, rebuilds no index, edits no zettels, reads no object bytes, echoes no zettel body text, zettel titles, absolute local paths, provider URLs, account ids, emails, tokens, or secret values, and calls no providers. MCP exposes the same read-only flow as `index_health`.

`archive objet-capture-selection --staged-path <archive-relative-file> --source-intake-receipt <receipt> --dry-run` bridges a recorded source-intake plan to B4 local objet capture. It hashes one staged file to produce `approved_object_id`, validates the source-intake receipt, and previews a selection manifest. `--approve --reviewed-by <actor>` writes only `receipts/objet-capture-selections/*.selection.json`; it does not run `objet-capture`, copy object bytes, append `objects/manifests/files.jsonl`, draft, mint, upload, or clean.

`archive create-draft --source-intake-plan <json-file>` consumes a successful source-intake dry-run JSON file, validates that it is metadata-only and blocker-free, then merges safe `source_refs_for_draft` into draft `source_refs`. If the source-intake plan carries a valid `project_intake_context`, the draft `source_intake.project_intake_context` preserves that receipt evidence through mint preview/receipts without copying decision answer values. The plan file path is not stored in frontmatter, and WOM-kit does not follow local paths inside the plan.

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

Record an approved local candidate after reviewing a saved candidate plan:

```powershell
python wom-kit\cli\archive.py record-attestation-review-candidate wom-kit\examples\fake-life-archive `
  --candidate-plan workbench\foreign-block-attestation-review-candidate.json `
  --approve `
  --reviewed-by person:me `
  --format json
```

Review recorded attestation review candidates:

```powershell
python wom-kit\cli\archive.py attestation-candidate-review wom-kit\examples\fake-life-archive `
  --format json
```

Use `--case-id <safe-id>` for one case, `--review-scope <scope-or-all>` for a displayed candidate filter, and `--include-receipts` when the reviewer needs sanitized candidate receipt summaries. The index still validates every discovered candidate before setting top-level `ok`, writes nothing, and keeps every foreign block untrusted.

Preview a non-binding statement draft for one recorded candidate:

```powershell
python wom-kit\cli\archive.py attestation-statement-draft wom-kit\examples\fake-life-archive `
  --case-id case-review-001 `
  --dry-run `
  --statement-style human_readable `
  --format json
```

The statement draft re-reads the current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt. It is not an attestation, not trust, not signing, not import, not minting, not a receipt write, and not ZET transport.

Record an approved local statement draft after reviewing a saved draft preview:

```powershell
python wom-kit\cli\archive.py record-attestation-statement-draft wom-kit\examples\fake-life-archive `
  --draft-preview workbench\foreign-block-attestation-statement-draft.json `
  --approve `
  --reviewed-by person:me `
  --format json
```

This records only an untrusted statement draft JSON and matching receipt. It still does not create trust, import, attestation, signature, mint, sharing, provider calls, or ZET transport.

Review recorded untrusted statement drafts and their receipts:

```powershell
python wom-kit\cli\archive.py attestation-statement-draft-review wom-kit\examples\fake-life-archive `
  --statement-style all `
  --review-scope all `
  --include-receipts `
  --format json
```

Use `--case-id <safe-id>` for one case, `--statement-style minimal|review_checklist|human_readable|all` for displayed draft style filtering, `--review-scope identity|source_refs|header_hashes|prompt_boundary|full_human_review|all` for displayed review-scope filtering, and `--include-receipts` when the reviewer needs sanitized receipt summaries. Style and scope filters never hide blockers from other discovered statement draft records. `--case-id` intentionally scopes the consistency verdict to that one case.

The review index writes nothing, returns `index_status: indexed_not_modified`, keeps `trust_state: untrusted_foreign`, and leaves `attestation_status` and `signature_status` as `not_created`. It still does not create trust, import, attestation, signature, mint, acceptance, sharing, provider calls, or ZET transport.

Preview a non-binding next review route for one recorded statement draft:

```powershell
python wom-kit\cli\archive.py attestation-statement-draft-decision wom-kit\examples\fake-life-archive `
  --case-id case-review-001 `
  --dry-run `
  --decision-intent needs_more_review `
  --format json
```

The default decision intent is `needs_more_review`. Supported route intents are `keep_under_review`, `revise_statement_draft`, `reject_statement_draft`, `prepare_future_attestation_statement_review`, and `needs_more_review`.

The preview revalidates the current statement draft review index, statement draft record/receipt, candidate record/receipt, quarantine case/receipt, and decision record/receipt. It returns `decision_status: preview_not_recorded`, keeps the foreign block `untrusted_foreign`, and leaves `attestation_status` and `signature_status` as `not_created`. It never records a decision, accepts a statement draft, creates trust, imports, attests, signs, mints, publishes to WordPress, calls providers, writes receipts, or runs ZET transport.

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

`archive import-external --source notion --export <folder> --dry-run` previews a Notion Markdown export import. `archive import-external --source google_drive --export <manifest.json> --dry-run` does the same for Google Drive exports. Approved imports write inbox drafts and `receipts/import/*.external-import.json`; when manifest metadata includes explicit safe object refs, safe non-object source refs, safe facets, or a safe zettel id override, those values are preserved in the imported draft frontmatter. Imported bodies that still contain provider URLs or local absolute paths block before approval. `--provider-locator-policy object-ref` can convert supported Notion body locators to one reviewed `objet:<object_id>` reference when exactly one object source ref is present. The command does not call Notion or Google Drive APIs, read object bytes, or store OAuth secrets.

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
docs/zet-publication-surface-baseline.md
docs/zet-projection-plan-preview.md
docs/zet-closed-sharing-model-baseline.md
docs/zet-radio-frequency-recommendation-model.md
docs/zet-shared-update-record-baseline.md
docs/zet-shared-update-record-review-preview.md
docs/zet-shared-update-record-review-index.md
docs/zet-transport-threat-model.md
docs/product-roadmap.md
docs/public-release-link-hygiene.md
docs/concepts/korean-product-language-baseline.ko.md
docs/korean-product-language-hygiene.md
docs/public-privacy-hygiene.md
docs/release-readiness-gate.md
docs/main-branch-protection-readiness.md
examples/zet-publication-surface/
examples/zet-closed-sharing/
examples/zet-radio-frequency-recommendation/
examples/zet-shared-update-record/
```

## Next Implementation Plan

Earlier promotion work is tracked in:

```text
plans/phase-3-implementation-plan.md
plans/phase-4-lineage-trust-plan.md
```

Phase 2 is complete for the safe local toolkit subset. Phase 3 added real promotion. v0.2.8 added the product-facing minting lifecycle with canonical zettel, mint receipt, and draft snapshot outputs. v0.2.9 stabilizes minting terminology while preserving promotion compatibility. v0.2.10 adds dry-run `delegate-zet`, `attest-zet`, and `anchor-zet` lifecycle previews. v0.2.11 adds the delegate capability contract with `counterparty_bound` and `claimable_once` dry-run policies. v0.2.12 adds CLI-only real delegate receipt writes. v0.2.13 adds the WOM naming baseline and compatibility-safe aliases: `mint-zet`, `parcel`, and `admit`. v0.2.14 records the `WOM`/`zet`/`ZET` distinction and defines the WOM Safe HTML Profile as a compatibility-safe documentation baseline. v0.2.15 adds `archive check-safe-html --dry-run` as a read-only CLI validator that previews WOM Safe HTML Profile compatibility for v0.2 Markdown-compatible zets. v0.2.16 adds the read-only WOM AI Runtime Context Layer so terminal-capable AI runtimes can confirm archive identity, type, paths, write policy, and safe actions before drafting or mint approval. v0.2.17 adds the read-only WOM Profile Registry dry-run layer so AI runtimes resolve the requested target profile before assuming the default archive. v0.2.18 adds profile-aware `create-draft --dry-run` and replay-safe inbox draft creation for AI runtimes. v0.2.19 renames the implementation/tooling layer to WOM-kit with `wom-kit/` and `wom_kit`. v0.2.20 adds a dry-run-first GitHub repository setup planner for WOM profiles with local-only approval metadata. v0.2.21 adds a dry-run-first object storage / objet setup planner for WOM profiles with local-only approval metadata. v0.2.22 adds dry-run-only source intake planning before draft creation. v0.2.23 lets `create-draft` consume validated source-intake dry-run plans without re-reading source files. v0.2.24 adds read-only block header previews for `block = zet + header`. v0.2.25 adds the WOM profile wallet concept baseline and read-only `profile-wallet` previews. v0.2.26 adds prompt injection boundary, responsible use, and runtime model guidance plus read-only `prompt-boundary` checks. v0.2.27 lets `create-draft` consume validated prompt-boundary reports and preserve the untrusted-text boundary in draft metadata and mint receipts. v0.2.28 adds read-only foreign block intake previews before any trust/import action. v0.2.29 adds read-only foreign block trust / attestation previews from intake reports. v0.2.30 adds read-only foreign block attestation packet previews for future human review without creating trust or receipts. v0.2.31 adds read-only foreign block quarantine plans for future isolated holding without writing quarantine files. v0.2.32 adds CLI-only approved foreign block quarantine case and receipt writes while keeping the foreign block untrusted and unimported. v0.2.33 adds a read-only foreign block quarantine review index for existing untrusted cases and receipt consistency checks. v0.2.34 adds read-only foreign block quarantine decision previews for candidate future decision paths without recording a decision. v0.2.35 adds CLI-only approved quarantine decision records and receipts while keeping the foreign block untrusted and unimported. v0.2.36 adds a read-only quarantine decision review index for recorded decisions. v0.2.37 adds a read-only decision outcome planner for one recorded decision without applying trust, import, acceptance, or attestation. v0.2.38 adds a read-only attestation review candidate planner for eligible recorded decisions. v0.2.39 adds CLI-only approved attestation review candidate records while keeping the foreign block untrusted and without creating attestations or signatures. v0.2.40 adds a read-only attestation review candidate index for recorded untrusted candidates. v0.2.41 adds a read-only non-binding attestation statement draft preview for one recorded candidate. v0.2.42 adds CLI-only approved attestation statement draft records while keeping the foreign block untrusted and without creating attestations or signatures. v0.2.43 adds a read-only attestation statement draft review index for recorded untrusted statement drafts. v0.2.44 adds a read-only attestation statement draft decision preview without recording acceptance or creating trust. v0.2.45 adds the ZET publication surface baseline. v0.2.46 adds dry-run ZET projection plan previews. v0.2.47 adds the ZET closed sharing model baseline. v0.2.48 adds the ZET radio-frequency recommendation model baseline. v0.2.49 adds public release link hygiene checks. v0.2.50 adds the Korean product-language baseline. v0.2.51 adds a local Korean product-language hygiene checker. v0.2.52 adds a local public privacy hygiene checker. v0.2.53 adds a local release-readiness gate. v0.2.54 documents main branch protection readiness. v0.2.55 adds the ZET shared update record baseline. v0.2.56 adds a read-only shared update record review preview. v0.2.57 adds the public capability matrix and README readability cleanup. v0.2.58 adds a read-only shared update record review index. Phase 4 adds the lineage/trust dry-run baseline and the first owner/operator identity model. Phase 7B adds CLI-only real ownership transfer plus provider change planning. Phase 8B adds one-command setup orchestration above the Docker-first runtime. Phase 8C hardens the local installer and container runtime. Phase 9 starts Notion and Google Drive export import. v0.3.88 adds overview-first zet reading, block-header first-read cards, stale link type migration, safe Notion external-ref resolution for single-edge writes, and provider URL mint guards. v0.3.89 adds a read-only Notion provider locator to manifested objet link planner, but real parcel/workpack import, real share/merge/fork, live external provider API sync, OS keyring integration, UI, Markdown-to-WOM-Safe-HTML conversion, profile registration, token storage, wallet creation, real signing, source content import, foreign block import/trust/apply, real foreign attestation writes, signed attestation statements, quarantine review apply/accept, quarantine decision accept/apply/trust, decision outcome apply/accept, attestation review candidate accept/apply/trust, attestation statement draft decision write/accept/apply/trust, shared update review writes, receiver-side renewal writes, projection-plan apply/write behavior, projection receipts, provider-specific publishing, recommendation fetching/ranking/feed updates, automatic neighbor feed updates, GitHub Release editing from tools, external URL network fetching from link checks, GitHub Actions, branch protection, user-level sharing pipeline, live object storage upload/sync, approval-gated Notion locator rewrite, source intake apply/capture, complete prompt-injection prevention, full-auto execution, ZET transport, token mechanics, and CI matrix remain future work.

v0.2.38 adds a read-only attestation review candidate planner for eligible recorded decisions. It prepares human-review metadata only and does not create trust, signatures, attestations, imports, minting, sharing, provider calls, or ZET transport.

v0.3.90 adds read-only saved view health diagnostics for stale or empty
`views/*.yml` filters. Approval-gated view filter rewrite remains future work.

v0.3.96 adds a read-only archive-wide Notion objet link index for provider
locator fingerprints. v0.3.97 adds read-only saved view recommendations from
indexed navigation facets. v0.3.98 adds a read-only Notion objet link rewrite
plan that validates one reviewed locator/object pair before approved
conversion. v0.3.99 adds approval-gated policy batch zettel
edge writes through `zettel-edge-batch`, while keeping real export parsing and
MCP write tools closed. v0.3.100 adds approval-gated Notion objet manifest
locator fingerprint labels so index/plan matching can recover when manifests
know the Notion source but lack the reviewed locator fingerprint.
v0.3.101 adds approval-gated Notion objet link conversion for reviewed
`embed` edges, while keeping body replacement, provider calls, and MCP write
tools closed.
v0.3.102 adds the read-only operational terminology translation layer,
archive-relative batch plan resolution, explicit `--skip-existing` batch
reruns, and a sanitized version-chain `supersedes` recommendation while
keeping source bodies, provider calls, LLM classification, and MCP write tools
closed.
v0.3.103 adds read-only Notion source-map material-link planning for imported
zets whose body provider locators were already omitted, while keeping provider
calls, zettel body reads, object byte reads, edge writes, receipt writes, and
private value echoes closed.
v0.3.104 adds a read-only Notion import material-clue audit that checks whether
omitted-locator imports preserved an object ref, have a source-map candidate,
or need future import-time preservation repair, while keeping reads and writes
body-safe.
v0.3.105 preserves explicit safe manifest object refs into approved external
import draft `source_refs`, while keeping dry-run object id values hidden in
counts and avoiding provider calls, object byte reads, uploads, and edge writes.
v0.3.106 adds machine-readable `runtime-context` guide handoff fields so AI
runtimes can discover `AGENTS.md`, `ai-response-concept-guide`, and read-only
Notion material-link routes before choosing tools.
v0.3.107 fixes large-manifest startup hangs in source-map material planning and
import clue auditing by reusing a preloaded manifest index instead of resolving
each manifest object through repeated full manifest scans.
v0.3.108 extends that large-manifest fix to `zettel-edge-batch` objet target
resolution and adds receipt-based `revert-edge` / `revert-batch` rollback
commands for approved edge writes while preserving original receipts.
v0.3.109 adds receipt-backed `archive migrate --target link-types-v0.3
--revert` for safe link-type migration rollback when the migration receipt says
which edge types were added and those types remain unused and unchanged from the
base template, while blocking `frontmatter-v0.3 --revert` until future snapshot
receipts can make that rollback lossless.
v0.3.110 adds verified `archive retire-draft --dry-run|--approve` cleanup for
already minted inbox drafts, lets validate/doctor treat still-present minted
draft twins as informational cleanup candidates, accepts retired mint sources
through retired-draft receipts, makes short CJK titles pass the title checklist
when they are not generic placeholders, and suppresses title-only duplicate
warnings when bodies are materially different.
v0.3.111 fixes LaTeX escape false positives in forbidden-location checks and
extends `archive import-external` for high-fidelity structured manifests: safe
zettel id overrides, facets, source refs, and an explicit Notion locator to
`objet:` conversion option are supported while provider URLs in imported bodies
remain blocked by default.
v0.3.112 fixes receipt SHA validation after approved edge-only canonical zet
growth, preserves mint snapshot bytes, lets legacy LF/CRLF-only source/snapshot
pairs retire with a warning, and preloads one zettel id/path index for
zet-to-zet `zettel-edge-batch` plans.
v0.3.113 adds account recovery and break-glass credential-store scenarios for
2FA recovery codes and emergency-only secrets, requiring independent offline
redundancy, a two-location minimum, and circular-dependency review while WOM
still records only refs and metadata.
v0.3.114 makes mint duplicate checks use the current generated index when
available, upserts newly minted canonical rows back into that index during
approved mint loops, and lets `retire-draft` accept mint target SHA history that
changed only through approved post-receipt zettel-edge writes.
v0.3.115 adds the public product roadmap that makes the pre-1.0 line meanings
explicit: `v0.1.x` idea/protocol language, `v0.2.x` local implementation,
current `v0.3.x` WOM real-use feedback and safety hardening, planned `v0.4.x`
custom UI control layer, and planned `v0.5.x` ZET real-use feedback. It is
documentation-only and adds no UI, provider adapter, ZET transport, wallet,
token, sync, or worker behavior.
v0.3.116 closes the remaining mint source-resolution scale gap after v0.3.114:
standard `inbox/<zettel_id>.md` and `zettels/<zettel_id>.md` paths are checked
directly, with matching frontmatter id verification, before the legacy
archive-wide id scan fallback. Generated-index-backed `mint-zet --zettel-id`
dry-run and approve flows no longer reparse every zettel just to find the
standard inbox draft path.
v0.3.117 adds AI operational context rehydration: `runtime-context` now exposes
the bounded `operational_context` record from `ops/operational-context.yml`, and
CLI `archive operational-context` can dry-run read or approval-write reviewed
mission, scope, state, gotchas, decisions, and next actions with a receipt. It
does not replace zets or receipts, scan broad archive bodies, call providers, or
add MCP write tools.
v0.3.118 closes the remaining mint staleness scale gap for current-format
generated indexes: `archive index` writes `index_metadata`, and generated-index
backed `mint-zet` uses that metadata instead of glob/stat checking every
canonical zettel before each mint. Approved mint upserts keep the metadata
current during large batches; older indexes without metadata still fall back to
the legacy live staleness scan. The same release opens generated-index SQLite
connections with a 30s busy timeout, uses WAL mode on index write paths, and
keeps WAL/SHM/journal sidecars in the generated-artifact ignore/hygiene layer.
v0.3.119 adds `mint-zet-batch` / `bulk-mint` and `retire-draft-batch` /
`bulk-retire` so large mint and retired-draft cleanup runs can use one reviewed
plan, one WOM-kit process, `--skip-existing`, `--max-items`, per-item failure
lists, and one batch receipt instead of fragile per-item shell loops.
v0.3.120 hardens the next batch performance layer: edge-only canonical target
SHA evolution checks now reuse a source-zettel-path edge receipt index in
`retire-draft-batch`, and `validate` / `doctor` use a lazy edge receipt cache
instead of rescanning edge receipts for every mint or retired-draft receipt.
v0.3.121 adds scoped validation for the next large-archive feedback loop:
`archive validate --since <batch-id-or-receipt>` validates the zettels and
receipts touched by a mint, retired-draft, or zettel-edge batch receipt, while
`archive validate --scope <facet=value>` uses a current generated index to
validate only matching indexed zettels. Generated index rows now carry
`body_sha256`, `approved_body_sha256`, file size/mtime, and a forbidden-location
flag so scoped validation can reuse unchanged body evidence. `--progress`
streams stage/item counts, elapsed time, and ETA to stderr. Scoped validation is
an incremental safety gate, not a permanent replacement for periodic full
`archive validate`.
v0.3.122 adds the first AI usage observability layer. `archive ai-usage-plan
--dry-run` estimates explicit archive-relative context files against a token
budget without echoing file contents. `archive ai-usage-record
--dry-run|--approve` records reviewed non-secret runtime token counters under
`receipts/ai-usage/`. `archive ai-usage-report --dry-run` aggregates those
receipts by runtime, model, and purpose. This does not call LLM providers,
retrieve live provider billing, store prompts, store responses, or enforce hard
runtime budgets yet; it gives WOM a local token-accounting ledger baseline.
v0.3.123 adds a dedicated containment edge vocabulary checkpoint. The base and
fake archive `types.yml` files now include `contains` for structural child
page, child database, collection view, or nested archive containment.
`connection-import-plan`, the parser contract, the sanitized fixture parser,
and connection edge intelligence now understand `notion_containment` evidence
and map it to `contains` instead of forcing it into `view_query`, `references`,
`material`, or `inherited_by`. `ai-response-concept-guide` also explains this
as a model-gap escalation rule: if no active edge type fits, pause for a
developer decision before writing durable edges.
v0.3.124 adds a read-only Notion nested tree recovery checkpoint.
`archive notion-nested-tree-plan --dry-run` reads only a sanitized tree fixture,
walks parent refs to assign leaf pages to known generation roots, separates live
content leaves from structure/template/view containers, and reports
untraceable leaves instead of guessing from a partial mirror. It does not read
real exports, page titles, page bodies, call providers, mint zets, or write
edges.
v0.3.125 adds read-only Notion ancestor crawl request planning.
`archive notion-ancestor-crawl-plan --dry-run` groups missing ancestors from the
nested-tree hold queue into a `crawl_request_queue` for a future
credential-bounded adapter. The nested-tree planner also derives `content_class`
from `node_kind` when needed, blocks oversized fixtures instead of returning
partial success, allows shared logical `generation_id` values across unique
roots, and warns on likely ref-format mismatches. It still does not call
providers, read real exports, read page titles or bodies, merge fixtures, mint
zets, write edges, or write receipts.
v0.3.126 adds the local fixture and merge half of that loop.
`archive notion-block-mirror-tree-fixture-plan --dry-run` builds a sanitized
nested tree fixture preview from reviewed block mirror metadata and immediately
runs a nested-tree plan preview. `archive notion-ancestor-merge-plan --dry-run`
merges sanitized ancestor result nodes into a tree preview and replans in
memory. Both commands remain read-only and call no providers, read no titles or
bodies, write no fixture files, mint no zets, write no edges, and write no
receipts.
v0.3.127 adds a read-only client issue verification bundle for this loop.
`archive notion-client-issue-verification-plan --dry-run` combines a sanitized
tree fixture, optional reviewed block mirror fixture, generated ancestor crawl
request queue, and optional sanitized ancestor result fixture into one verdict:
the issue is reproduced and needs ancestor evidence, closed by sanitized
ancestor merge, still needs more ancestor evidence, or not present in the
sanitized input. It still calls no providers, reads no titles or bodies, writes
no fixture files, mints no zets, writes no edges, and writes no receipts.
v0.3.128 adds a read-only sanitized fixture request package for client follow-up.
`archive notion-client-fixture-request-plan --dry-run` says which minimal
sanitized fixture should be requested next, lists accepted fixture kinds and
safe fields, includes a redaction checklist, and can reuse the v0.3.127
verification preview when local fixtures are already present. It still sends no
message, calls no providers, reads no titles or bodies, writes no fixture files,
mints no zets, writes no edges, and writes no receipts.
v0.3.129 adds request-queue scope filters to the Notion ancestor crawl plan.
`archive notion-ancestor-crawl-plan --scope-generation-id DB1 --dry-run` can
narrow a broad workspace crawl queue by generation id, root ref, ancestor ref,
or affected leaf ref before any future credential-bounded adapter receives it.
It still calls no providers, starts no OAuth, reads no titles or bodies, writes
no fixture files, mints no zets, writes no edges, and writes no receipts.
v0.3.130 adds the read-only Notion ancestor fetch adapter execution contract.
`archive notion-ancestor-fetch-adapter-execution-contract --dry-run` fixes the
future adapter's scoped input queue contract, sanitized ancestor-result fixture
output contract, credential approval boundary, and next merge/replan command. It
still calls no providers, retrieves no secrets, starts no OAuth, reads no titles
or bodies, writes no fixture files, mints no zets, writes no edges, and writes
no receipts.
v0.3.131 clarifies that contract's live fetch execution subject. The intended
future executor is a WOM local credential-bounded adapter process after human
scope review and credential approval, not the AI chat runtime. Client-supplied
ancestor fixtures remain accepted as sanitized safe-origin fallback input, but
the contract does not require clients or client-side AI to hand-roll provider
crawling.
v0.3.132 adds the read-only Notion media byte fetch adapter contract and media
result verification plan. `archive notion-media-fetch-adapter-execution-contract
--dry-run` scopes candidate nested content leaf pages and defines the future
sanitized `notion_media_result_fixture`; `archive
notion-media-result-verification-plan --dry-run` checks that sanitized fixture
against `objects/manifests/files.jsonl`. Both still call no providers, refresh
no signed URLs, download no media bytes, hash no bytes, update no manifests, and
write no receipts.
v0.3.133 clarifies the last read-only contract edge before live execution:
future Notion ancestor fetch adapters must recursively crawl parent chains from
each crawl request seed until a stop condition, and generation-unknown
untraceable leaf recovery should be scoped by leaf/root/ancestor refs rather
than generation id. It still calls no providers, retrieves no secrets, starts no
OAuth, reads no titles or bodies, writes no fixture files, mints no zets, writes
no edges, and writes no receipts.
v0.3.134 adds the first approval-gated local Notion ancestor structure fetch adapter.
`archive notion-ancestor-fetch-adapter-run --dry-run|--approve`
verifies a credential access approval receipt, supports `env:` token refs in
the local CLI process, fetches only parent-chain structure metadata from Notion,
and writes a sanitized `notion_ancestor_result_fixture` plus a non-secret
execution receipt. It still does not read page titles, page bodies, comments,
media bytes, file URLs, or raw provider responses, and it does not mint zets,
write edges, or expose a live MCP provider-call tool.
v0.3.135 adds a read-only beginner guide for that human-operated recovery step:
`archive beginner-setup-manual --topic notion_nested_recovery --dry-run`
translates the low-level ancestor/fetch/fixture/merge vocabulary into
folder/shelf/location language, explains why the human approves the local
Notion run, and shows the scoped review -> one-time approval -> live structure
fetch preview/run -> merge-plan handoff chain without reading secrets, calling
providers, writing approval receipts, running the fetch, or echoing exact env
var names.
v0.3.136 adds the beginner-facing wrapper for the same recovery path:
`archive notion-recover`.
It auto-selects the reviewed missing-location queue, asks for local
confirmation, accepts the token only through a hidden local terminal prompt or
an already available local process value, writes the one-time approval receipt
internally, runs the approved location fetch, writes the sanitized ancestor
result fixture, and returns the AI handoff sentence for tidying and merging.
It still does not read page titles, page bodies, comments, media bytes, signed
file URLs, raw provider responses, or expose exact credential refs, env var
names, approval receipt paths, tokens, provider URLs, account ids, or emails.
v0.3.138 adds a CLI-only `file:<path>` fallback to that wrapper for users who
already have the Notion token in a local text file. The wrapper extracts the
token locally, passes it through the same approval-gated adapter chain, and
does not echo the token file path, file name, token value, transient env ref, or
receipt path. Vault/keyring one-click handoff remains the right long-term
credential-broker direction, but live vault/keyring reads are still closed until
a dedicated local adapter exists.
v0.3.139 adds Tiro lossless recovery planning plus approval-gated raw recovery
bundle capture. `archive tiro-lossless-recovery-plan --dry-run` records the
official Tiro data surfaces and bundle contract, while
`archive tiro-lossless-recovery-capture --dry-run|--approve` preserves a
reviewed raw Tiro recovery JSON bundle as a content-addressed WOM objet with a
non-secret receipt. It also adds `archive zet-markdown-style-guide --dry-run`
and wires the `A ~ B` range-tilde rule into `ai-response-concept-guide`. The
live credential-bounded Tiro fetch adapter lands in v0.3.140.
v0.3.140 adds `archive tiro-lossless-recovery-fetch-run --dry-run|--approve`.
The command reads an approved local `env:` Tiro credential only on approve,
calls the official Tiro REST API, writes the private raw bundle under
`workbench/`, and records a non-secret fetch receipt under
`receipts/tiro/lossless-fetches/`. Command output and receipts do not echo the
credential ref, environment variable name, token, meeting titles, transcript
text, participant names, provider URLs, or raw provider responses. At the
v0.3.140 checkpoint, keyring/vault credential reads, original audio byte
retrieval where no official endpoint is confirmed, AI enrichment writes,
derived text, zet drafting, and minting remained separate future layers.
v0.3.143 extends that same Tiro fetch path to approved Windows Credential
Manager reads through `keyring:` and `credential-manager:` refs. Dry-run still
opens no credential store. Approved mode may read exactly one matching Windows
generic credential from a safe label, including auto-detection when there is one
match, while output and receipts echo no ref, target name, token, provider URL,
account id, or email. macOS Keychain, Linux Secret Service, KeePassXC, wallet,
browser password-manager reads, and non-Tiro provider secret reads remain
future layers.
v0.3.141 responds to the beta-tester Notion recovery experience breakdown.
`archive notion-connection-plan --dry-run` records the one-click "Connect
Notion" product contract and separates internal connection tokens, personal
access tokens, and public OAuth connections. `archive notion-recover` and the
underlying Notion ancestor fetch adapter now classify provider failures into
safe action categories such as invalid token, permission/page-share gap, missing
or unshared object, rate limit, network/timeout, or temporary provider outage
without echoing raw provider errors. Browser OAuth, managed local callback
storage, keyring/vault reads, page picker authorization, and UI buttons remain
future layers; env/file token handoff stays a power-user fallback.
v0.3.142 adds `archive notion-oauth-connection-preflight --dry-run`, a
secret-blind local OAuth runtime contract check before any future browser,
callback, authorization-code exchange, token storage, or provider call. The
preflight validates safe refs, local loopback callback shape, and keyring,
secret, or wallet token-store intent while rejecting plain env token storage.
It writes nothing and echoes no refs, redirect URI, tokens, provider URLs,
account ids, or emails.

v0.2.41 adds a read-only attestation statement draft preview after v0.2.40 candidate indexing. The draft is non-binding, labels hash commitments as not proof of authenticity, writes nothing, and still does not create trust, signatures, attestations, imports, minting, receipts, sharing, provider calls, or ZET transport.

v0.2.42 adds CLI-only approved attestation statement draft records after v0.2.41 preview. The record and receipt preserve the untrusted state and still do not create trust, signatures, attestations, imports, minting, sharing, provider calls, or ZET transport.

v0.2.43 adds a read-only attestation statement draft review index after v0.2.42 record writes. The index validates statement draft records, receipts, and upstream quarantine/candidate/decision chain consistency without writing files or changing trust state.

v0.2.44 adds a read-only attestation statement draft decision preview after v0.2.43 indexing. The preview proposes one safe next human-review route but records no decision, accepts no draft, and still creates no trust, signatures, attestations, imports, minting, publishing, provider calls, or ZET transport.

v0.2.45 adds a documentation-only ZET publication surface baseline. It explains that WOM can stay no-UI at the core while users choose projection surfaces such as WordPress later. Posting is not minting, a surface locator is not canonical zet identity, and no provider call or projection write is implemented.

v0.2.46 adds read-only ZET projection plan previews. The preview considers one local zet and one declared surface kind, emits metadata only, writes nothing, creates no receipts, calls no providers, publishes nothing, and runs no ZET transport.

v0.2.47 adds the ZET closed sharing model baseline. It clarifies that GitHub, object storage, and DB are base-system substrates, while ZET is the future closed sharing/SNS layer above them. It adds no sharing pipeline, transport, feed update, provider call, or UI.

v0.2.48 adds the ZET radio-frequency recommendation model baseline. It distinguishes followed/neighbor feeds from future recommended/broadcast feeds and requires recommendation selector logic to be user/node-owned, inspectable, configurable, and explainable. It adds no recommendation fetching, ranking, feed update, provider call, transport, or UI.

v0.2.49 adds public release link hygiene checks. The checker validates local Markdown links and release-note file links, but it does not edit GitHub Releases or fetch external URLs.

v0.2.50 adds the Korean product-language baseline. It records approved Korean explanation terms such as `옴`, `쪽글`/`토막글`, `공유 계층`, `발행`, `공유`, `수용`, `반영`, `갱신`, `소포`, `검문소`, `상자`, `초록`, `수제 앱`, `수제 알고리즘`, `젯 갱신하기`, `쿠키 굽기`, and `스레드`, while keeping implementation identifiers in English.

v0.2.51 adds a local Korean product-language hygiene checker. The checker reads public Markdown files known to Git, validates the baseline anchors, and flags a small set of high-risk public wording regressions without rewriting files or fetching external URLs.

v0.2.52 adds a local public privacy hygiene checker. The checker reads public text files known to Git and flags obvious local path, token-like, private key header, seed-phrase-like, and private endpoint leaks without rewriting files, fetching external URLs, inspecting private archives, calling providers, or adding product behavior.

v0.2.53 adds a local release-readiness gate. The gate runs the public link, Korean product-language, and public privacy hygiene checkers together, prints a compact summary, and still does not add CI, branch protection, GitHub API calls, product doctors/tests, or product behavior.

v0.2.54 adds the main branch protection readiness baseline. It documents what GitHub's `main` branch warning means and recommends a staged path from the local release gate to future CI, status checks, and branch protection without enabling any repository settings yet.

v0.2.55 adds the ZET shared update record baseline. It documents a future receiver-side review artifact for shared zet updates and includes a sanitized non-executable example without adding transport, feed, trust, import, attestation, signature, provider, projection, or CLI/MCP behavior.

v0.2.56 adds read-only `shared-update-record-review` previews. The preview reads one archive-contained shared update record JSON, blocks unsafe paths, body-included records, private location/secret-like values, and true mutation flags, and writes nothing before any receiver-side renewal.

v0.2.57 adds the public capability matrix and README readability cleanup. It is documentation, metadata, and test coverage only; it adds no product CLI, MCP, service, provider, transport, trust, import, attestation, signature, anchor, or full-auto behavior.

v0.2.58 adds read-only `shared-update-record-review-index` previews. The index scans only direct-child local JSON records under an archive-relative directory, reuses the single-record review policy, writes nothing, echoes no body text or local absolute paths, and performs no feed, trust, import, attestation, signature, anchor, provider, projection, receipt, or ZET transport action.

v0.2.59 adds read-only `zet-transport-plan` previews. The planner reads one local shared update record through the existing review policy and returns method-specific future risk/control notes for `key-sharing`, `radio-frequency`, or `mirroring`; it creates no keys, sends nothing, writes no receipts, calls no providers, starts no workers, and runs no ZET transport.

v0.2.60 closes v0.2.x as a conservative local-first checkpoint and records the proposed v0.3.0 entry boundary. It is documentation, version, and test coverage only: no product CLI command, MCP tool, archive service behavior, or schema changes are added.

v0.3.0 opens that first boundary narrowly. `shared-update-attestation-review` is CLI-only, requires `--approve --reviewed-by`, reuses the shared update review preview policy, writes one local review record and one receipt, refuses replay/overwrite, and still does not create real trust, import, acceptance, signature, anchor, feed update, provider sync, projection, or ZET transport.

v0.3.1 adds read-only `shared-update-route-preview`. The router reads one local shared update record through the existing review policy and returns a candidate route pointer, `delegate`, `attest`, `anchor`, or `none`. It writes nothing, does not authorize the route, does not duplicate lifecycle previews, and still does not create real trust, import, acceptance, signature, anchor, feed update, provider sync, projection, receipt, or ZET transport.

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
human_artifact_store_plan
credential_keepassxc_command_plan
zet_surface_prototype_plan
project_intake_plan
project_intake_session_guide
project_intake_status
source_intake_plan
block_header_check
zet_projection_plan_check
zet_shared_update_record_review_preview
zet_shared_update_record_review_index
zet_transport_would_plan
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
foreign_block_attestation_review_candidate_index
foreign_block_attestation_statement_draft_preview
record_attestation_statement_draft_check
foreign_block_attestation_statement_draft_review_index
foreign_block_attestation_statement_draft_decision_preview
archive_init
list_zettels
zet_catalog
read_zettel
zettel_objet_links
notion_objet_link_plan
view_health
index_health
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

The MCP server is intentionally local and stdio-only. It exposes `wom_profile_list`, `wom_profile_resolve`, `wom_profile_wallet_check`, `archive_runtime_context`, `prompt_boundary_check`, `github_repository_setup_plan`, `object_storage_setup_plan`, `human_artifact_store_plan`, `credential_keepassxc_command_plan`, `zet_surface_prototype_plan`, `project_intake_plan`, `project_intake_session_guide`, `project_intake_status`, `source_intake_plan`, `zet_catalog`, `read_zettel`, `zettel_objet_links`, `notion_objet_link_plan`, `view_health`, `index_health`, `block_header_check`, `zet_projection_plan_check`, `zet_shared_update_record_review_preview`, `zet_shared_update_record_review_index`, `zet_transport_would_plan`, `foreign_block_intake_check`, `foreign_block_trust_check`, `foreign_block_attestation_packet_check`, `foreign_block_quarantine_plan`, `quarantine_foreign_block_check`, `foreign_block_quarantine_review_index`, `foreign_block_quarantine_decision_check`, `record_quarantine_decision_check`, `foreign_block_quarantine_decision_review_index`, `foreign_block_decision_outcome_plan`, `foreign_block_attestation_review_candidate_plan`, `record_attestation_review_candidate_check`, `foreign_block_attestation_review_candidate_index`, `foreign_block_attestation_statement_draft_preview`, `record_attestation_statement_draft_check`, `foreign_block_attestation_statement_draft_review_index`, and `foreign_block_attestation_statement_draft_decision_preview` as read-only, and exposes `mint_zettel_check`, legacy `promotion_check`, `share_check`, `delegate_zet_check`, `attest_zet_check`, `anchor_zet_check`, and `ownership_transfer_check` as dry-run only. `zet_catalog` is frontmatter-only and paged; `read_zettel` supports overview-first sections; `source_intake_plan` can carry a `project_intake_receipt` as session evidence; and `create_draft_zettel` accepts optional `abstract`, can dry-run without writing, can consume structured `source_intake_plan` and `prompt_boundary_report` objects, and normal profile-bound AI writes require draft approval plus expected body hash replay values. It does not expose real profile registration, token registration, wallet registration, key generation, real signing, real minting, block minting, token or coin mechanics, legacy real promotion, real delegate writes, real sharing, real claim registries, real attestation writes, real signed attestation statements, real anchoring writes, real merge, real fork, real ownership transfer, project intake decision writes through MCP, project intake apply/capture/cleanup tools, foreign block apply/import/trust/quarantine writes, quarantine review apply/accept, quarantine decision apply/accept/write through MCP, quarantine decision review apply/accept/write through MCP, decision outcome apply/accept/write through MCP, attestation review candidate approve/apply/write/review-apply through MCP, attestation statement draft write/apply through MCP, attestation statement draft review apply/write/approve through MCP, attestation statement draft decision write/apply/accept through MCP, shared update record review/index apply/write/transport/import/trust/attest/anchor tools, ZET transport apply/write/send/deliver/publish/key/radio-frequency/mirror tools, projection-plan apply/write, projection receipt writes, WordPress publishing, provider publishing, human artifact note writes, ZET surface writes, vault writes, KeePassXC command execution, foreign attestation writes, prompt boundary apply, auto-approve, full-auto, source intake apply/capture/upload/sync, live object storage apply/create/connect/upload/sync tools, or approval-gated Notion locator rewrites, approval-gated view filter rewrites, generated-index auto-rebuilds; AI-created zettels go to `inbox/`. The ownership transfer check includes a provider change plan, but MCP still cannot apply local ownership changes or external provider account changes.

Archive ownership is separate from archive operation. A family, company, or other group can own an archive while named people operate it. For example, parents can operate a child-related archive under a family owner, and a later receipt-backed transfer can move ownership to the child.

## Safety Defaults

- AI writes drafts to `inbox/` by default.
- Canonical zettels live in `zettels/` and require explicit human minting or legacy promotion.
- Zettels reference original files by `object_id`, not provider URLs.
- Object storage providers are replaceable through manifests.
- External provider accounts are described in `provider-bindings.yml` with env/keyring references, not secrets.
- Objet storage setup can be planned locally, and reviewed external upload evidence can be registered against existing manifests, but bucket creation, live upload, sync, copy, hashing, source intake apply/capture, and source import remain outside WOM-kit v0.3.0.
- Profile wallet readiness can be previewed locally, but private key custody, wallet creation, real signing, blockchain integration, and payment/economic layers remain outside WOM-kit v0.3.0.
- Foreign block intake, trust preview, attestation packet preview, quarantine plan, quarantine review index, quarantine decision preview, quarantine decision review index, decision outcome plan, attestation review candidate plan, attestation review candidate index, attestation statement draft preview, attestation statement draft review index, and attestation statement draft decision preview are inspect-only; CLI quarantine write records an isolated untrusted case and receipt, CLI quarantine decision write records only an operator-reviewed local decision and receipt, CLI attestation review candidate write records only an untrusted candidate and receipt, and CLI attestation statement draft write records only an untrusted statement draft and receipt. Foreign block import, trust, drafting, minting, attesting, anchoring, applying, signed attestation statements, quarantine decision acceptance, decision outcome acceptance, attestation review candidate acceptance/apply/trust, attestation statement draft decision write/accept/apply/trust, transport, WordPress publishing, and automatic acceptance remain outside WOM-kit v0.3.0.
- ZET publication surfaces now have a dry-run projection plan preview in v0.2.46 and a read-only user-selected surface prototype preview for WordPress, Joplin, Notion, and Obsidian, but projection-plan apply/write behavior, projection receipt writes, provider-specific publishing, WordPress publishing, note/vault writes, and ZET transport remain future work.
- The ZET closed sharing model is documented in v0.2.47, but shared zet update CLI, neighbor feed CLI, mirror/re-project CLI, real ZET transport, automatic neighbor feed updates, real trust/import/acceptance, and real attestation/signature writes remain future work.
- The ZET radio-frequency recommendation model is documented in v0.2.48, but recommendation fetching, selector execution, ranking, feed updates, provider-backed recommendation services, and automatic neighbor updates remain future work.
- Public release link hygiene checks are local validation only; GitHub Release editing and external URL network fetching remain outside WOM-kit v0.3.0.
- Korean product-language terms and the hygiene checker are public explanation guardrails only; CLI commands, JSON fields, schema fields, filenames, Python identifiers, and package names remain English in WOM-kit v0.3.0.
- Public privacy hygiene checks are local validation only; automatic rewriting, full-disk scanning, private archive inspection, provider calls, GitHub Release editing, and general-purpose secret scanning remain outside WOM-kit v0.3.0.
- Artifact hygiene checks are report-only classification and `.gitignore` validation only; automatic cleanup, prune/gc, orphan-objet sweeping, provider upload/sync, real local objet capture, and default reads of real `-objets` stores remain outside WOM-kit v0.3.0.
- Release readiness gate checks are local validation only; CI, GitHub Actions, branch protection, product doctors/tests, GitHub API calls, and release editing remain outside WOM-kit v0.3.0.
- Main branch protection readiness is documentation only; GitHub Actions, branch protection, repository settings changes, and GitHub API calls remain outside WOM-kit v0.3.0.
- ZET shared update record review/index remains preview-only. CLI `shared-update-attestation-review` can write exactly one local review record and one receipt after approval, but shared-update transport, neighbor feed update, trust/import/acceptance/anchor, real attestation/signature writes, provider sync, WordPress publishing, projection writes/receipts, and MCP write/apply tools remain outside WOM-kit v0.3.0.
- ZET transport planning is dry-run only; real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, queue jobs, workers, delivery receipts, neighbor feed updates, provider calls, trust/import/acceptance, attestation/signature writes, anchor writes, and MCP write/apply/send/deliver tools remain outside WOM-kit v0.3.0.
- Prompt boundary checks and prompt-boundary draft metadata are heuristic guardrails only; complete prompt-injection prevention, LLM classification, provider scanning, OCR/import apply, and full-auto safety guarantees remain outside WOM-kit v0.3.0.
- The v0.3.0 first boundary is implemented only as a CLI local review record and receipt; it must not imply transport, provider sync, trust graph mutation, public proof anchoring, DID/wallet/key custody, blockchain, token, governance, or full-auto behavior.
- The capability matrix is documentation only; it adds no product command, MCP tool, archive service behavior, provider call, transport, trust, import, attestation, signature, anchor, worker, payment, token, or full-auto behavior.
- Ownership transfer can update the archive identity locally, but external provider permissions remain manual until a future explicit integration.
- Provenance and visibility fields are mandatory in shared or derived records.
- Local profiles and secrets are ignored by default.
- Archive sharing requires scope and trust dry-runs before any future real write path.
- `archive doctor` flags common accidental secret files such as `.env`, private keys, credential exports, and secret-like values.
