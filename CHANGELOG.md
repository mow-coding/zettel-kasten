# Changelog

All notable public releases of `zettel-kasten`, `zet`, and `ZET` should be documented here.

This project uses semantic versioning for public compatibility checkpoints.

## Unreleased

## v0.3.95 - 2026-06-17

- Added `mint_checklist_guidance` to read-only `archive mint-zettel --dry-run`
  / `archive mint-zet --dry-run` output.
- The guidance reports missing required checklist ids, checklist items that
  need explicit human review, the preferred `mint.checklist` frontmatter path,
  the legacy accepted `promotion.checklist` path, and a safe boolean-only
  frontmatter example.
- Text output now prints checklist guidance when required mint checklist items
  are missing.
- Updated the beginner quickstart to explain that items such as
  `one_clear_purpose` and `sensitive_content_reviewed` should only be marked
  true after the human reads the draft.
- Kept minting approval rules unchanged: dry-run writes nothing, real minting
  still requires `--approve` and `--reviewed-by`, and machine-enforced safety
  checks still run at mint time.

## v0.3.94 - 2026-06-17

- Improved read-only `archive projection-plan --dry-run` surface guidance.
- CLI help now lists supported projection surface kinds and projection formats
  instead of requiring users to infer them from source code.
- Blocked JSON output now includes `projection_contract` with supported
  surface kinds, surface prototype kinds, visibility values, and projection
  formats, plus safe `surface.requested_surface_kind` and `surface_status`.
- Unsupported surface values no longer prevent a safe zet reference from being
  resolved, so blocked output can still show safe zet metadata instead of
  nulling the whole plan context.
- Invalid `--surface notion` now explains that Notion belongs to the separate
  `zet-surface-prototype --surface-kind notion` preview rather than the
  projection-plan surface set.
- Kept the command read-only: it renders no body output, writes no projection
  records or receipts, calls no providers, publishes nothing, runs no ZET
  transport, and echoes no unsafe raw surface URLs, local paths, credentials, or
  secret values.

## v0.3.93 - 2026-06-17

- Extended read-only `archive view-health <archive-root> --dry-run` and MCP
  `view_health` with `facet_role_summary` and `facet_roles`.
- The new output uses static key heuristics to separate likely navigation axes
  such as `subject`, `institution`, `record_type`, and `source_category` from
  internal/import metadata such as `notion_status`, `migration_batch`, and
  `contents`.
- Text output now prints navigation/internal/unknown facet key counts so AI
  navigation view repair can start from visible facet roles instead of one
  noisy mixed table.
- Kept the feature read-only: it writes no view files, rewrites no zettel
  facets, rebuilds no index, reads no zettel bodies or object bytes, calls no
  providers, and echoes no zettel titles, absolute local paths, provider URLs,
  account ids, emails, tokens, or secret values.

## v0.3.92 - 2026-06-17

- Added `review_summary` output to read-only
  `archive connection-edge-intelligence-plan --dry-run`, separating
  `ambiguous_count` from candidate-level `human_review_required_count` and
  durable-write approval counts.
- The text output now prints human-review-required candidate counts,
  durable-write approval counts, and `auto_writable_count: 0` so
  `ambiguous_count: 0` cannot be mistaken for "ready to write".
- Expanded the human review queue entries with ambiguity and parsimony signals
  while keeping candidate ids opaque.
- Kept the command read-only and privacy-bounded: it writes no candidate
  records, zets, edges, receipts, or manifests; calls no providers or LLMs; and
  echoes no body text, provider URLs, local paths, account ids, emails, tokens,
  or secret values.

## v0.3.91 - 2026-06-17

- Added read-only CLI `archive index-health <archive-root> --dry-run` and MCP
  `index_health` to check generated-index drift before running `view-zets`,
  `view-health`, `related-zets`, or `search`.
- The check compares live zettel paths and basic frontmatter metadata
  (`id`, `status`, and `kind`) against rows in `db/archive-index.sqlite`, and
  flags zettel files modified after the index was generated.
- Output reports missing live zets, extra indexed paths, changed metadata, and
  modified-after-index samples with archive-relative paths only.
- Kept the command read-only: it writes nothing, rebuilds no index, reads no
  object bytes, calls no providers, and echoes no zettel body text, zettel
  titles, absolute local paths, provider URLs, account ids, emails, tokens, or
  secret values.

## v0.3.90 - 2026-06-17

- Added read-only CLI `archive view-health <archive-root> --dry-run` and MCP
  `view_health` to diagnose saved view drift before editing `views/*.yml`.
- The health check reads the generated local index and reports saved view
  counts by `active`, `empty_result`, and `blocked`, plus per-filter facet
  diagnostics and observed facet value samples for keys used by saved views.
- This helps real archives discover why default or imported AI navigation views
  return zero zets when saved filters such as `facets.domain` no longer match
  the actual facet distribution.
- Kept the command read-only: it writes nothing, reads no zettel bodies, echoes
  no zettel titles, absolute local paths, provider URLs, account ids, emails,
  tokens, or secret values, calls no providers, and reads no object bytes.

## v0.3.89 - 2026-06-17

- Added read-only CLI `archive notion-objet-link-plan --path <zet.md>|--zettel-id
  <id> --dry-run` and MCP `notion_objet_link_plan` for the Phase 3 gap where
  imported zet bodies contain Notion provider locators instead of
  `sha256:<hex>` or `objet:sha256:<hex>` refs.
- The planner scans one non-redacted zettel for Notion provider locators,
  groups them by opaque `sha256:` locator fingerprint, and matches them against
  existing `objects/manifests/files.jsonl` records when the manifest carries an
  exact redacted locator field or reviewed locator fingerprint.
- Candidate output surfaces only safe manifest object ids, match field names,
  store labels, and resolver states, so a reviewed operator can replace the
  locator with `objet:sha256:<hex>` or write a reviewed embed edge later.
- Kept the new path read-only and privacy-bounded: it writes nothing, calls no
  providers, starts no OAuth, creates no provider or presigned URLs, reads no
  object bytes, and echoes no zettel body text, frontmatter values, provider
  URLs, page titles, local paths, account ids, emails, tokens, or secret values.

## v0.3.88 - 2026-06-17

- Added overview-first zet reading through `archive read-zettel --section
  overview`, returning a cheap first-read card with gist, facets, tie counts,
  and edge previews while omitting the full body and full frontmatter details.
- Added `first_read` to `archive block-header --dry-run` output so AI runtimes
  can inspect a zet's short meaning signal and tie summary before reading the
  full body. The first-read card stays outside `header_preview`, so existing
  header hash boundaries are not redefined.
- Added approval-gated `archive migrate --target link-types-v0.3` to append
  missing recommended connection edge vocabulary from the base
  `zettel-kasten/types.yml` into stale archive-local `types.yml` files.
- Extended `archive zettel-edge` target resolution so safe external refs such
  as `zet:notion:ZET637` can resolve to archive-local zet ids such as
  `zet_notion_db3_ZET0637` before the edge preview/write.
- Hardened mint and draft safety checks so plain `https://` provider URLs in
  zet bodies, including Notion page mentions, block `object_id_only` even when
  legacy frontmatter checklist values claimed the item was already passed.
- Kept the new paths local and privacy-bounded: they call no providers, start
  no OAuth, read no source exports, read no object bytes, write no bulk edge
  candidates, expose no provider URLs, and do not implement Notion
  embed-to-objet sha256 conversion yet.

## v0.3.87 - 2026-06-17

- Added read-only CLI `archive connection-edge-intelligence-plan
  --evidence <archive-relative-json> --source notion --dry-run`, with alias
  `connection-edge-classification-plan`, for reviewing sanitized connection
  fixture candidates before durable edge writes.
- The plan separates source mechanism from relationship meaning, keeps current
  active edge types conservative, and surfaces provisional meaning labels such
  as `format_variant`, `responds_to`, `fulfills`, `enabling`, and `sequence`
  as review labels rather than active link types.
- Added ambiguity, parsimony, and human-review queue signals so vague
  `semantic` links can be named more specifically or dropped before
  `zettel-edge` writes.
- Kept the command read-only: it reads no real exports, source bodies,
  derived-text bodies, or comment bodies, calls no providers or LLMs, runs no
  multi-lens AI classifier, writes no candidates, zets, edges, receipts, or
  manifests, and echoes no provider URLs, local paths, page titles, comment
  bodies, source body text, derived-text body text, account ids, emails,
  tokens, or secret values.

## v0.3.86 - 2026-06-17

- Added read-only CLI `archive object-storage-upload-evidence-audit
  --receipt <archive-relative-json> --dry-run` for checking a v0.3.85 upload
  evidence receipt against `objects/manifests/files.jsonl`.
- The audit verifies receipt schema, lifecycle action, safe provider/store
  labels, non-secret privacy flags, closed no-provider actions, manifest update
  completion, linked `object_storage` locations, `declared_uploaded`
  availability, sha256 content-addressed key hints, and receipt/location count
  consistency.
- Kept the audit read-only: it writes no audit receipt, reads no source bytes,
  computes no local source hashes, calls no provider APIs, performs no remote
  HEAD checks, uploads/downloads/syncs nothing, creates no provider URLs, reads
  no secrets, and echoes no receipt path, manifest path, object ids, locations,
  provider URLs, bucket names, account ids, emails, tokens, or secret values.

## v0.3.85 - 2026-06-17

- Added approval-gated CLI `archive object-storage-upload-evidence
  --ledger <jsonl> --dry-run|--approve` for registering reviewed external
  object-storage upload evidence without provider calls.
- Dry-run mode reads UTF-8 JSONL upload evidence ledgers, counts successful
  `uploaded`, `verified`, `succeeded`, `already_present`, or `ok` rows, matches
  sha256 objects against `objects/manifests/files.jsonl`, previews manifest
  location updates, and echoes no ledger paths or row values.
- Approved mode requires `--reviewed-by` and a safe `--store-ref`, writes a
  non-secret receipt under
  `receipts/providers/object-storage-upload-evidence/`, and adds
  `object_storage` locations with `declared_uploaded` availability to existing
  object manifest records.
- Kept live provider work closed: no source bytes are read, no local hashes are
  computed, no R2/S3/API calls are made, no HEAD checks are performed, no
  upload/download/sync happens, no provider URLs or bucket names are created,
  and no secrets are read or echoed.

## v0.3.84 - 2026-06-17

- Added read-only CLI `archive ai-response-concept-guide --topic all
  --dry-run`, with aliases `ai-concept-guide` and `wom-concept-guide`.
- The command returns beginner-facing explanation cards for sha256 object
  identity vs location, object manifests vs zets, and the
  `objet -> derived text -> zet` layer split.
- Added structured safe routing hints and overclaim guardrails so an AI runtime
  does not claim upload, remote availability, provider URLs, or manifest proof
  without receipts.
- Kept the guide read-only: no source bytes, derived-text bodies, manifest
  writes, receipt writes, draft zets, minted zets, object uploads, provider
  calls, source filenames, local paths, provider URLs, account ids, emails,
  tokens, or secret values are produced.

## v0.3.83 - 2026-06-17

- Extended read-only `archive derive-text coverage --dry-run` and alias
  `archive derive-text-coverage --dry-run` with a `manifest_quality` block for
  existing `objects/manifests/derived-text.jsonl` records.
- The coverage gate now reports and blocks false complete claims when
  derived-text records are missing required extraction provenance such as
  `tool_version`, `tool_name`, `derivation_kind`, or `review_status`.
- `tool_version` values such as blank, `unknown`, `n/a`, `none`, `todo`, or
  `tbd` are treated as quality issues.
- Kept the workflow read-only: no source bytes, derived-text bodies, parser/OCR
  tools, provider APIs, receipts, derived text writes, zets, local paths, tool
  paths, provider URLs, tokens, or secret values are produced.

## v0.3.82 - 2026-06-17

- Added approval-gated CLI `archive zettel-edge --from-zettel <zet>
  --target <zet-or-objet> --edge-type <type> --dry-run|--approve`, with
  aliases `link-zettel-edge` and `write-zettel-edge`.
- The command writes exactly one reviewed edge to source zettel frontmatter and
  one non-secret receipt under `receipts/edges/*.zettel-edge.json`.
- Target validation is local and narrow: `zet_<id>` targets must resolve to an
  existing zettel, and `sha256:<64hex>` / `objet:sha256:<64hex>` targets must
  resolve through `objects/manifests/files.jsonl`.
- Duplicate `type + target` edges are blocked, `edge_type` must already be
  defined in `zettel-kasten/types.yml`, and MCP still exposes no write tool for
  this surface.
- Kept the workflow local and approval-gated: no Notion call, OAuth, real
  export read, comment read, media download, candidate record write, object
  manifest update, provider URL, local path, raw export path, page title,
  comment body, account id, email, token, or secret value is produced. The
  command does not echo zettel body text or zettel titles.

## v0.3.81 - 2026-06-16

- Added read-only `archive connection-evidence-parse-fixture --evidence
  <archive-relative-json> --source notion --dry-run`, aliases
  `connection-evidence-parser-fixture` and
  `notion-connection-evidence-parser-fixture`, and MCP
  `connection_evidence_parse_fixture`.
- Added fake archive fixture `workbench/connection-evidence.sample.json` so the
  parser path can be tested without real client exports.
- The fixture parser emits candidate edge previews for relation properties,
  synced block references, database view/filter snapshots, internal hyperlinks,
  page mentions, comment context, and objet embeds. It writes nothing and keeps
  real Notion export parsing unimplemented.
- Kept the workflow read-only: no Notion call, OAuth, real export read, comment
  read, media download, candidate record write, zet write, edge write, receipt
  write, object manifest update, provider URL, local path, raw export path, page
  title, comment body, account id, email, token, or secret value is produced.

## v0.3.80 - 2026-06-16

- Added read-only `archive connection-evidence-parser-contract --source
  notion --dry-run`, aliases `connection-parser-contract` and
  `notion-connection-parser-contract`, and MCP
  `connection_evidence_parser_contract`.
- Defined the future Notion connection evidence parser contract before real
  export parsing: accepted input lanes, candidate edge record fields, static
  snapshot requirements for dynamic view/filter and comment-context evidence,
  parser stages, and redaction rules.
- Kept the workflow read-only: no Notion call, OAuth, export read, comment read,
  media download, parser execution, candidate record write, zet write, edge
  write, receipt write, object manifest update, provider URL, local path, raw
  export path, page title, comment body, account id, email, token, or secret
  value is produced.

## v0.3.79 - 2026-06-16

- Added the recommended Notion connection edge vocabulary to the base
  `zettel-kasten/types.yml` and fake archive types:
  `material`, `derived`, `semantic`, `embed`, `mention`, `view_query`, and
  `comment_context`.
- Updated `connection-import-plan` so the current fake archive reports those
  recommended edge types as present instead of missing.
- Clarified that this is still a vocabulary/schema checkpoint before evidence
  parsing or edge writes: no Notion call, OAuth, export read, comment read,
  media download, zet write, edge write, receipt write, object manifest update,
  provider URL, local path, page title, comment body, account id, email, token,
  or secret value is produced.

## v0.3.78 - 2026-06-16

- Added read-only `archive object-storage-adapter-execution-contract
  --operation upload_object --dry-run`, aliases
  `object-storage-upload-execution-contract` and
  `objet-storage-adapter-execution-contract`, and MCP
  `object_storage_adapter_execution_contract`.
- The contract fixes the future upload adapter rules before live execution:
  sha256 content-addressed remote keys, approval receipt re-verification, local
  SHA-256 verification before upload, provider HEAD/idempotency checks, bounded
  retry/resume ledger, non-secret execution receipt, and manifest update only
  after provider confirmation.
- Clarified S3-compatible integrity handling: provider SHA-256 checksums are
  preferred when supported, and ETag is not treated as WOM SHA-256 unless a
  provider-specific policy verifies that equivalence for the exact upload mode.
- Kept the workflow read-only: no provider call, secret retrieval, object byte
  read, local hash computation, upload, remote availability check, resume ledger
  write, receipt write, manifest update, bucket name, prefix, provider URL,
  local absolute path, exact credential ref, token, or secret value is produced.

## v0.3.77 - 2026-06-16

- Added read-only `archive connection-import-plan --source notion --dry-run`
  and MCP `connection_import_plan` for Notion connection evidence.
- The planner maps relation properties, synced block references, database
  view/filter snapshots, internal links, page mentions, comment context, and
  objet embeds to typed-edge candidates.
- Added a recommended edge vocabulary for this feedback slice:
  `material`, `derived`, `semantic`, `embed`, `mention`, `view_query`, and
  `comment_context`.
- The planner checks the archive's allowed link types and reports which
  recommended edge types are missing before any write command exists.
- Kept the workflow read-only: no Notion call, OAuth, export read, comment
  read, media download, zet write, edge write, receipt write, object manifest
  update, provider URL, local path, page title, comment body, account id,
  email, token, or secret value is produced.

## v0.3.76 - 2026-06-16

- Added explicit `large_media_export_trap` output to
  `archive external-export-plan` so broad workspace/database exports that can
  pull uploaded files, attachments, images, audio, or video are visible before
  anyone starts a provider export.
- Added safe first-pass command shapes for `text_only` and `targeted_pages`
  planning before bulk media handling.
- Extended Notion guidance with a large-workspace fallback: split oversized or
  failing workspace exports into smaller top-level page or database batches
  before retrying media-heavy export work.
- Kept the workflow read-only: no provider export, provider API call, OAuth,
  file read, media-byte read, attachment download, archive write, provider URL,
  local path, filename, account id, email, token, or secret value is produced.

## v0.3.75 - 2026-06-16

- Added `wom-kit/docs/ai-response-concept-guide.md`, a beginner-facing guide
  for AI runtimes explaining sha256 object identity vs location, object
  manifests vs zets, and the `objet -> derived text -> zet` layer split.
- Linked the guide from the English and Korean public documentation maps.
- Updated the capability matrix and README status to mark the guide as
  documented-only, with no new command, MCP tool, provider call, upload, source
  read, derived-text capture, draft, mint, transport, or write behavior.

## v0.3.74 - 2026-06-16

- Extended Cloudflare R2 setup guidance with English/Korean dashboard label
  hints and location-based navigation for bucket creation and R2 API token
  creation.
- Clarified that R2 API token creation is reached from the R2 account/overview
  area, not from one bucket's settings page.
- Clarified the post-creation credential split: S3-compatible object access
  uses the Access Key ID plus Secret Access Key pair; the separate Token value
  should not be pasted into chat or stored in WOM unless a future non-S3
  API-token flow explicitly asks for it.
- Configured the MCP stdio entrypoint to use UTF-8 so localized guidance labels
  remain readable on Windows pipes.
- Kept the workflow read-only: no Cloudflare dashboard is opened, no provider
  API is called, no bucket or API token is created, no upload/download occurs,
  and no provider URLs, local paths, tokens, or secret values are echoed.

## v0.3.73 - 2026-06-16

- Extended `archive prehashed-objet-ledger` with `--mime-field <json-field>`
  so externally verified ledgers can carry safe MIME values into
  `objects/manifests/files.jsonl` without echoing row values or reading blob
  bytes.
- Updated `derive-text coverage` so existing derived-text records count as a
  conservative textual signal when older external manifest rows lack useful
  extension/MIME metadata, preventing misleading `0/0` coverage reads after a
  real extraction pass has already been linked.
- Added `wom-kit/schemas/derived-text-capture-manifest-item.schema.json` and
  documented the required `derive-text capture --from-manifest` fields,
  including `tool_version`.
- Kept the workflow closed: no source bytes are read, no providers are called,
  no uploads or downloads are performed, and public/debug output still avoids
  row values, source filenames, local paths, provider URLs, tokens, and secret
  values.

## v0.3.72 - 2026-06-16

- Added `archive imap-mailbox-material-capture-approval-audit <archive-root>
  --material-selection-receipt <archive-relative-json> --approval-receipt
  <archive-relative-json> --capture-action
  message_body_capture|attachment_capture|derived_text_capture
  --expected-decision needs_review|approve_once|deny --dry-run --format json`.
- Added aliases `archive imap-material-capture-approval-audit` and
  `archive mailbox-material-capture-approval-audit`.
- The new read-only audit validates that one material capture approval receipt
  matches the selected material receipt, expected capture action, expected
  decision, future-adapter action flags, redaction flags, and closed-action
  flags.
- Kept material capture closed: the command reads no original execution
  receipt, opens no IMAP connection, reads no environment variables, opens no
  keyring/password manager, reads no message headers, bodies, or attachments,
  creates no derived text, writes no files, and echoes no approval receipt
  path, material-selection receipt path, execution receipt path, candidate
  refs, local paths, tokens, or secret values.

## v0.3.71 - 2026-06-16

- Added `archive imap-mailbox-material-capture-approval-plan <archive-root>
  --material-selection-receipt <archive-relative-json> --capture-action
  message_body_capture|attachment_capture|derived_text_capture --decision
  needs_review|approve_once|deny --dry-run|--approve --format json`.
- Added aliases `archive imap-material-capture-approval-plan`,
  `archive mailbox-material-capture-approval-plan`, and
  `archive imap-mailbox-material-capture-approval`.
- The new approval-gated write reuses the material capture execution contract
  and writes one non-secret human decision receipt under
  `receipts/imap/material-capture-approvals/`.
- Kept material capture closed: the command reads no original execution
  receipt, opens no IMAP connection, reads no environment variables, opens no
  keyring/password manager, reads no message headers, bodies, or attachments,
  creates no derived text, writes no message material, and echoes no
  material-selection receipt path, execution receipt path, candidate refs,
  local paths, tokens, or secret values.

## v0.3.70 - 2026-06-16

- Added `archive imap-mailbox-material-capture-execution-contract <archive-root>
  --material-selection-receipt <archive-relative-json> --capture-action
  message_body_capture|attachment_capture|derived_text_capture --dry-run
  --format json`.
- Added aliases `archive imap-material-capture-execution-contract` and
  `archive mailbox-material-capture-execution-contract`.
- The new read-only gate reuses the material capture request validation and
  returns a future local-adapter execution contract: required inputs, allowed
  actions after separate approval, and a non-secret output receipt shape.
- Kept material capture closed: the command reads no original execution
  receipt, opens no IMAP connection, reads no environment variables, opens no
  keyring/password manager, reads no message headers, bodies, or attachments,
  creates no derived text, writes no files, and echoes no material-selection
  receipt path, execution receipt path, candidate refs, local paths, tokens, or
  secret values.

## v0.3.69 - 2026-06-16

- Added `archive imap-mailbox-material-capture-request-plan <archive-root>
  --material-selection-receipt <archive-relative-json> --capture-action
  message_body_capture|attachment_capture|derived_text_capture --dry-run
  --format json`.
- Added aliases `archive imap-material-capture-request-plan` and
  `archive mailbox-material-capture-request-plan`.
- The new read-only gate validates a non-secret material selection receipt and
  checks whether the selected future material lane authorizes the requested
  body, attachment, or derived-text capture action.
- Kept material capture closed: the command reads no original execution
  receipt, opens no IMAP connection, reads no environment variables, opens no
  keyring/password manager, reads no message headers, bodies, or attachments,
  creates no derived text, writes no files, and echoes no material-selection
  receipt path, execution receipt path, candidate refs, local paths, tokens, or
  secret values.

## v0.3.68 - 2026-06-16

- Added `archive imap-mailbox-material-selection-record <archive-root>
  --execution-receipt <archive-relative-json> --selection-mode
  human_review_queue|body_candidates|attachment_candidates|derived_text_candidates
  --selected-index <n> --dry-run|--approve --format json`.
- Added aliases `archive imap-material-selection-record` and
  `archive mailbox-material-selection-record`.
- The new approval-gated write records one-based candidate indexes from a
  validated IMAP header metadata scan receipt, creating a non-secret material
  selection receipt under `receipts/imap/material-selections/`.
- Kept message material closed: the command writes no candidate refs, echoes no
  execution receipt path, opens no IMAP connection, reads no environment
  variables, opens no keyring/password manager, reads no message headers,
  bodies, or attachments, creates no derived text, starts no OAuth, and calls no
  providers.

## v0.3.67 - 2026-06-16

- Added `archive imap-mailbox-material-selection-plan <archive-root>
  --execution-receipt <archive-relative-json> --selection-mode
  human_review_queue|body_candidates|attachment_candidates|derived_text_candidates
  --dry-run --format json`.
- Added aliases `archive imap-material-selection-plan` and
  `archive mailbox-material-selection-plan`.
- The new read-only planner consumes an existing non-secret IMAP header
  metadata scan execution receipt and plans the next human material review
  lane before any future body, attachment, or derived-text capture work.
- Kept the gate closed: it opens no IMAP connection, reads no environment
  variables, opens no keyring/password manager, reads no message headers,
  bodies, or attachments, writes no queue files, and echoes no execution receipt
  path, candidate refs, subjects, senders, recipients, local paths, tokens, or
  secret values.

## v0.3.66 - 2026-06-16

- Added `archive external-export-plan <archive-root> --source
  notion|google_drive|generic_workspace --dry-run --format json`.
- The new read-only planner helps users and AI helpers stop before broad
  provider exports that might pull large uploaded files, attachments, images,
  audio, or video into a first local download.
- The planner classifies media risk, recommends text-first, targeted, or
  stop-and-split-media export modes, and links the later `scan-source`,
  `import-external`, and object-storage recommendation commands.
- Kept the export planner closed: it starts no provider export, calls no
  providers, starts no OAuth, reads no files or media bytes, downloads no
  attachments, writes no archive files, and echoes no provider URLs, local
  paths, filenames, account ids, emails, tokens, or secret values.

## v0.3.65 - 2026-06-16

- Extended `archive version <root> --format json` and runtime-context
  `wom_kit_version` pin discovery so an inspected archive root can also find a
  project-local installed-version pin in the parent project root.
- Added redacted logical pin-location reporting through `project_pin.path`,
  `project_pin.pin_root`, and `project_pin.checked_locations`, including
  locations such as `parent_of_archive/.zettel-kasten/installed-version.txt`.
- Normalized UTF-8 BOM-prefixed installed-version files so Windows-created pin
  files do not produce confusing version strings.
- Kept the version check read-only and private by default: it writes no files,
  calls no providers, reads no secrets, and does not echo local absolute paths
  unless the trusted debugging flag is used.

## v0.3.64 - 2026-06-16

- Added `archive beginner-setup-manual <archive-root> --topic
  object_storage_setup_manual --dry-run --format json`.
- Extended `archive object-storage-recommendation` so the recommendation output
  surfaces the proposed bucket name, the bucket naming rule, the exact
  `beginner-setup-manual --topic object_storage_setup_manual` command, and the
  exact `archive object-storage --dry-run` command.
- Added Cloudflare R2 bucket/API-token setup guidance for beginner fields:
  Location, Jurisdiction, Standard storage default, private/public-access
  boundary, Object Read & Write permission, single-bucket scope, TTL/IP
  restriction tradeoffs, and credential-ref bridging.
- Kept the flow read-only: no provider APIs are called, no live pricing or
  bucket availability is checked, no bucket/API token is created, no object
  bytes are read, no files are uploaded, no secrets are read, and no provider
  URLs or secret values are echoed by CLI JSON.

## v0.3.63 - 2026-06-16

- Added `archive imap-mailbox-header-scan-receipt-audit <archive-root>
  --execution-receipt <archive-relative-json> --dry-run|--approve --format json`.
- Added aliases `archive imap-header-scan-receipt-audit` and
  `archive mailbox-header-scan-audit`.
- The new command validates an existing non-secret IMAP header metadata scan
  execution receipt, checks opaque candidate refs and redaction flags, and can
  write a separate non-secret audit receipt under
  `receipts/imap/adapter-execution-audits/`.
- Kept the audit offline and closed: it opens no IMAP connection, reads no
  environment variables, opens no keyring/password manager, reads no
  headers/bodies/attachments, calls no providers, and does not echo the
  execution receipt path or candidate refs.

## v0.3.62 - 2026-06-16

- Added `archive imap-mailbox-header-metadata-scan <archive-root>
  --dry-run|--approve --format json`.
- Added aliases `archive imap-header-metadata-scan` and
  `archive mailbox-header-metadata-scan`.
- Opened the first narrow, approval-gated live IMAP path: app-password auth via
  `env:` refs, IMAP TLS connection, login, read-only inbox select, UID search,
  limited header fetch, opaque candidate refs, and non-secret execution receipt
  writing.
- Kept broad mail ingestion closed: the command returns no username/password
  values, environment variable names, exact credential refs, exact mailbox refs,
  IMAP host values, raw UIDs, Message-ID values, subjects, senders/recipients,
  raw headers, bodies, attachments, provider URLs, or local absolute paths.

## v0.3.61 - 2026-06-16

- Added `archive imap-mailbox-adapter-execution-contract <archive-root>
  --dry-run --format json`.
- Added aliases `archive imap-mailbox-adapter-execution-plan` and
  `archive mailbox-adapter-execution-contract`.
- The new read-only contract wraps IMAP adapter preflight and becomes ready only
  when the adapter manifest, approval receipt, selection plan, and audit
  preview are ready.
- Kept live IMAP execution closed: the command opens no connection, logs into
  nothing, selects no mailbox, reads no headers/bodies/attachments, retrieves
  no credential values, calls no providers, writes no receipts, and writes no
  files.

## v0.3.60 - 2026-06-16

- Added `archive credential-semantic-extraction-recipe <archive-root>
  --source-label <safe-label> --dry-run --format json`.
- Added aliases `archive credential-extraction-recipe` and
  `archive secret-semantic-extraction-recipe`.
- The new read-only recipe helps a human and AI split complex credential notes
  into separate semantic candidates before plaintext migration planning,
  including multi-account, multi-secret, mail, API/CLI token, SSO/passkey,
  recovery-code, wallet/private-key, and status/toggle notes.
- Kept the recipe closed by default: it reads no plaintext files, detects no
  secret values, opens no vaults/keyrings/browser stores, calls no providers,
  writes no files, and returns no secret values to AI.

## v0.3.59 - 2026-06-16

- Added a derived-text completeness signal to
  `archive derive-text coverage <archive-root> --dry-run --format json` and
  alias `archive derive-text-coverage`.
- The new `completeness_signal` block distinguishes manifest-scoped derived
  text coverage from full external workspace/mailbox/cloud-drive mirror
  completion.
- Added `wom-kit/docs/derived-text-completeness-signal.md`, release notes,
  capability matrix coverage, README/documentation map links, and CLI tests.
- Kept the signal read-only and non-secret: it reads no source file bodies,
  scans no external workspaces, calls no providers, reads no secrets, writes no
  files, and echoes no local absolute paths.

## v0.3.58 - 2026-06-16

- Added runtime canonical entrypoint metadata to
  `archive runtime-context <archive-root> --format json`.
- The new `canonical_entrypoints` block names `archive.yml` as the start-here
  file and lists the archive-relative files/directories an AI should treat as
  authoritative for identity, local agent instructions, source bindings,
  provider setup metadata, canonical zets, draft inbox, objets, derived text,
  saved views, and schema context.
- Added `wom-kit/docs/runtime-canonical-entrypoints.md`, release notes,
  capability matrix coverage, README/documentation map links, and CLI tests.
- Kept the check read-only and non-secret: it reads no file bodies, writes no
  files, calls no providers, reads no secrets, and echoes no local absolute
  paths by default.

## v0.3.57 - 2026-06-16

- Added a read-only WOM-kit version truth-source checkpoint:
  `archive --version`, `archive version [inspection-root] --format text|json`,
  and `runtime-context` JSON field `wom_kit_version`.
- The version report names `wom_kit.__version__` as the package source of truth,
  compares it with `wom-kit/pyproject.toml` when running from a source checkout,
  and can compare an optional project pin such as
  `.zettel-kasten/source/installed-version.txt`.
- Added `wom-kit/docs/version-truth-source.md`, release notes, capability
  matrix coverage, README/documentation map links, and CLI tests.
- Kept the check local and non-secret: it writes no files, calls no providers,
  reads no secrets, and redacts local paths by default.

## v0.3.56 - 2026-06-16

- Added approval-gated local IMAP adapter audit receipt writing:
  `archive imap-mailbox-adapter-audit-write --dry-run|--approve` and alias
  `archive mailbox-adapter-audit-write`.
- The command wraps the existing IMAP adapter audit preview and writes exactly
  one non-secret JSON receipt under `receipts/imap/adapter-audits/` only after
  explicit `--approve --reviewed-by <actor>`.
- Added replay protection when the same audit receipt already exists.
- Added `wom-kit/docs/imap-mailbox-adapter-audit-write.md`, public
  documentation links, capability matrix coverage, and CLI tests.
- Kept the command local and non-secret: it exposes no MCP write tool, opens no
  IMAP connection, attempts no login, selects no mailbox, searches no mailbox,
  lists no candidate messages, reads no IMAP UIDs, Message-ID values, headers,
  bodies, or attachments, creates no derived text, retrieves no secrets, starts
  no OAuth, calls no providers, and echoes no email addresses, username values,
  exact account refs, exact credential refs, exact mailbox refs, IMAP host
  values, provider URLs, message ids, subjects, sender or recipient values,
  attachment names, approval receipt paths, selection receipt paths, local
  absolute paths, tokens, or secret values.

## v0.3.55 - 2026-06-16

- Added read-only IMAP adapter preflight planning:
  `archive imap-mailbox-adapter-preflight-plan --dry-run`, alias
  `archive imap-mailbox-adapter-execution-preflight --dry-run`, and alias
  `archive mailbox-adapter-preflight --dry-run`.
- Added MCP tool `imap_mailbox_adapter_preflight_plan` for the same read-only
  preflight surface.
- The preflight composes adapter readiness, manifest status, approval receipt
  verification, mailbox selection planning, and adapter audit receipt preview
  into one final gate before any future live IMAP adapter.
- `preflight_state` returns `ready_for_future_adapter_after_approval` only when
  the adapter manifest is `present_and_schema_valid`, the request package has a
  verified approval receipt, selection is ready, and the audit preview is ready.
- Added `wom-kit/docs/imap-mailbox-adapter-preflight-plan.md`, public
  documentation links, capability matrix coverage, and CLI/MCP tests.
- Kept the preflight read-only: it writes nothing, exposes no live IMAP tool,
  opens no IMAP connection, attempts no login, selects no mailbox, searches no
  mailbox, lists no candidate messages, reads no IMAP UIDs, Message-ID values,
  headers, bodies, or attachments, creates no derived text, retrieves no
  secrets, starts no OAuth, calls no providers, and echoes no email addresses,
  username values, exact account refs, exact credential refs, exact mailbox
  refs, IMAP host values, provider URLs, message ids, subjects, sender or
  recipient values, attachment names, approval receipt paths, selection receipt
  paths, schema validation issue values, local absolute paths, tokens, or secret
  values.

## v0.3.54 - 2026-06-16

- Extended `archive imap-mailbox-adapter-readiness-plan --dry-run` and MCP
  `imap_mailbox_adapter_readiness_plan` with optional `--adapter-id` /
  `adapter_id` manifest status checks.
- The readiness output now includes `adapter_manifest_summary.status` with
  `not_checked`, `missing`, `present_and_schema_valid`, `invalid`, or
  `blocked`.
- When a safe adapter id is supplied, readiness reads only the archive-relative
  non-secret manifest under `config/imap-adapters/`, validates it against
  `imap-mailbox-adapter-manifest.schema.json`, and checks the archive id,
  adapter id, privacy contract, and closed actions without echoing user-edited
  schema issue values.
- Updated `wom-kit/docs/imap-mailbox-adapter-readiness-plan.md`, the capability
  matrix, README version baseline, release notes, CLI tests, and MCP tests.
- Kept the check read-only: it writes nothing, exposes no live write MCP tool,
  opens no IMAP connection, attempts no login, selects no mailbox, searches no
  mailbox, lists no candidate messages, reads no IMAP UIDs, Message-ID values,
  headers, bodies, or attachments, creates no derived text, retrieves no
  secrets, starts no OAuth, calls no providers, and echoes no email addresses,
  username values, exact account refs, exact credential refs, exact mailbox
  refs, IMAP host values, provider URLs, message ids, subjects, sender or
  recipient values, attachment names, approval receipt paths, selection receipt
  paths, schema validation issue values, local absolute paths, tokens, or secret
  values.

## v0.3.53 - 2026-06-16

- Added CLI `archive imap-mailbox-adapter-manifest-write --dry-run|--approve`
  with alias `archive mailbox-adapter-manifest-write`.
- `--dry-run` previews the schema-validated non-secret IMAP adapter manifest and
  the write receipt paths without writing files.
- `--approve --reviewed-by <actor>` writes exactly one manifest under
  `config/imap-adapters/` and one non-secret receipt under
  `receipts/imap/adapter-manifests/`, refusing overwrite/replay.
- Added `wom-kit/docs/imap-mailbox-adapter-manifest-write.md`, public
  documentation links, capability matrix coverage, and CLI tests.
- Kept the command local and non-secret: it exposes no MCP live write tool,
  opens no IMAP connection, attempts no login, selects no mailbox, searches no
  mailbox, lists no candidate messages, reads no IMAP UIDs, Message-ID values,
  headers, bodies, or attachments, creates no derived text, retrieves no
  secrets, starts no OAuth, calls no providers, and echoes no email addresses,
  username values, exact account refs, exact credential refs, exact mailbox
  refs, IMAP host values, provider URLs, message ids, subjects, sender or
  recipient values, attachment names, approval receipt paths, selection receipt
  paths, local absolute paths, tokens, or secret values.

## v0.3.52 - 2026-06-16

- Added JSON Schema `wom-kit/schemas/imap-mailbox-adapter-manifest.schema.json`
  for future IMAP mailbox adapter manifests.
- Updated `archive imap-mailbox-adapter-manifest-plan --dry-run` and MCP
  `imap_mailbox_adapter_manifest_plan` to validate the non-secret manifest
  preview against that schema.
- The preview now returns `schema_validation` metadata so CLI and MCP callers
  can see whether the generated manifest shape passed the contract.
- Updated IMAP manifest documentation, capability matrix coverage, public
  documentation links, and tests for the schema baseline.
- Kept the release read-only: it writes no adapter manifests, executes no live
  adapters, opens no IMAP connection, attempts no login, selects no mailbox,
  searches no mailbox, lists no candidate messages, reads no IMAP UIDs,
  Message-ID values, headers, bodies, or attachments, creates no derived text,
  retrieves no secrets, starts no OAuth, calls no providers, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message ids, subjects, sender
  or recipient values, attachment names, approval receipt paths, selection
  receipt paths, local absolute paths, tokens, or secret values.

## v0.3.51 - 2026-06-16

- Added read-only IMAP adapter manifest previews:
  `archive imap-mailbox-adapter-manifest-plan --dry-run`, alias
  `archive imap-mailbox-adapter-manifest --dry-run`, and alias
  `archive mailbox-adapter-manifest-plan --dry-run`.
- Added MCP tool `imap_mailbox_adapter_manifest_plan` for the same read-only
  preview surface.
- The planner previews a non-secret declaration under `config/imap-adapters/`
  with supported provider labels, operation labels, selection rules, approval
  requirements, audit requirements, privacy contract, and closed actions.
- Added `wom-kit/docs/imap-mailbox-adapter-manifest-plan.md` and public
  documentation links.
- Kept the preview read-only: it writes no adapter manifests, executes no live
  adapters, opens no IMAP connection, attempts no login, selects no mailbox,
  searches no mailbox, lists no candidate messages, reads no IMAP UIDs,
  Message-ID values, headers, bodies, or attachments, creates no derived text,
  retrieves no secrets, starts no OAuth, calls no providers, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message ids, subjects, sender
  or recipient values, attachment names, approval receipt paths, selection
  receipt paths, local absolute paths, tokens, or secret values.

## v0.3.50 - 2026-06-16

- Added read-only IMAP adapter audit receipt previews:
  `archive imap-mailbox-adapter-audit-plan --dry-run`, alias
  `archive imap-mailbox-adapter-audit --dry-run`, and alias
  `archive mailbox-adapter-audit-plan --dry-run`.
- Added MCP tool `imap_mailbox_adapter_audit_plan` for the same read-only
  preview surface.
- The planner composes `imap-mailbox-selection-plan` with safe future adapter
  result metadata, then previews a non-secret receipt shape under
  `receipts/imap/adapter-audits/`.
- Added `wom-kit/docs/imap-mailbox-adapter-audit-plan.md` and public
  documentation links.
- Kept the preview read-only: it writes no audit receipts, selection receipts,
  approval receipts, or adapter manifests, executes no live adapters, opens no
  IMAP connection, attempts no login, selects no mailbox, searches no mailbox,
  lists no candidate messages, reads no IMAP UIDs, Message-ID values, headers,
  bodies, or attachments, creates no derived text, retrieves no secrets, starts
  no OAuth, calls no providers, and echoes no email addresses, username values,
  exact account refs, exact credential refs, exact mailbox refs, IMAP host
  values, provider URLs, message ids, subjects, sender or recipient values,
  attachment names, approval receipt paths, selection receipt paths, local
  absolute paths, tokens, or secret values.

## v0.3.49 - 2026-06-16

- Added read-only IMAP mailbox selection planning:
  `archive imap-mailbox-selection-plan --dry-run`, alias
  `archive imap-mailbox-message-selection-plan --dry-run`, and alias
  `archive mailbox-selection-plan --dry-run`.
- Added MCP tool `imap_mailbox_selection_plan` for the same read-only planning
  surface.
- The planner composes the IMAP operation request package with a safe future
  selector rule such as `newest_first`, `unread_first`, `since_days_window`, or
  `human_review_queue`.
- `selection_state` distinguishes `needs_human_approval`,
  `ready_for_future_adapter_after_approval`, human denial, policy denial, and
  blockers without treating a selector plan as mailbox access.
- Added `wom-kit/docs/imap-mailbox-selection-plan.md` and public documentation
  links.
- Kept the planner read-only: it opens no IMAP connection, attempts no login,
  selects no mailbox, searches no mailbox, lists no candidate messages, reads no
  IMAP UIDs, Message-ID values, headers, bodies, or attachments, creates no
  derived text, retrieves no secrets, starts no OAuth, sends no mail, deletes no
  mail, changes no flags, writes no files or receipts, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message ids, subjects, sender
  or recipient values, attachment names, approval receipt paths, local absolute
  paths, tokens, or secret values.

## v0.3.48 - 2026-06-15

- Added KeePassXC CSV bulk migration guidance to
  `archive beginner-setup-manual --topic credential_bulk_migration --dry-run`.
- The new beginner topic covers normal import vs passkey import, temporary
  import database creation, UTF-8 CSV settings, header/field separator/text
  qualifier/comment character choices, Group/Title/Username/Password/URL/Notes
  column mapping, `Database > Merge from Database`, expected root/group tree
  shape, slash-created nested groups, and safe cleanup order.
- Linked the bulk migration guide back to
  `credential-plaintext-migration-plan` so the plan-level and screen-level
  workflows are easier to follow together.
- Updated the beginner setup manual, capability matrix, README summary, and
  release notes.
- Kept the topic read-only: it reads no CSV, opens no KeePassXC window, creates
  no temporary database, imports or merges no vault, records no database path,
  deletes no temporary files, writes nothing, and echoes no secret values,
  usernames, emails, provider URLs, local paths, CSV paths, or vault paths.

## v0.3.47 - 2026-06-15

- Added read-only IMAP mailbox adapter readiness checks:
  `archive imap-mailbox-adapter-readiness-plan --dry-run`, alias
  `archive imap-mailbox-adapter-plan --dry-run`, and alias
  `archive mailbox-adapter-readiness --dry-run`.
- Added MCP tool `imap_mailbox_adapter_readiness_plan` for the same
  read-only readiness surface.
- The readiness planner composes the IMAP operation request package with local
  runtime module checks for the future adapter path.
- `readiness_state` now distinguishes `ready_for_request_package`,
  `ready_for_future_adapter_after_approval`, human denial, policy denial, and
  blockers without treating runtime readiness as live mailbox access.
- Added `wom-kit/docs/imap-mailbox-adapter-readiness-plan.md` and public
  documentation links.
- Kept the planner read-only: it opens no IMAP connection, attempts no login,
  selects no mailbox, reads no headers, bodies, or attachments, creates no
  derived text, retrieves no secrets, starts no OAuth, sends no mail, deletes no
  mail, changes no flags, writes no files or receipts, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message headers, message
  bodies, attachment names, approval receipt paths, local absolute paths,
  tokens, or secret values.

## v0.3.46 - 2026-06-15

- Added read-only IMAP mailbox operation request packages:
  `archive imap-mailbox-operation-request-plan --dry-run`, alias
  `archive imap-mailbox-request-plan --dry-run`, and alias
  `archive mailbox-operation-request-plan --dry-run`.
- Added MCP tool `imap_mailbox_operation_request_plan` for the same
  read-only request package surface.
- The package composes `imap-mailbox-plan` and `credential-policy-check` for
  `mail_source_read` into one future-adapter approval gate.
- `request_state` distinguishes `needs_human_approval`,
  `ready_for_future_adapter_after_approval`, human denial, policy denial, and
  blockers without treating missing human approval as live execution readiness.
- `approve_once` requires a verified archive-relative approval receipt before
  the request package can become `ready_for_future_adapter_after_approval`.
- Added `wom-kit/docs/imap-mailbox-operation-request-plan.md` and public
  documentation links.
- Kept the planner read-only: it opens no IMAP connection, attempts no login,
  selects no mailbox, reads no headers, bodies, or attachments, creates no
  derived text, retrieves no secrets, starts no OAuth, sends no mail, deletes no
  mail, changes no flags, writes no files or receipts, and echoes no email
  addresses, username values, exact account refs, exact credential refs, exact
  mailbox refs, IMAP host values, provider URLs, message headers, message
  bodies, attachment names, approval receipt paths, local absolute paths,
  tokens, or secret values.

## v0.3.45 - 2026-06-15

- Added read-only object-storage operation request packages:
  `archive object-storage-operation-request-plan --dry-run`, alias
  `archive object-storage-request-plan --dry-run`, and alias
  `archive objet-storage-operation-request --dry-run`.
- Added MCP tool `object_storage_operation_request_plan` for the same
  read-only request package surface.
- The package composes provider readiness, object target validation,
  presigned URL planning or objet-ref resolution, and `credential-policy-check`
  for `object_storage_request` into one future-adapter approval gate.
- `request_state` now distinguishes `needs_human_approval`,
  `ready_for_future_adapter_after_approval`, human denial, policy denial, and
  blockers without treating missing human approval as live execution readiness.
- `approve_once` requires a verified archive-relative approval receipt before
  the request package can become `ready_for_future_adapter_after_approval`.
- Added `wom-kit/docs/object-storage-operation-request-plan.md` and public
  documentation links.
- Kept the planner read-only: it calls no providers, retrieves no secrets,
  creates no presigned URLs, uploads or downloads nothing, lists no remote
  metadata, reads no object bytes, checks no remote availability, writes no
  files or receipts, and echoes no bucket names, prefixes, provider URLs,
  generated URLs, local absolute paths, exact credential refs, approval receipt
  paths, provider setup receipt paths, tokens, or secret values.

## v0.3.44 - 2026-06-15

- Added a KeePassXC 2.7.x first-vault walkthrough to
  `archive beginner-setup-manual --store-id keepassxc --platform windows
  --dry-run`.
- The walkthrough now gives screen-by-screen and field-by-field guidance for
  the new database wizard: general screen, encryption settings, credentials,
  save dialog, and first entry.
- Added WOM-context field decisions for first local KeePassXC vaults:
  KDBX 4.0, AES-256, Argon2d, and leaving KeePassXC automatic/recommended KDF
  tuning values alone.
- Added explicit conflict guidance for Argon2d vs Argon2id: WOM's beginner
  recommendation is scoped to a local offline KDBX vault threat model; stricter
  workplace/school/regulatory policy still wins when present.
- Kept the manual read-only: it does not open KeePassXC, create a database,
  store database paths, read or write secrets, read environment variables, call
  providers, install tools, or write files.

## v0.3.43 - 2026-06-15

- Added manifest-aware object storage recommendations.
- `archive object-storage-recommendation --scenario auto_from_manifest
  --dry-run` now reads aggregate metadata from `objects/manifests/files.jsonl`
  to infer a scenario before provider setup planning.
- Recommendation output now includes `manifest_analysis`, `scenario_source`,
  and `rough_cost_estimates` with total manifest size, dominant content class,
  content-class percentages, and non-live storage/egress estimate fields.
- Rough estimates use a static 2026-06-15 public-pricing snapshot for
  comparison only; live pricing APIs are not called and humans must still check
  official calculators/docs before spending money.
- Kept the command read-only: it writes no files, reads no object bytes, calls
  no providers, checks no bucket availability, creates no buckets, uploads or
  downloads nothing, creates no presigned URLs, and echoes no object filenames,
  local paths, provider account URLs, tokens, or secret values.

## v0.3.42 - 2026-06-15

- Updated `archive connected-accounts --dry-run` so account-map success is
  separate from the optional local credential catalog status.
- Malformed ignored local credential catalog rows now appear under nested
  `credential_catalog.ok`, `credential_catalog.status`, and
  `credential_catalog.blockers` instead of making the whole connected account
  overview return `ok: false`.
- Kept true account-map blockers, such as unsafe account labels or unreadable
  provider/source binding files, as top-level blockers.
- Updated connected-accounts documentation and capability matrix language for
  the split status model.
- Kept the command read-only: it still writes no files, opens no password
  manager/keyring/browser store, reads no environment variables, calls no
  providers, opens no IMAP connection, reads no source bytes, and echoes no
  exact credential refs, emails, usernames, tokens, provider URLs, local paths,
  or secret values.

## v0.3.41 - 2026-06-15

- Added read-only object storage adapter readiness commands:
  `archive object-storage-adapter-readiness-plan --dry-run`, alias
  `archive object-storage-adapter-plan --dry-run`, and alias
  `archive objet-storage-adapter-readiness --dry-run`.
- Added MCP tool `object_storage_adapter_readiness_plan` for the same
  read-only readiness surface.
- The planner bridges `provider-status`, object-storage setup receipts,
  credential access broker requirements, credential policy checks, human
  approval receipts, adapter manifests, and future audit receipts without
  executing an adapter.
- Added `wom-kit/docs/object-storage-adapter-readiness-plan.md` and public
  documentation links.
- Kept the command read-only: it calls no providers, retrieves no secrets,
  creates no presigned URLs, uploads or downloads nothing, reads no object
  bytes, checks no remote availability, writes no files or receipts, and echoes
  no bucket names, prefixes, provider URLs, local absolute paths, exact
  credential refs, provider setup receipt paths, tokens, or secret values.

## v0.3.40 - 2026-06-15

- Added read-only presigned URL planning commands:
  `archive presigned-url-plan --dry-run`, alias
  `archive object-presigned-url-plan --dry-run`, and alias
  `archive objet-presigned-url-plan --dry-run`.
- Added MCP tool `presigned_url_plan` for the same read-only planning surface.
- The planner reuses `resolve-objet-ref`, validates `object_id`, safe
  `store_ref`, operation, TTL, and object-storage binding presence before any
  future provider adapter.
- Added `wom-kit/docs/presigned-url-plan.md` and public documentation links.
- Kept the command read-only: it creates no presigned URLs, calls no providers,
  retrieves no credential values, reads no object bytes, uploads or downloads
  nothing, writes no files or receipts, and echoes no provider URLs, local
  absolute paths, exact credential refs, bucket URLs, tokens, or secret values.

## v0.3.39 - 2026-06-15

- Added read-only object storage recommendation commands:
  `archive object-storage-recommendation --dry-run`, alias
  `archive object-storage-match --dry-run`, and alias
  `archive objet-storage-recommendation --dry-run`.
- The matcher maps human scenarios such as `personal_low_ops`,
  `backup_cost_sensitive`, `aws_native`, and `google_cloud_native` to existing
  WOM-kit object-storage setup provider ids and returns the next
  `archive object-storage --dry-run` command shape.
- Added `wom-kit/docs/object-storage-recommendations.md` and public
  documentation links.
- Kept the command read-only: it calls no providers, performs no live price
  lookup, checks no bucket availability, creates no buckets, uploads or
  downloads no files, reads no object bytes, creates no presigned URLs, starts
  no OAuth, reads no secret values, writes no files, and echoes no provider
  URLs, local paths, object filenames, tokens, or secret values.

## v0.3.38 - 2026-06-15

- Added read-only connected account overview commands:
  `archive connected-accounts --dry-run`, alias `archive accounts --dry-run`,
  and alias `archive account-status --dry-run`.
- The overview bridges provider bindings, IMAP mailbox source accounts, and the
  ignored local credential-ref inventory into one account/status map.
- Added `wom-kit/docs/connected-accounts.md` and public documentation links.
- Kept the command read-only: it reads metadata only, writes no files, opens no
  vault/keyring/browser store, reads no environment variables or source bytes,
  starts no OAuth, calls no providers, opens no IMAP connection, reads no mail,
  and echoes no exact credential refs, local paths, usernames, emails, tokens,
  provider URLs, or secret values.

## v0.3.37 - 2026-06-15

- Added read-only beginner setup manual commands:
  `archive beginner-setup-manual --dry-run`, alias
  `archive first-use-setup-manual --dry-run`, and alias
  `archive setup-manual --dry-run`.
- The manual bridges existing credential and derived-text setup surfaces by
  explaining first vault setup, safe non-secret labels, KeePassXC-style naming,
  derived-text tool readiness, private `--tool-hints` files, and the next
  dry-run commands to execute.
- Added `wom-kit/docs/beginner-setup-manual.md` and public documentation links.
- Kept the manual read-only: it opens no vault, reads no keyring or environment,
  installs no tools, executes no tools, reads no source bytes, writes no files,
  runs no OCR/parsers/ASR/provider calls, and echoes no local paths, tool hint
  paths, usernames, emails, tokens, provider URLs, or secret values.

## v0.3.36 - 2026-06-15

- Added `--tool-hints <json>` to read-only derived-text doctor commands:
  `archive derive-text doctor --tool-hints <json> --dry-run` and
  `archive derive-text-doctor --tool-hints <json> --dry-run`.
- Tool hints let a local user provide executable path hints for PATH-missing
  extractors such as `soffice`, `libreoffice`, `tesseract`, and `hwp5txt`
  without echoing those paths in JSON or text output.
- Fixed the doctor readiness summary so a tool with multiple executable probes,
  such as LibreOffice via `soffice` or `libreoffice`, is not listed as missing
  when any accepted probe is available.
- Kept the doctor read-only: it only checks local path existence for user-supplied
  hints, installs nothing, executes nothing, reads no source bytes, writes
  nothing, and emits no tool paths, import paths, local absolute paths, provider
  URLs, source bodies, usernames, or secret values.

## v0.3.35 - 2026-06-15

- Added read-only derived-text toolchain doctor commands:
  `archive derive-text doctor --dry-run` and
  `archive derive-text-doctor --dry-run`.
- The doctor checks boolean readiness for Python module probes (`docx`,
  `openpyxl`, `pptx`, `fitz`) and executable probes (`soffice`,
  `libreoffice`, `tesseract`, `hwp5txt`) without echoing executable paths,
  import paths, local absolute paths, source filenames, provider URLs, source
  bodies, usernames, or secret values.
- Added family readiness output for plain text/markup, OOXML Word,
  spreadsheets, presentations, legacy Office, HWP/HWPX, PDF, image scan, and
  audio routes.
- Kept the doctor read-only: it installs nothing, reads no source bytes, runs
  no OCR/parsers/ASR/vision calls, calls no providers, writes no derived text,
  writes no receipts, drafts no zets, and mints nothing.

## v0.3.34 - 2026-06-15

- Added read-only derived-text coverage gate commands:
  `archive derive-text coverage --dry-run` and
  `archive derive-text-coverage --dry-run`.
- Added read-only derived-text toolchain recommendation commands:
  `archive derive-text toolchain --extension <ext> --dry-run` and
  `archive derive-text-toolchain --extension <ext> --dry-run`.
- Added read-only derived-text agent operating contract commands:
  `archive derive-text agent-contract --dry-run` and
  `archive derive-text-agent-contract --dry-run`.
- The coverage gate compares `objects/manifests/files.jsonl` with
  `objects/manifests/derived-text.jsonl`, classifies textual candidates by
  extension/MIME, flags `missing_derived_text` and
  `needs_password_or_encrypted`, and blocks completion claims while uncovered
  textual objets remain.
- The toolchain recommendation surface covers PDF, Office OOXML, legacy Office,
  HWP/HWPX, image, audio, and plain-text/markup families without running OCR,
  parsers, ASR, LLM vision, or provider APIs.
- Kept the release read-only and privacy-preserving: it reads no source bytes,
  echoes no source filenames, local absolute paths, provider URLs, or source
  bodies, writes no derived text or receipts, drafts no zets, and mints
  nothing.

## v0.3.33 - 2026-06-15

- Added CLI-only `archive credential-keepassxc-write --approve` for the first
  minimal live KeePassXC credential write adapter.
- Reused approval receipt verification and `credential_policy_check` before
  execution, and required one scoped `approve_once` receipt for each write.
- Invoked only `keepassxc-cli add --password-prompt` in approved local CLI
  mode, so the database unlock secret and new entry password stay in the local
  terminal/KeePassXC CLI prompt instead of argv, stdin, chat, JSON output, or
  receipts.
- Added non-secret execution receipts under
  `receipts/credentials/keepassxc-writes/` and blocked replay with the same
  approval receipt once a write execution receipt exists.
- Kept MCP preview-only: no live KeePassXC write tool is exposed through MCP.
- Added `wom-kit/docs/credential-keepassxc-write.md` plus CLI/docs coverage
  for verified receipts, database-path non-echo, secret non-echo, replay
  blocking, and the CLI-only execution boundary.

## v0.3.32 - 2026-06-15

- Added read-only CLI `archive credential-keepassxc-command-plan --dry-run`
  and MCP `credential_keepassxc_command_plan` for previewing a safe
  KeePassXC CLI add-command shape after approval receipt verification.
- Added CLI aliases `archive keepassxc-command-plan --dry-run` and
  `archive credential-keepassxc-write-plan --dry-run`.
- Required `--approval-receipt <path>` and re-used `credential_policy_check`
  so the plan is blocked unless the written approval receipt verifies for the
  same archive, credential, action, store, consumer, and `approve_once`
  decision.
- Kept the release non-executing and non-secret: it runs no `keepassxc-cli`,
  opens no KeePassXC vaults, stores no `.kdbx` paths, reads no database
  passwords, reads no plaintext files, pipes no secrets to stdin, places no
  secret values in argv, writes no vault entries, and keeps
  `live_execution_allowed_now` false.
- Added `wom-kit/docs/credential-keepassxc-command-plan.md` plus CLI/MCP/docs
  coverage for receipt verification, dry-run-only behavior, allowed-root
  enforcement, no-write behavior, and privacy boundaries.

## v0.3.31 - 2026-06-15

- Added local CLI approval receipt writing through
  `archive credential-access-approval --approve --reviewed-by <actor>` for
  recording one non-secret credential access approval receipt under
  `receipts/credentials/access-approvals/`.
- Kept `archive credential-access-approval-plan --dry-run` and MCP
  `credential_access_approval_plan` as preview-only surfaces; MCP still cannot
  write approval receipts.
- Updated `archive credential-policy-check --dry-run` and MCP
  `credential_policy_check` so they can verify an archive-relative approval
  receipt with `--approval-receipt <path>` before any future adapter execution.
- Preserved secret boundaries: the writer records no secret values, no exact
  credential refs, no usernames, no email addresses, no local paths, no provider
  URLs, and it opens no vault, keyring, browser store, environment variable,
  plaintext file, provider API, OAuth flow, or live adapter.
- Added CLI/docs coverage for receipt preview, receipt write, duplicate/no-mode
  blockers, policy receipt verification, no-write MCP behavior, and privacy
  boundaries.

## v0.3.30 - 2026-06-15

- Added read-only CLI `archive credential-policy-check --dry-run` and MCP
  `credential_policy_check` for evaluating a proposed credential use request
  before any future live adapter can run.
- Added CLI aliases `archive credential-access-policy-check --dry-run` and
  `archive secret-policy-check --dry-run`.
- Added policy results `ready_after_approval_receipt`, `needs_human_review`,
  `denied_by_human_decision`, `denied_by_policy`, and `blocked`.
- Added a concrete policy object preview for approval decision, store kind,
  adapter kind, adapter operation, action kind, and non-echo rules.
- Kept the checker non-mutating and non-executing: it writes no approval
  receipts, executes no live adapters, opens no vaults, keyrings, browser
  stores, environment variables, plaintext secret files, provider APIs, or
  OAuth flows, and even a passing result keeps `live_execution_allowed_now`
  false.
- Added `wom-kit/docs/credential-policy-check.md` plus CLI/MCP/docs tests for
  policy pass, policy denial, dry-run-only behavior, allowed-root enforcement,
  no-write behavior, and privacy boundaries.

## v0.3.29 - 2026-06-15

- Added read-only CLI `archive credential-plaintext-migration-plan --dry-run`
  and MCP `credential_plaintext_migration_plan` for planning how a
  human-selected plaintext note could later be migrated into a real
  vault/keyring/store without returning secrets to AI.
- Added CLI aliases `archive secret-migration-plan --dry-run` and
  `archive credential-import-plan --dry-run`.
- Required a safe `--source-label` instead of accepting or echoing local file
  paths, and linked target store routing to the v0.3.28 vault onboarding layer.
- Kept the release strictly non-mutating and non-secret: it reads no plaintext
  files, prints no plaintext file paths, hashes no plaintext bytes, detects no
  secret values, returns no candidate secret values to AI, opens no vaults,
  keyrings, browser stores, environment variables, provider APIs, OAuth flows,
  or adapter runners, deletes no plaintext notes, and writes no files.
- Added `wom-kit/docs/credential-plaintext-migration-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, pathless source
  labeling, no-write behavior, and privacy boundaries.

## v0.3.28 - 2026-06-15

- Added read-only CLI `archive credential-vault-onboarding-plan --dry-run`
  and MCP `credential_vault_onboarding_plan` for planning how a human-selected
  external vault, password manager, platform password manager, OS keyring,
  developer secret manager, or environment injection surface should fit WOM.
- Added CLI aliases `archive credential-vault-onboarding --dry-run` and
  `archive secret-vault-onboarding-plan --dry-run`.
- Added safe store-id routing for `recommended`, `keepassxc`, `bitwarden`,
  `1password`, `browser_or_platform_password_manager`, `os_keyring`,
  `developer_secret_manager`, and `environment_variable`.
- Linked the onboarding layer to credential refs, inventory, broker planning,
  approval previews, adapter readiness, adapter manifests, and adapter audit
  previews without opening or reading any real vault/keyring/store.
- Kept the release strictly non-mutating and non-secret: it opens no password
  managers, browser stores, OS keyrings, environment variables, plaintext
  secret files, provider APIs, OAuth flows, or adapter runners; writes no
  files; and includes no secret values, exact credential refs, usernames, email
  addresses, tokens, local paths, provider URLs, passwords, or API keys.
- Added `wom-kit/docs/credential-vault-onboarding-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  planner-chain linkage, and privacy boundaries.

## v0.3.27 - 2026-06-15

- Added read-only CLI `archive credential-adapter-audit-plan --dry-run` and
  MCP `credential_adapter_audit_plan` for previewing a non-secret future
  credential adapter audit receipt.
- Added CLI aliases `archive credential-adapter-audit --dry-run` and
  `archive secret-adapter-audit-plan --dry-run`.
- Defined the future audit boundary after credential refs, adapter manifests,
  readiness checks, human approval receipts, and local adapter operations.
- Kept the audit layer non-mutating and non-executing: it writes no receipts or
  manifests, executes no live adapters, opens no vaults, keyrings, browser
  stores, environment variables, plaintext secret files, provider APIs, or
  approval writers, and includes no secret values, exact credential refs,
  usernames, email addresses, tokens, local paths, provider URLs, passwords, or
  API keys.
- Added `wom-kit/docs/credential-adapter-audit-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  non-execution, and privacy boundaries.

## v0.3.26 - 2026-06-15

- Added read-only CLI `archive credential-adapter-manifest-plan --dry-run`
  and MCP `credential_adapter_manifest_plan` for previewing a non-secret
  future credential adapter manifest.
- Added CLI aliases `archive credential-adapter-manifest --dry-run` and
  `archive secret-adapter-manifest-plan --dry-run`.
- Added JSON schema `wom-kit/schemas/credential-adapter-manifest.schema.json`
  and schema validation in the manifest preview output.
- Kept the manifest layer non-mutating and non-secret: it writes no manifests,
  opens no vaults, keyrings, browser stores, environment variables, plaintext
  secret files, provider APIs, approval receipt writers, or audit receipt
  writers, and it includes no secret values, exact credential refs, local
  absolute paths, provider account values, provider URLs, passwords, tokens, or
  API keys.
- Added `wom-kit/docs/credential-adapter-manifest-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, schema validity,
  no-write behavior, and privacy boundaries.

## v0.3.25 - 2026-06-15

- Added read-only CLI `archive credential-adapter-readiness-plan --dry-run`
  and MCP `credential_adapter_readiness_plan` for previewing the contract a
  future local credential adapter must satisfy before using a password manager,
  OS keyring, browser/platform password manager, developer secret manager,
  environment injection surface, or future wallet.
- Added CLI aliases `archive credential-adapter-plan --dry-run` and
  `archive secret-adapter-readiness --dry-run`.
- Added adapter readiness coverage for resolving a credential for one approved
  action, writing a new secret, rotating a secret, plaintext secret migration,
  browser login fill, and metadata-only listing.
- Kept the release strictly non-mutating: it opens no vaults, keyrings, browser
  stores, environment variables, plaintext secret files, provider APIs,
  approval receipt writers, or audit receipt writers, and it never echoes exact
  credential refs or secret values.
- Added `wom-kit/docs/credential-adapter-readiness-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  exact-ref non-echo, and raw-secret redaction.

## v0.3.24 - 2026-06-15

- Added read-only CLI `archive credential-access-approval-plan --dry-run` and
  MCP `credential_access_approval_plan` for previewing a future
  human-reviewed credential access approval receipt.
- Added preview decisions `needs_review`, `approve_once`, and `deny`; even
  `approve_once` remains a non-mutating preview and grants no live access in
  this release.
- Kept exact credential ref values and secret values out of the receipt preview;
  the preview reports only safe metadata such as credential id, kind, provider,
  purpose, ref store, ref prefix, action kind, store kind, and consumer label.
- Added `wom-kit/docs/credential-access-approval-plan.md` plus CLI/MCP/docs
  tests for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  exact-ref non-echo, and raw-secret redaction.
- Fixed the secret scanner so declared credential refs such as
  `secret:keepassxc-personal-mail` and `keyring:openai-api-key` do not trigger
  `secret_value_detected` when recorded in the local credential-ref catalog.
  Raw secret-like values are still detected.

## v0.3.23 - 2026-06-15

- Added read-only CLI `archive credential-access-broker-plan --dry-run` and
  MCP `credential_access_broker_plan` for planning a future local credential
  access broker without retrieving secrets.
- Defined broker action kinds for mail source reads, model API calls, OCR API
  calls, object-storage requests, CLI token auth, browser login fill, and
  plaintext secret migration planning.
- Kept exact credential ref values and raw secret values out of structured
  output; the planner reports only safe metadata such as credential id, kind,
  provider, purpose, ref store, and ref prefix.
- Documented the broker boundary for future AI use: AI requests a credential
  capability by purpose/ref, while a local approved adapter uses the secret for
  the approved action without echoing it into chat, zets, receipts, logs,
  prompts, or public docs.
- Added `wom-kit/docs/credential-access-broker-plan.md` plus CLI/MCP/docs tests
  for dry-run-only behavior, allowed-root enforcement, no-write behavior,
  exact-ref non-echo, and raw-secret redaction.

## v0.3.22 - 2026-06-14

- Added read-only CLI `archive credential-store-recommendation --dry-run` and
  MCP `credential_store_recommendation` for scenario-based recommendations
  across KeePassXC-style offline vaults, Bitwarden/1Password-style syncing
  managers, browser/platform password managers, OS keyrings, developer secret
  managers, automation env refs, local app adapters, and institutional mail.
- Defined WOM compatibility rules for `secret:`, `keyring:`, `env:`, and
  future `wallet:` refs in the context of human password vault choice.
- Documented the future credential access broker boundary: AI should request a
  credential capability by purpose/ref, while a local approved adapter uses the
  secret without echoing it into chat, zets, receipts, logs, prompts, or public
  docs.
- Added `wom-kit/docs/credential-store-recommendations.md` plus CLI/MCP/docs
  tests for read-only behavior, scenario coverage, allowed-root enforcement,
  no-write behavior, and non-echo guarantees.

## v0.3.21 - 2026-06-14

- Added read-only CLI `archive credential-ref-inventory --dry-run` and MCP
  `credential_ref_inventory` for listing known credential refs without echoing
  exact ref values or secrets.
- Added ignored local catalog guidance for
  `profiles/local/credential-refs.local.yml` so a human can remember credential
  ids, kinds, providers, purposes, and store prefixes while keeping passwords,
  tokens, API keys, and account values outside WOM archive records.
- Improved IMAP mailbox planning feedback when a credential-store ref such as
  `keyring:*` is accidentally passed as `account_ref`; `account_ref` is now
  explained as a non-secret account label, while `keyring:`, `env:`, `secret:`,
  and `wallet:` refs belong in username, app-password, OAuth-token, or generic
  credential fields.
- Added `wom-kit/docs/credential-ref-inventory-and-onboarding.md` plus
  CLI/MCP/docs tests for dry-run-only behavior, allowed-root enforcement,
  no-write behavior, and non-echo guarantees.

## v0.3.20 - 2026-06-14

- Added read-only CLI `archive credential-ref-plan --dry-run` and MCP
  `credential_ref_plan` for planning mail, OpenAI API, OCR API, provider,
  object-storage, and backup credential references without storing secrets.
- Defined safe credential ref prefixes `env:`, `keyring:`, `secret:`, and
  `wallet:` so archive records can point to local secret stores without
  containing the secret value.
- Kept the boundary conservative: the plan writes nothing, reads no environment
  variables, opens no OS keyring, starts no OAuth, calls no providers, calls no
  OpenAI or paid OCR APIs, and blanks invalid raw secret inputs before returning
  structured output.
- Added `wom-kit/docs/credential-store-contract.md` plus CLI/MCP/docs tests for
  dry-run-only behavior, allowed-root enforcement, raw-secret redaction, and
  public documentation coverage.

## v0.3.19 - 2026-06-14

- Added read-only CLI `archive imap-mailbox-plan --dry-run` and MCP
  `imap_mailbox_plan` for provider-neutral IMAP mailbox source planning across
  Gmail, Naver, and generic IMAP hosts.
- Added `imap_mailbox` as a registered source type while keeping live IMAP
  scans fail-closed in this release; `scan-source` now directs operators back
  to the planning step for safe credential refs.
- Kept the mail boundary conservative: the plan writes nothing, connects to no
  server, attempts no login, reads no headers, bodies, or attachments, sends no
  mail, deletes no mail, changes no flags, and accepts credential refs instead
  of raw usernames, emails, passwords, or tokens.
- Added `wom-kit/docs/imap-mailbox-source.md` plus CLI/MCP/source-map tests for
  dry-run-only behavior, registration shape, scan blocking, and private-value
  redaction.
- Tightened zettel path guidance so absolute `--path` inputs point users back to
  archive-relative `inbox/` or `zettels/` paths and `--zettel-id`.

## v0.3.18 - 2026-06-14

- Added read-only CLI `archive zettel-objet-links --path <zet.md>|--zettel-id
  <id> --dry-run` and MCP `zettel_objet_links` for zettel-level objet link
  previews.
- The preview scans one non-redacted zettel for `sha256:<hex>` and
  `objet:sha256:<hex>` refs, then reuses `resolve-objet-ref` to return safe
  local archive-relative candidates and external store labels.
- Kept the preview conservative: it writes nothing, echoes no zettel body text
  or frontmatter values, echoes no absolute local paths or provider URLs, reads
  no object bytes, calls no providers, creates no presigned URLs, and blocks
  redacted zettels.
- Added `wom-kit/docs/zettel-objet-links.md` and tests for CLI/MCP behavior,
  dry-run-only enforcement, and privacy boundaries.

## v0.3.17 - 2026-06-14

- Added read-only CLI `archive resolve-objet-ref --object-id sha256:<hex>
  --dry-run` and MCP `resolve_objet_ref` for the first reading-side objet
  reference resolver.
- The resolver reads `objects/manifests/files.jsonl` and reports safe local
  archive-relative candidates plus external store labels for one manifest
  `object_id`.
- Kept the resolver non-mutating and conservative: it writes nothing, echoes no
  absolute local paths or provider URLs, reads no object bytes, re-hashes no
  object bytes, calls no providers, creates no presigned URLs, downloads
  nothing, uploads nothing, and does not decide deletion safety.
- Added `wom-kit/docs/objet-ref-resolution.md` and documentation tests for the
  resolver boundary.

## v0.3.16 - 2026-06-14

- Added `wom-kit/docs/notion-page-snapshot-model.md` to define Notion
  `recordMap` / `blocks` JSON as provider page snapshot source objets, separate
  from extracted derived text and human-authored zets.
- Clarified `store_ref` semantics for prehashed external objet ledgers:
  `object_id` identifies the bytes, `store_kind` names the storage family, and
  `store_ref` is only a reviewed safe external-store label, not a raw path,
  URL, token, or proof of byte availability.
- Linked the model from the Notion three-store example, source objet storage
  policy, text provenance hierarchy, README, public documentation map, and
  capability matrix without adding Notion API calls, provider sync, extraction
  helpers, page-snapshot schemas, or byte materialization adapters.

## v0.3.15 - 2026-06-14

- Added approval-gated CLI `archive project-intake-unpack-choice
  --dry-run|--approve` and MCP `project_intake_unpack_choice` so a human can
  record one reviewed `item-0001` style unpack choice after the queue step.
- The new choice receipt stores the opaque item ref, intended action, completed
  project-intake receipt link, and public-safe queue digest without exposing
  staged entry names, local paths, file bodies, or choice notes in command
  output.
- Kept source-intake, capture, drafting, minting, provider sync, and cleanup as
  separate gates after the human choice receipt.

## v0.3.14 - 2026-06-14

- Added read-only CLI `archive project-intake-unpack-queue --dry-run` and MCP
  `project_intake_unpack_queue` for the first practical "unpacking boxes"
  layer in the human-guided project intake flow.
- The unpack queue returns opaque `item-0001` style refs plus coarse
  kind/extension/size hints so an AI can ask which staged item the human wants
  to unpack next without exposing entry names, local paths, file bodies, or
  decision values.
- Documented the queue between project-intake receipt review and per-item
  `project-intake-item-plan`, while keeping source-intake, capture, drafting,
  minting, provider sync, and cleanup as separate approval gates.

## v0.3.13 - 2026-06-14

- Strengthened `wom-kit/docs/human-artifact-store-contract.md` as the shared
  contract for user-selected surfaces such as WordPress, Joplin, Notion,
  Obsidian, and generic Markdown/workspace apps.
- Added a role matrix and adapter questions that separate raw data stores,
  human-readable artifacts, projection surfaces, and system/AI records so app
  names do not become implicit WOM architecture.
- Added a capture-action shape for future note/report/handoff workflows:
  explicit human capture first, then a separate local WOM receipt/source-map
  record outside the app.
- Linked the contract from README and the public documentation maps, and pointed
  ZET surface prototypes back to the shared contract before future app-specific
  adapters write anything.

## v0.3.12 - 2026-06-14

- Updated `wom-kit/docs/project-intake-cookbook.md` with a bulk raw-preservation
  to selective promotion bridge for large already-hashed migrations:
  `prehashed-objet-ledger` registers raw object manifests first, while the
  project-intake cookbook remains the human-guided path for selected drafts and
  zets.
- Clarified that `archive-objets/` is the recommended local staging root in the
  cookbook rehearsal, not a requirement to move an existing external
  content-addressed store.
- Added copy/paste-friendly `$sourceIntakeReceipt` and `$selectionJson`
  placeholders for the source-intake-record to capture-selection handoff.

## v0.3.11 - 2026-06-14

- Extended `archive prehashed-objet-ledger` so CLI `--ledger` may be repeated,
  allowing retrieval, deep, and workspace download ledgers to be deduped across
  one dry-run/approval pass.
- Added skipped-row accounting for prehashed ledger rows with null or empty
  `sha256`, so aid-dedup style rows can be ignored without blocking approval;
  malformed non-empty sha values remain invalid.

## v0.3.10 - 2026-06-14

- Added `wom-kit/docs/project-intake-cookbook.md`, a fake-archive rehearsal
  walkthrough for the manual project-intake spine from session planning through
  answer receipt, source-intake, capture selection, capture, draft/mint gates,
  and cleanup verification.
- Strengthened the project-intake-to-objet-capture roundtrip regression so it
  now creates the project-intake receipt through
  `archive project-intake-record-answer` semantics before passing that receipt
  into source-intake and capture context checks.
- Updated README release-baseline bookkeeping to v0.3.10, including the Korean
  README's release tag list.

## v0.3.9 - 2026-06-14

- Added approval-gated CLI `archive project-intake-record-answer --dry-run|--approve`
  to append exactly one human-reviewed project-intake answer to a new or
  existing decisions receipt without echoing current or previous answer values,
  running source intake, capturing objets, drafting, minting, calling providers,
  or cleaning staged folders.

## v0.3.8 - 2026-06-14

- Added read-only CLI `archive project-intake-staging-guide --dry-run` and MCP
  `project_intake_staging_guide` to show the recommended local objet-store
  intake path for one project slug without creating folders, moving files,
  uploading, capturing, drafting, minting, or cleaning.
- Added read-only CLI `archive project-intake-session-guide --dry-run` and MCP
  `project_intake_session_guide` to show the next safe human-guided intake step
  from a project slug, staged folder, or existing decisions receipt without
  echoing decision values, reading file bodies, writing decisions, capturing,
  drafting, minting, uploading, cleaning, or authorizing automatic execution.
- Added read-only CLI `archive project-intake-next-question --dry-run` and MCP
  `project_intake_next_question` so AI-assisted intake can ask one
  human-review question at a time without echoing decision values, writing
  decisions, capturing, drafting, minting, uploading, or cleaning.
- Added read-only CLI `archive project-intake-decision-template --dry-run` and
  MCP `project_intake_decision_template` to produce the next answer's decision
  JSON shape without filling answer values, echoing previous answers, approving
  receipts, or writing files.
- Added read-only CLI `archive project-intake-item-plan --dry-run` and MCP
  `project_intake_item_plan` to preview the next source-intake dry-run route for
  one human-selected file while redacting local paths and avoiding capture,
  drafting, minting, uploads, cleanup, or selection-manifest generation.
- Added approval-gated CLI `archive source-intake-record --dry-run|--approve`
  to validate a reviewed `source-intake --dry-run` JSON file and preserve the
  redacted plan under `receipts/sources/` for later capture evidence without
  reading file bodies, calculating content hashes, or calling providers.
- Added approval-gated CLI `archive objet-capture-selection
  --dry-run|--approve` to build a reviewed `objet-capture --selection`
  manifest from one staged file and one recorded source-intake plan. It hashes
  the selected staged file to bind `approved_object_id`, writes only the
  selection manifest on approve, and does not capture bytes, append object
  manifest records, draft, mint, upload, or clean staged originals.
- Added CLI `archive prehashed-objet-ledger --dry-run|--approve` for
  already-hashed external content-addressed ledgers, including Notion
  source-export ledgers. Dry-run previews registration without echoing row
  values; approved mode appends external manifest records and writes a receipt
  without reading blob bytes, copying objects, uploading, drafting, minting, or
  claiming that `objet-capture` can skip byte verification today. MCP remains a
  read-only `prehashed_objet_ledger_preview`.
- Added read-only CLI `archive zet-surface-prototype --dry-run` and MCP
  `zet_surface_prototype_plan` for user-selected ZET surface prototypes across
  WordPress, Joplin, Notion, and Obsidian. The preview returns surface-specific
  settings, risks, and future adapter steps without provider calls, token
  prompts, note writes, vault writes, post publishing, projection receipts,
  minting, cleanup, or ZET transport.

## v0.3.7 - 2026-06-13

- Added optional `archive objet-capture --project-intake-receipt <receipt>` context validation, and matching selection-manifest support via `project_intake_receipt_path`, so reviewed project-intake decisions can gate capture planning before staged bytes are read; added fake-archive roundtrip regressions for plan -> decisions -> status -> source-intake -> create-draft/mint metadata and plan -> decisions -> status -> source-intake -> objet-capture.
- Added read-only CLI/MCP human artifact store planning for WordPress, Joplin, Notion, Obsidian, Evernote, generic Markdown, and generic workspace surfaces, keeping raw data, human-facing artifacts, and system/AI artifacts separate without provider calls, note writes, publishing, uploads, minting, cleanup, or ZET transport.
- Added read-only MCP `project_intake_plan` and `project_intake_status`, and added `project_intake_receipt` support to MCP `source_intake_plan`, so AI runtimes can follow the human-guided intake question loop without project-intake write/apply tools.
- Added read-only CLI `archive provider-status --dry-run` and MCP `provider_setup_status` to compare setup-managed GitHub/object-storage provider metadata with local provider setup receipts without provider calls, uploads, sync, pushes, or file writes.
- Added per-item `item_status` values to derived-text batch dry-run/apply output so large JSONL captures can distinguish ready, skipped, blocked, and written rows at a glance.
- Added `project-intake-status` `next_review_prompts` for missing checklist ids so AI-assisted intake sessions can ask the next human-review questions without inventing or echoing answer values.
- Clarified the project-intake migration spine from project planning through source-intake, objet-capture, derived-text registration, drafting, minting, and cleanup verification; documented the local-only intent behind collaboration/runtime `.gitignore` guardrails.

## v0.3.6 - 2026-06-13

- Added optional `archive source-intake --project-intake-receipt <receipt>` context validation so one-item metadata dry-runs can carry a reviewed project-intake session receipt without echoing answer text or granting automatic execution authority.
- Added `archive project-intake-status --receipt <receipt> --dry-run` to review checklist coverage and receipt integrity without echoing recorded answer text or authorizing automatic execution.
- Added `archive project-intake-decisions --dry-run|--approve --reviewed-by <actor>` to validate and record human-reviewed project intake checklist answers as a local receipt without echoing answer text or running capture/draft/mint/cleanup steps.
- Extended `archive project-intake-plan --dry-run` with a human review checklist, classification labels, and a draft decision-record template while preserving the no-names/no-bodies privacy boundary.

## v0.3.5 - 2026-06-13

- Added `archive derive-text capture --from-manifest <jsonl>` for dry-run/approved batch registration of already extracted UTF-8 derived text.
- Batch derived-text manifests accept one JSON object per line with `source_object_id`, `text_file`, `derivation_kind`, `tool_name`, `tool_version`, and `review_status`; relative `text_file` paths resolve from the manifest location.
- Added `archive repair-gitignore <archive-root> --dry-run|--approve --reviewed-by <actor>` to append missing WOM-kit safe `.gitignore` patterns without rewriting existing entries.
- Removed private dogfood archive identifiers from public guardrail code and docs, keeping generic live-archive and `*-objets` protections.

## v0.3.4 - 2026-06-13

- Added `archive derive-text capture` for dry-run/approved registration of externally extracted text as provenance-aware derived text records.
- Added `objects/manifests/derived-text.jsonl`, local derived text body storage under `objects/derived-text/sha256/`, approval receipts under `receipts/derived-text-capture/`, doctor/schema validation, and search index ingestion for derived text.
- Standardized the first implemented derived-text vocabulary to `parser`, `ocr`, `asr`, `llm_vision` and `unreviewed`, `human_corrected`.

## v0.3.3 - 2026-06-13

Compatible fixes from v0.3.2 upgrade field feedback:

- CLI output no longer crashes on console encodings that cannot represent a character (e.g. emoji on a Korean Windows cp949 console); unencodable characters are replaced,
- doctor now warns (`zettel_frontmatter_unquoted_timestamp`) when frontmatter contains an unquoted YAML timestamp, with the field path and a quoting hint; `doctor --strict` and `validate` treat it as failing,
- `validate` accepts `--strict` for parity with doctor (validate already fails on warnings unless `--allow-warnings`),
- `staged-cleanup-check` now exits `0` only when the report is both `ok` and `safe_to_cleanup`; unsafe cleanup reports exit `1` while still returning the JSON report,
- `view-zets` now indexes list-valued facets as repeated scalar facet rows, so saved views and ad-hoc scalar filters can match zettels tagged with lists,
- `view-zets` now blocks list-valued filter inputs instead of silently broadening or guessing,
- objet-capture source-intake plan SHA binding now has regression coverage against a real `source-intake --dry-run` producer plan through dry-run and approve,
- added `wom-kit/docs/validation-surface.md` documenting what doctor, validate, preflight, and staged cleanup checks each guarantee.

Compatibility:

- the v0.3.1 frontmatter schema is unchanged,
- no archive migration is required for v0.3.2 users,
- rebuild the disposable search index with `archive index <archive-root>` to pick up list-valued facet indexing for `view-zets`,
- cleanup remains manual; `staged-cleanup-check` never deletes files.

## v0.3.2 - 2026-06-11

Frontmatter migration, redaction hardening, and the local capture spine.

Added:

- CLI `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run --format json`,
- approve-gated `archive migrate <archive-root> --target frontmatter-v0.3 --approve --format json`,
- lossless handling for clean object-shaped `provenance.source` values by relocating them to `source_refs`,
- manual-review blockers for ambiguous or unsafe source values,
- doctor compatibility output and migration hints for legacy frontmatter failures,
- v0.3 zettel-rules guidance for required `provenance` and `visibility` subfields,
- approval-gated CLI `archive objet-capture <archive-root> --selection <manifest> --dry-run|--approve --reviewed-by <actor>` capturing approved staged files into the local content-addressed objet store (`objects/sha256/<2>/<64>`) with manifest records and always-written capture receipts,
- report-only CLI `archive staged-cleanup-check <archive-root> --staged <folder> --dry-run` verifying every staged file is preserved or explicitly deferred before any manual cleanup; fails closed on unenumerable trees and never deletes,
- read-only CLI `archive related-zets <archive-root> --zettel-id <id>` with bidirectional typed-edge traversal (backlinks), depth 1-3, cycle safety, and edge-type filters,
- read-only CLI `archive view-zets <archive-root> --view-id <id> | --facet key=value ...` executing saved-view facet filters from `views/*.yml`,
- typed edges and zettel facets in the disposable search index,
- report-only artifact hygiene checker and six-class file-lifecycle baseline doc,
- an end-to-end test proving the full loop: stage -> capture -> draft -> mint -> cleanup-safe.

Privacy:

- redacted-zettel content suppression is now enforced across search, the on-disk index, `list-zettels`, `read-zettel`, block-header previews, projection previews, related-zets, and view-zets, with regression tests per surface.

Compatibility:

- the v0.3.1 frontmatter schema is unchanged,
- `--dry-run` writes no files anywhere; approve paths rewrite only reviewed targets,
- archives authored from older v0.2-draft rules should run the migration dry-run before strict v0.3 validation,
- the objet-capture write path refuses archives without an explicit sandbox marker,
- run `archive index` once to pick up edges and facets,
- private/live archives, provider sync, staged-original deletion, MCP write tools, ZET transport, and schema redesign are not part of this release.

## v0.3.1 - 2026-06-04

Shared update route preview.

Added:

- CLI `archive shared-update-route-preview <archive-root> --record <path> --dry-run --format json`,
- service `shared_update_route_preview`,
- read-only route pointers for `delegate`, `attest`, `anchor`, and `none`,
- explicit `related_shared_update_review_required_flags` when the route points toward `shared-update-attestation-review`,
- hardening so free-form or hostile proposed-action metadata is not echoed as a route,
- public documentation, release note, and work log for the v0.3.1 route-preview boundary.

Compatibility:

- the route-preview command itself requires no provider, transport, or shared-update record migration,
- archives authored from older v0.2-draft frontmatter rules may still need `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run` before strict v0.3 validation,
- the command is dry-run only and writes no files,
- the command reuses `zet_shared_update_record_review_preview` before returning a route pointer,
- MCP exposes no shared-update route write/apply/approve tool for this boundary,
- body text, local absolute paths, provider URLs, tokens, secrets, and unsafe free-form route metadata are not echoed,
- the route preview does not create real trust, import, acceptance, attestation, signature, anchor, public proof, provider sync, feed update, projection, ZET transport, queue/worker, wallet/key custody, payment, staking, consensus, blockchain, token, model training, backpropagation, or full-auto behavior.

## v0.3.0 - 2026-06-03

Shared update attestation/review write boundary.

Added:

- CLI `archive shared-update-attestation-review <archive-root> --record <path> --decision <attest|needs_more_review|reject> --reviewed-by <actor> --approve --format json`,
- service `record_shared_update_attestation_review`,
- deterministic local review record and receipt paths under `shared-updates/attestation-reviews/` and `receipts/shared-updates/`,
- replay/overwrite refusal for the same reviewed shared update record,
- rollback if the receipt write fails after the review record write,
- public documentation, release note, and work log for the v0.3.0 first write boundary.

Compatibility:

- the shared-update attestation/review command itself requires no provider, transport, or shared-update record migration,
- archives authored from older v0.2-draft frontmatter rules may still need `archive migrate <archive-root> --target frontmatter-v0.3 --dry-run` before strict v0.3 validation,
- MCP exposes no write/apply sibling tool for this boundary,
- the write reuses `zet_shared_update_record_review_preview` before recording anything,
- body text, local absolute paths, provider URLs, tokens, secrets, and unsafe values are not echoed or persisted,
- `attest` records only a local human review decision and does not create real trust, import, acceptance, signature, anchor, public proof, provider sync, feed update, projection, ZET transport, queue/worker, wallet/key custody, payment, staking, consensus, blockchain, token, model training, backpropagation, or full-auto behavior.

## v0.2.60 - 2026-06-02

v0.2.x freeze and v0.3.0 entry boundary.

Added:

- public [v0.2.x freeze and v0.3.0 entry boundary](wom-kit/docs/v02x-freeze-v03-entry-boundary.md),
- release note and public-safe work log for the v0.2.60 checkpoint batch,
- capability matrix updates for the v0.2.x freeze, public proof boundary, DID-compatible identity research boundary, and proposed first v0.3.0 write boundary,
- focused documentation tests for the freeze/boundary document.

Compatibility:

- no private archive migration is required,
- no product CLI command was added,
- no MCP tool was added,
- no archive service behavior changed,
- no schema changed,
- v0.3.0 is proposed to start with one narrow receiver-side, replay-gated, human-approved, local-first, body-safe write,
- no real ZET transport, key-sharing registry, radio-frequency access creation, mirroring delivery, feed update, trust/import/acceptance/anchor mutation, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, queue, worker, DID registry, wallet/key custody, public proof anchoring, blockchain, token, system token, validator governance, payment, staking, consensus, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.59 - 2026-06-02

ZET transport threat model and would-transport plan.

Added:

- CLI `archive zet-transport-plan <archive-root> --record <path> --method <key-sharing|radio-frequency|mirroring> --dry-run --format json`,
- MCP `zet_transport_would_plan`,
- read-only service `zet_transport_would_plan`,
- method-specific planning-only risk/control previews for `key-sharing`, `radio-frequency`, and `mirroring`,
- public documentation, release note, and work log for the v0.2.59 planning batch.

Compatibility:

- no private archive migration is required,
- the new CLI/MCP path is dry-run only and writes no files,
- the planner reuses the v0.2.56 single-record review preview policy before producing any plan,
- body text, local absolute paths, provider URLs, tokens, secrets, and unsafe values are not echoed,
- no real ZET transport, key creation, key-sharing registry, radio-frequency access creation, mirroring delivery, shared-update review writes, receiver-side renewal writes, neighbor feed update, recommendation execution, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, queues, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.58 - 2026-06-02

ZET shared update record review index.

Added:

- CLI `archive shared-update-record-review-index <archive-root> --records-dir <path> --dry-run --format json`,
- MCP `zet_shared_update_record_review_index`,
- read-only service indexing for direct-child local shared update record JSON files,
- public documentation, release note, and work log for the v0.2.58 index batch.

Compatibility:

- no private archive migration is required,
- the new CLI/MCP path is dry-run only and writes no files,
- the index reuses the v0.2.56 single-record review preview policy,
- unsafe records remain blocked per record and record body text is never echoed,
- no shared-update review writes, shared-update transport, real ZET transport, neighbor feed update, automatic feed renewal, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.57 - 2026-06-02

Capability matrix and README readability patch.

Added:

- public [WOM-kit Capability Matrix](wom-kit/docs/capability-matrix.md) for implemented, read-only preview, approval-gated write, documented-only, local hygiene, and not-implemented surfaces,
- release note and public-safe work log for the v0.2.57 readability batch,
- focused documentation tests for the capability matrix and README release-tag sequence.

Changed:

- shortened the top-level README status summary and pointed readers to the capability matrix,
- restored the missing `v0.2.55` README release-tag entry,
- recorded a proposed v0.2.x closing plan and a narrow proposed v0.3.0 boundary,
- updated version metadata to `0.2.57`.

Compatibility:

- no private archive migration is required,
- no archive product CLI, MCP, service, provider, transport, trust/import, attestation/signature, anchor, payment, blockchain, token, worker, or full-auto behavior changed.

## v0.2.56 - 2026-06-02

ZET shared update record review preview.

Added:

- CLI `archive shared-update-record-review <archive-root> --record <path> --dry-run --format json`,
- MCP `zet_shared_update_record_review_preview`,
- read-only service validation for local archive-contained shared update record JSON before any receiver-side renewal action,
- release note and public-safe work log for the v0.2.56 preview batch.

Compatibility:

- no private archive migration is required,
- the new CLI/MCP path is dry-run only and writes no files,
- the preview reads only the selected archive-relative JSON record,
- unsafe absolute paths, URL-like record paths, body-included records, token/secret-like values, and true mutation/write/transport/provider/trust flags block,
- no shared-update transport, real ZET transport, neighbor feed update, automatic feed renewal, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.55 - 2026-05-27

ZET shared update record baseline.

Added:

- public documentation for a future receiver-side ZET shared update record,
- sanitized non-executable example JSON for a shared update review preview,
- release note and public-safe work log for the v0.2.55 documentation/example batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the example is body-free and contains placeholder refs only,
- no shared-update transport, real ZET transport, RF access, key-sharing registry, mirroring delivery, neighbor feed update, automatic feed renewal, recommendation execution, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.54 - 2026-05-27

Main branch protection readiness baseline.

Added:

- public documentation for staged future `main` branch protection readiness,
- a recommended path from local release-readiness gate to future GitHub Actions, required status checks, and optional review requirements,
- release note and public-safe work log for the v0.2.54 documentation batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- no GitHub Actions, branch protection, repository settings, or GitHub API behavior changed,
- no files are rewritten automatically,
- no external URLs are fetched,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.53 - 2026-05-27

Release readiness gate patch.

Added:

- local `wom-kit/tools/check_release_readiness.py` gate that runs the existing public release hygiene checkers together,
- unit tests for expected child checker paths, pass/fail behavior, failure output, current-repository pass behavior, and network-free / release-edit-free gate scope,
- documentation, release note, and public-safe work log for the v0.2.53 gate batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the gate runs local subprocess calls to public hygiene checkers only,
- no files are rewritten automatically,
- no external URLs are fetched,
- no GitHub APIs, GitHub Actions, branch protection, product doctor/test commands, providers, private archives, or GitHub Releases are inspected or changed,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.52 - 2026-05-27

Public privacy hygiene checker patch.

Added:

- local `wom-kit/tools/check_public_privacy.py` checker for public release and documentation privacy hygiene,
- unit tests for local user-home paths, token-like strings, private key headers, seed-phrase-like text, private/local endpoint examples, placeholder allowances, current-repository pass behavior, and network-free checker scope,
- documentation, release note, and public-safe work log for the v0.2.52 checker batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the checker reads local Git-known public text files only,
- no files are rewritten automatically,
- no external URLs are fetched,
- no private archives, provider APIs, GitHub Releases, or full-disk locations are inspected or changed,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.51 - 2026-05-27

Korean product-language hygiene checker patch.

Added:

- local `wom-kit/tools/check_korean_product_language.py` checker for public Markdown documentation,
- unit tests for required Korean product-language anchors, risky drift phrases, current-facing spelling variants, messenger thread blockchain claims, WordPress/ZET transport claims, and network-free checker scope,
- documentation, release note, and public-safe work log for the v0.2.51 checker batch.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- the checker reads local Git-known Markdown files only,
- no files are rewritten automatically,
- no code identifiers, CLI commands, JSON fields, schema fields, filenames, or package names are renamed,
- no real ZET transport, RF access, key-sharing registry, mirroring delivery, trust/import/acceptance/anchor, attestation/signature write, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.50 - 2026-05-27

Korean product-language baseline patch.

Added:

- Korean product-language baseline for WOM, zettel-kasten, zet, ZET, objet, lifecycle verbs, block/header/body wording, foreign block safety terms, sharing forms/methods, surface/action terms, SNS-type ZET actions, and messenger-type ZET threads,
- README and public documentation map pointers to the new Korean concept document,
- release note and public-safe work log for the v0.2.50 batch.

Clarified:

- `WOM` is pronounced `옴`, not `웜`,
- `zet` may be explained as `쪽글` or `토막글`, while the product term remains `zet`,
- `ZET` may be explained as `공유 계층`, while the product term remains `ZET`,
- Korean product terms are for public explanation, not CLI/JSON/schema/file/package renames.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- no real ZET transport, real trust/import/acceptance/anchor, attestation/signature write, RF access, key-sharing registry, mirroring delivery, provider sync, WordPress publishing, projection write/receipt, recommendation fetching/ranking/feed update, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.49 - 2026-05-27

Public release link hygiene patch.

Added:

- local public-link checker for repository Markdown and release-note link hygiene,
- tests for case-sensitive local Markdown links, release-note relative link rejection, GitHub `blob` link mapping, and suspicious GitHub `tree` file links,
- documentation explaining repo-local Markdown links, GitHub Release body links, external URLs, and case-sensitive public GitHub paths.

Fixed:

- release note links that were correct inside the repository but unsafe when copied into GitHub Release bodies.

Compatibility:

- no private archive migration is required,
- no archive product CLI or MCP behavior changed,
- no GitHub Release was edited by the tool,
- no network URL fetching, provider calls, WordPress publishing, projection writes, receipts, ZET transport, recommendation fetching/ranking, neighbor feed updates, trust/import/acceptance/attestation/signature/minting changes, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.48 - 2026-05-27

ZET radio-frequency recommendation model baseline patch.

Added:

- documentation for the future distinction between followed/neighbor feeds and recommended/broadcast feeds,
- documentation for the radio-frequency metaphor where a node tunes into an accessible ZET channel, frequency, scope, or broadcast lane,
- documentation for prompt-as-algorithm selectors as inspectable policy/rule/config/code bundles rather than only LLM prompts,
- sanitized non-executable selector shape example with central black-box ranking disabled.

Compatibility:

- no private archive migration is required,
- no CLI or MCP behavior changed,
- no recommendation fetching, ranking, feed update, provider call, WordPress publishing, projection write, receipt write, ZET transport, trust, import, acceptance, attestation, signature, minting, anchoring, delegation, payment, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior is implemented.

## v0.2.47 - 2026-05-26

ZET closed sharing model baseline patch.

Added:

- documentation for the base zettel-kasten layer as GitHub-tracked records, object storage, and DB relationships,
- documentation for the unit layer distinction between `zet` and `objet`,
- documentation for the future ZET closed sharing/SNS layer above the base system,
- documentation for pluggable user-selected surfaces such as custom SaaS, open-source ZET UI, static site, private archive UI, feed/RSS-like app, team workspace, WordPress, or future dedicated ZET client,
- sanitized non-executable example shape for a future closed sharing update.

Compatibility:

- no private archive migration is required,
- no CLI or MCP behavior changed,
- GitHub is clarified as base infrastructure or possible substrate, not the whole ZET sharing architecture,
- WordPress is clarified as one possible projection surface, not the WOM/ZET UI,
- attestation is described as receiver-side verification/review before any future neighbor feed update, mirror, or re-projection,
- this release does not call providers, publish to WordPress, write projection records or receipts, implement real ZET transport, automatically update neighbor feeds, mint, trust, import, accept, attest, sign, anchor, apply, add Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## v0.2.46 - 2026-05-26

ZET projection plan dry-run preview patch.

Added:

- `archive projection-plan <archive-root> --zet <zet-id-or-path> --surface <surface-kind> --dry-run --format json`,
- read-only MCP `zet_projection_plan_check`,
- metadata-only projection plan output for one local zet and one operator-declared surface kind,
- closed safety flags for provider, WordPress, projection-write, receipt-write, trust, import, acceptance, attestation, signature, mint, ZET transport, and full-auto behavior.

Compatibility:

- no private archive migration is required,
- the preview writes nothing and returns `would_change: []`,
- it does not output the full zet body,
- it uses archive-relative paths only,
- visibility is operator-declared intent, not verified provider state,
- projection format is future intent, not rendered body output,
- this release does not call providers, publish to WordPress, write projection records or receipts, mint, trust, import, accept, attest, sign, anchor, apply, run ZET transport, add Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.

## v0.2.45 - 2026-05-26

ZET publication surface baseline patch.

Added:

- documentation for the no-UI WOM core and user-selected publication/projection surfaces,
- sanitized example files for a future projection envelope, WordPress-like title, and WOM Safe HTML-compatible post body,
- release notes and work log for the ZET publication surface baseline.

Compatibility:

- no private archive migration is required,
- no CLI or MCP behavior changed,
- posting is documented as separate from minting,
- a surface locator is documented as separate from canonical zet identity,
- the examples use placeholder identifiers and `https://example.invalid/...` only,
- this release does not call providers, publish to WordPress, implement projection-plan CLI/MCP, create projection receipts, trust, import, accept, attest, sign, mint, anchor, run ZET transport, add payments, staking, consensus, blockchain, Redis, model training, backpropagation, or full-auto behavior.

## v0.2.44 - 2026-05-26

Foreign block attestation statement draft decision preview patch.

Added:

- `archive attestation-statement-draft-decision <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--decision-intent`, `--reviewer`, `--expected-review-scope`, `--expected-statement-style`, and `--review-note`,
- read-only MCP `foreign_block_attestation_statement_draft_decision_preview`,
- non-binding route previews for `keep_under_review`, `revise_statement_draft`, `reject_statement_draft`, `prepare_future_attestation_statement_review`, and `needs_more_review`,
- current statement draft record/receipt, candidate record/receipt, quarantine case/receipt, and decision record/receipt consistency checks before any route preview.

Compatibility:

- no private archive migration is required,
- the preview writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- the default route intent is `needs_more_review`,
- review notes are preview context only; raw note bodies are not echoed or stored,
- previewed statement drafts remain `untrusted_foreign`, with `decision_status: preview_not_recorded`, `attestation_status: not_created`, and `signature_status: not_created`,
- the decision preview does not create trust, import, acceptance, attestation, signatures, minting, sharing, WordPress publishing, provider calls, ZET transport, receipts, or apply behavior,
- MCP remains read-only and exposes no statement draft decision write/apply/accept, foreign block attest/sign/trust/import, provider sync, WordPress publishing, mint, anchor, or full-auto tool.

## v0.2.43 - 2026-05-26

Foreign block attestation statement draft review index patch.

Added:

- `archive attestation-statement-draft-review <archive-root> --format json`,
- optional `--case-id`, `--statement-style`, `--review-scope`, and `--include-receipts` filters,
- read-only MCP `foreign_block_attestation_statement_draft_review_index`,
- index validation for recorded untrusted attestation statement drafts and matching draft receipts,
- current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt consistency checks.

Compatibility:

- no private archive migration is required,
- the index writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- displayed style/scope filters do not hide blockers from other discovered statement draft records,
- `--case-id` scopes the consistency verdict to one case,
- indexed records remain `untrusted_foreign`, with `attestation_status: not_created` and `signature_status: not_created`,
- indexing a statement draft does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, acceptance, or apply behavior,
- MCP remains read-only and exposes no statement draft review apply/write/approve, foreign block attest/sign/trust/import/accept, mint, anchor, provider sync, or full-auto tool.

## v0.2.42 - 2026-05-26

Foreign block attestation statement draft write approval patch.

Added:

- `archive record-attestation-statement-draft <archive-root> --draft-preview <json-file> --dry-run --format json`,
- CLI-only `--approve --reviewed-by <safe-actor-id>` to record a local statement draft record and matching receipt,
- read-only MCP `record_attestation_statement_draft_check`,
- stale/tamper checks that treat the v0.2.41 draft preview JSON as untrusted input and revalidate current candidate, receipt, quarantine, and decision state before any write,
- rollback-safe exclusive creation for exactly two files: `attestation-statement-draft.json` and its quarantine receipt.

Compatibility:

- no private archive migration is required,
- dry-run writes nothing and approve writes exactly one statement draft record plus one receipt,
- approved records stay `untrusted_foreign`, with `attestation_status: not_created` and `signature_status: not_created`,
- recording the statement draft does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, acceptance, or apply behavior,
- MCP remains read-only and exposes no statement draft approve/write/apply, foreign block attest/sign/trust/import/accept, mint, anchor, provider sync, or full-auto tool.

## v0.2.41 - 2026-05-26

Foreign block attestation statement draft preview patch.

Added:

- `archive attestation-statement-draft <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-review-scope`, `--prospective-attestor`, `--statement-style`, and `--review-note`,
- read-only MCP `foreign_block_attestation_statement_draft_preview`,
- non-binding statement draft output for one recorded attestation review candidate,
- validation that re-reads the current candidate, candidate receipt, quarantine case/receipt, and decision record/receipt before returning a draft.

Compatibility:

- no private archive migration is required,
- the preview writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- the statement draft is not an attestation, not trust, not signing, not import, not minting, not a receipt write, and not ZET transport,
- hash commitments remain `not_verified`, `not_trusted`, and not proof of authenticity,
- MCP remains read-only and exposes no statement draft write/apply, foreign block attest/sign/trust/import/accept, receipt-write, full-auto, provider, or ZET transport tool.

## v0.2.40 - 2026-05-26

Foreign block attestation review candidate index patch.

Added:

- `archive attestation-candidate-review <archive-root> --format json`,
- optional `--case-id`, `--review-scope`, and `--include-receipts` filters,
- read-only MCP `foreign_block_attestation_review_candidate_index`,
- index validation for recorded untrusted attestation review candidates and matching candidate receipts,
- current quarantine case, original quarantine receipt, recorded decision, and decision receipt consistency checks.

Compatibility:

- no private archive migration is required,
- the index writes nothing, keeps `dry_run: true`, and always returns `would_change: []`,
- displayed filters do not hide blockers from other discovered candidate records,
- indexed candidates remain `untrusted_foreign`, `recorded_untrusted_candidate`, and `not_created`,
- indexing a candidate does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, acceptance, or apply behavior,
- MCP remains read-only and exposes no candidate review approve/write/apply/trust/import/attest/sign/mint/full-auto tool.

## v0.2.39 - 2026-05-25

Foreign block attestation review candidate write approval patch.

Added:

- `archive record-attestation-review-candidate <archive-root> --candidate-plan <json-file> --dry-run --format json`,
- CLI-only `--approve --reviewed-by <actor-id>` to record an untrusted attestation review candidate,
- optional replay guards for expected case id, review scope, and prospective attestor,
- read-only MCP `record_attestation_review_candidate_check`.

Compatibility:

- no private archive migration is required,
- dry-run writes nothing and approve writes exactly one candidate record plus one receipt,
- approved records stay `untrusted_foreign`, `recorded_untrusted_candidate`, and `not_created`,
- recording a candidate does not create trust, import, attestation, signatures, minting, sharing, provider calls, ZET transport, or acceptance,
- MCP remains read-only and exposes no candidate approve/write/apply/trust/import/attest/sign/mint/full-auto tool.

## v0.2.38 - 2026-05-25

Foreign block attestation review candidate plan patch.

Added:

- `archive attestation-review-candidate <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-decision`, `--expected-outcome`, `--prospective-attestor`, `--review-scope`, and `--review-note`,
- read-only MCP `foreign_block_attestation_review_candidate_plan`,
- a human-review candidate object for cases whose recorded decision is `eligible_for_attestation_review` and whose planned outcome is `prepare_attestation_review_candidate`.

Compatibility:

- no private archive migration is required,
- candidate planning writes nothing and never reads the original foreign artifact, source payloads, objet bodies, or provider URLs,
- all candidates remain `untrusted_foreign`, `planned_not_recorded`, and `not_created`,
- hashes in existing sanitized records are retained only as commitments or claims, not proof of authenticity,
- MCP remains read-only and exposes no candidate apply/write/accept/trust/import/attest/sign/mint/full-auto tool.

## v0.2.37 - 2026-05-25

Foreign block decision outcome plan patch.

Added:

- `archive quarantine-decision-outcome <archive-root> --case-id <safe-case-id> --dry-run --format json`,
- optional `--expected-decision`, `--reviewer`, and `--review-note`,
- read-only MCP `foreign_block_decision_outcome_plan`,
- conservative outcome routing for recorded quarantine decisions.

Compatibility:

- no private archive migration is required,
- outcome planning writes nothing and never reads the original foreign artifact,
- all outcomes remain `untrusted_foreign` and `planned_not_applied`,
- `eligible_for_attestation_review` only becomes `prepare_attestation_review_candidate`; it does not create trust or an attestation,
- MCP remains read-only and exposes no outcome apply/write/accept/trust/import/attest/mint/full-auto tool.

## v0.2.36 - 2026-05-25

Foreign block quarantine decision review index patch.

Added:

- `archive quarantine-decision-review <archive-root> --format json`,
- optional `--case-id`, `--decision`, and `--include-receipts` filters,
- read-only MCP `foreign_block_quarantine_decision_review_index`,
- consistency checks for recorded quarantine decision records and matching decision receipts,
- current quarantine case and original quarantine receipt checks when reviewing recorded decisions.

Compatibility:

- no private archive migration is required,
- the decision review index writes nothing and never reads the original foreign artifact,
- indexed decisions remain `untrusted_foreign` review records only,
- MCP remains read-only and exposes no quarantine decision review apply/write/accept/import/trust/attest/full-auto tool.

## v0.2.35 - 2026-05-25

Foreign block quarantine decision write approval patch.

Added:

- `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --dry-run --format json`,
- `archive record-quarantine-decision <archive-root> --decision-preview <json-file> --approve --reviewed-by <actor-id> --format json`,
- CLI-only approval-gated quarantine decision records under `quarantine/foreign-blocks/<case-id>/quarantine-decision.json`,
- quarantine decision receipts under `receipts/quarantine/<case-id>.foreign-block-quarantine-decision.json`,
- read-only MCP `record_quarantine_decision_check` for dry-run validation only,
- replay validation that re-reads the current quarantine case and receipt before any approved local decision record write.

Compatibility:

- no private archive migration is required,
- decision writes are local review records only; they never trust, import, mint, attest, anchor, delegate, sign, execute, accept, apply, share, or call providers,
- approved writes are limited to the sanitized quarantine decision JSON and quarantine decision receipt JSON,
- MCP remains read-only for this workflow and exposes no quarantine decision apply/write/import/trust/attest/accept/full-auto tool.

## v0.2.34 - 2026-05-25

Foreign block quarantine decision preview patch.

Added:

- `archive quarantine-decision <archive-root> --case-id <safe-id> --dry-run --format json`,
- optional preview context: `--decision-intent`, `--reviewer`, and `--review-note`,
- read-only MCP `foreign_block_quarantine_decision_check`,
- decision-path previews for existing untrusted quarantine cases: `keep_quarantined`, `reject_and_keep_record`, `eligible_for_attestation_review`, and `needs_more_review`.

Compatibility:

- no private archive migration is required,
- quarantine decision preview writes nothing and never reads the original foreign artifact,
- decision preview does not record approval, trust, import, attestation, minting, anchoring, delegation, signing, acceptance, or apply state,
- MCP remains read-only and exposes no quarantine decision apply/write/import/trust/attest tool.

## v0.2.33 - 2026-05-25

Foreign block quarantine review index patch.

Added:

- `archive quarantine-review <archive-root> --format json`,
- optional `--case-id`, `--status`, and `--include-receipts` filters,
- read-only MCP `foreign_block_quarantine_review_index`,
- inventory and consistency checks for `quarantine/foreign-blocks/<case-id>/quarantine-case.json`,
- matching quarantine write receipt checks under `receipts/quarantine/<case-id>.foreign-block-quarantine.json`.

Compatibility:

- no private archive migration is required,
- quarantine review index writes nothing and never reads the original foreign artifact,
- indexing does not mean reviewed, trusted, imported, attested, minted, anchored, delegated, signed, or accepted,
- MCP remains read-only and exposes no quarantine review apply/import/trust/attest/write tool.

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
