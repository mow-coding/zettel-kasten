# Runtime Canonical Entry Points

Status: v0.3.316 Letter 129 complete collision-set inspection and cache-repair checkpoint

When an AI runtime enters a WOM archive, it needs a small, explicit "start
here" map. The archive may contain zets, source bindings, provider metadata,
object manifests, receipts, local instructions, and generated indexes. Without a
canonical entrypoint summary, an agent can mistake a partial export, mirror, or
secondary folder for the archive source of truth.

For the complete beginner-facing entry map, start with:

```powershell
archive ai-start-here <archive-root> --dry-run --progress --format json
```

The underlying raw context packet remains available through:

```powershell
archive runtime-context <archive-root> --format json
```

Both paths are quick by default and do not construct Doctor. Add
`--full-doctor` only when a complete archive health check is required. The
result includes `canonical_entrypoints`. From v0.3.117, it also includes
`operational_context`, a read-only view of `ops/operational-context.yml` for
AI-facing mission, scope, state, gotchas, and reviewed decisions. The
`canonical_entrypoints` object includes machine-readable `ai_runtime_order`,
`recommended_first_commands`, `action_routing`, and `material_link_routes` so
a terminal-capable AI can discover both the operational handoff and the
official read/write command paths without waiting for the human to mention
them.

## Explicit Host Guidance Readiness

Ordinary `runtime-context` and `ai-start-here` do not inspect a host
installation or a repository's `AGENTS.md`. They return
`runtime_guidance_readiness.status: not_checked` and the exact opt-in command:

```powershell
archive runtime-guidance-readiness <archive-root> --host codex --scope repo --repo-root <repo-root> --format json
```

The explicit command checks the current Codex runtime Skill state and the
repository-level exact routing contract without writing either location.
Missing Skill installation, an absent exact `AGENTS.md` contract, and a
present but non-current contract are separate diagnostics. Legacy phrase
anchors are human migration hints only. Unreadable or unsupported inputs fail
closed. If installation is needed, the result offers only the exact
`runtime-skill-install --dry-run` command; it never installs automatically and
never rewrites `AGENTS.md`. Successful inspection still reports host guidance
consumption as `not_proven`.

## Official Action Routing

Introduced in v0.3.278 and extended through v0.3.308, `action_routing` uses
`wom-kit/ai-command-path-routing/v0.13`. It tells an AI which official command
handles session entry, search, local version truth, saved-view inspection,
inbox pipeline-shape review, explicit event-membership add/removal planning, command
discovery, draft creation, minting, typed edges, source capture, and
operational-context updates.

v0.3.300 adds official plan/write/recovery routes for provider-neutral
external locators, local relation candidate judgment, migration-markup
normalization, bounded batch Objet capture, and project derived-bytecode
repair. It also routes reviewed third-party Principal registration and
unregistration, Principal listing, and selected base link-type
adoption/revert. The relation rule reserves `continues` for the next
week/installment of the same course or work and `sequence` for the next
reviewed generic process step. Candidates and plans remain non-authorizing.
Every listed mutation still requires a separate exact plan SHA-256 and
attributed human approval.

v0.3.302 adds a closed private request, preview, approval, immutable receipt,
and exact revert route for persistent saved views. Direct AI writes to
`views/*.yml` remain forbidden.

v0.3.308 extends the locator route with read-only
`external-locator-deactivate-plan` and approval-gated
`external-locator-deactivate`. A runtime must never choose a duplicate by
itself: the human names both the weaker active target and the compatible active
keeper. Approval re-plans under the existing lock, changes only the target to
`inactive`, preserves a prior snapshot and receipt, and keeps the ordinary
exact-byte locator revert route. Different occurrence anchors, missing keeper
coordinates, canonical body references, ambiguity, and stale bytes block.

The same checkpoint extends reviewed migration-markup routing for one complete
paired-file digest, self-closing page/audio bindings, and a strict safe table
cell subset. Unsupported, content-bearing, repeated identity-free, unsafe, or
unbalanced shapes remain byte-identical and blocked; the runtime must not infer
an edge, objet identity, or table semantics. See
[Letter 115 Completion](letter115-completion.md).

v0.3.309 adds no command and does not change the action-routing
schema. It narrows the existing markup plan/apply route: v0.2 manifests can
select a complete 1-based same-digest occurrence sequence within one zettel;
legacy v0.1 bindings remain unique-only. A reviewed `zettel_reference` may turn
one self-closing page mention into navigation to a unique current canonical
target, but it does not create an edge or infer a relation. One exact generated
`<unknown:table_of_contents/>` at the immutable original body's first nonempty
line may be removed; no heading scan or generated navigation is materialized.
Bare `callout` and `database`, plus `unknown:synced_block`,
`unknown:transclusion_reference`, `unknown:transclusion_container`,
`unknown:column_list`, `unknown:column`, `unknown:link_preview`, and
`unknown:unsupported`, remain deferred and fail closed because identity or
required child semantics are unverified. This does not remove existing
`<synced_block>`/`<synced_block_reference>` inner-preserving or
`<column>/<columns>` structural normalization. See
[Letter 116 Completion](letter116-completion.md). Source documentation and
external CI, exact-tag, GitHub Release, and wheel evidence remain distinct
verification layers.

v0.3.310 also adds no command and does not change action routing. It narrows
the same markup plan/apply route for four imported reference shapes. Exact
lowercase, attribute-free, self-closing `unknown:synced_block`,
`unknown:transclusion_reference`, and `unknown:transclusion_container`
occurrences may use complete v0.2 occurrence authority for one static
canonical zettel or manifested objet destination. One empty paired `database`
with required `inline` and `url`, optional `data-source-url`, exact boolean
`inline`, and no extra attributes may use a reviewed zettel destination. The
runtime must not describe these static links as an edge, live sync,
transcluded-child reconstruction, database view, or provider lookup.

Markup-like bytes inside quoted HTML attributes, unreviewed raw-HTML blocks,
multiline-label reference definitions, and next-line reference titles are
terminal literal content: the complete zettel remains unchanged. A runtime
must not present protected-context counts as actionable migration debt.
Callout display semantics, unknown column structure, unsupported content,
malformed or content-bearing reference shapes, incomplete selectors, and any
co-blocked zettel remain fail closed. Normalizing safe source spans outside a
protected literal is not implemented. See
[Letter 117 Completion](letter117-completion.md). Source documentation and
external CI, exact-tag, GitHub Release, and wheel evidence remain distinct
verification layers.

## v0.3.316 Complete Collision-Set Recovery Entry Points

When an updater returns many opaque runtime-source-shadow collisions, keep the
exact target and `materialization_plan_sha256`. Do not loop through entry refs
or infer local names. Run the alias-free CLI-only
`project-version-update-collision --action inspect-all --dry-run`; it evaluates
the complete set from one unchanged plan.

Only `project_bytecode_repair` eligibility for the exact complete set may
continue. Run `project-bytecode-repair-plan` with the same target and
materialization digest, review its separate plan digest, then use the approved
`project-bytecode-repair` form with reviewer attribution and
`--affirm-external-writers-quiescent`. The repair shares the updater lock and
removes only exact supported ignored cache artifacts. Mixed or unsupported
sets remain `inspected_remediation_unavailable`.

Repair success is not update success. The repair does not fetch, change `HEAD`
or a pin, retry an updater, or grant update approval. Always run a fresh updater
preview and approve that new update plan separately, then verify import/source/
pin/tag agreement from a new process. See
[Project Version Update](project-version-update.md),
[Bounded Operation Control](operation-control.md), and the
[v0.3.316 release note](releases/v0.3.316.md).

## v0.3.315 Update-Collision And Paired-Batch Entry Points

When `project-version-update` returns a bound collision, do not guess a local
path or repeat approval. Preserve its `materialization_plan_sha256` and opaque
`update-entry:NNNN` reference. Use the CLI-only
`project-version-update-collision --action inspect --dry-run` surface first.
Only an explicitly eligible ignored regular entry can proceed through a
separate `preserve-relocate` preview and approval. That action does not delete,
overwrite, copy, fetch, retry the updater, or change a pin. After a successful
preservation, always run a fresh updater dry-run and a separate updater
approval. Treat `recovery_required` and nullable write/relocation fields as a
stop signal and retain the private case and owned lock.

For one reviewed multi-item request containing originals with paired derived
text, use `objet-capture-batch` rather than rebuilding selection rows by hand.
The v0.3.315 result must partition original and derived requested,
written-or-ready, skipped, and blocked counts separately. `partial`,
`evidence_incomplete`, `recovery_required`, or
`batch_capture_outcome_unverified` is not success and must not be replayed
automatically. A fresh replay of the same request may skip exact existing
originals and finish derived text. If the staging originals are unavailable,
use durable original capture receipt object IDs in a separately reviewed
`derive-text capture --from-manifest` request instead of recopying them.

These routes remain local CLI workflows. The collision surface has no MCP
method, and the current AI `action_routing` machine schema remains v0.13. See
[Project Version Update](project-version-update.md),
[Derived Text Capture](derived-text.md), and the
[v0.3.315 release note](releases/v0.3.315.md).

## v0.3.314 Long-Operation And Index-Recovery Entry Points

For `project-version-update`, `index`, and `index-health`, use a fresh
command-appropriate `--output` path. Archive operations use
`.wom-scratch/diagnostics/*.json`; project-root updates use
`.zettel-kasten/diagnostics/*.json`. Preserve the opaque `operation_ref`
printed to stderr before the long work begins.

If the caller times out, do not start a duplicate writer. Use the exact
starting root and reference with `operation-control --action status --dry-run`,
bounded `wait`, or read-only `recovery-plan`. A wait deadline is neutral.
Cancel and resume are unsupported and write nothing; no MCP, daemon, queue,
background launcher, force kill, lock deletion, or automatic rollback exists.
A completed output proves only the verified saved CLI result, so follow its
command-specific next action.

Generated-index health must pass the clean rollback `DELETE` header and
no-sidecar preflight before SQLite opens. A legacy WAL-mode generated cache or
private projection blocker needs one ordinary explicit `archive index`
rebuild, followed by a fresh `index-health`. Do not hand-edit or delete the
database or sidecars. See [Bounded operation control](operation-control.md),
[Index Health](index-health.md), and the
[v0.3.314 release note](releases/v0.3.314.md).

## v0.3.313 Source-Fidelity Entry Points

Every new AI-assisted or AI-generated draft starts with one manifested local
content-addressed source. Preview `archive create-draft` with
`--source-fidelity`, `--fidelity-audience`, and
`--fidelity-source-object-id`, then replay the unchanged request only with
`--approve`, `--draft-approved-by`, `--expected-body-sha256`, and
`--expected-source-fidelity-plan-sha256`. Declared AI `created_by`,
`assisted_by`, or non-empty `local_ai_sessions` evidence cannot downgrade to
the human route; it fails as `ai_provenance_requires_ai_creation_mode`.

Use `verbatim` only for a personal archive and `private_self`; private personal
data remains intact while credential secrets block. `faithful_summary` and
`sanitized_derivative` bind an exact human-reviewed candidate but do not claim
machine-proven semantic faithfulness. The full source authority stays in a
private create-only receipt; frontmatter and ordinary CLI/MCP output expose a
safe projection with explicit reviewer attribution.

Before publication, run `mint-zet --dry-run` and use its current
source-fidelity plan digest in the approved CLI replay. Mint re-reads the source
and raw draft body. Existing human-written creation remains compatible; an old
AI draft needs the attributed `legacy_source_fidelity_reviewed` affirmation,
not an inferred historical mode. MCP `create_draft_zettel` carries the matching
create fields and binds its own AI identity; `mint_zettel_check` is preview-only.
Audience is not an ACL and none of these actions shares, exports, transports,
or calls a provider.

The stopped shortening attempt produced no draft or mint write, so verified
data loss is zero. Local tests establish implementation behavior only, not
merge, CI, tag, Release, wheel, fresh-install, real-archive, sharing, or human
acceptance evidence. See [Source Fidelity And Private Verbatim Preservation](source-fidelity-and-private-verbatim.md)
and the [v0.3.313 release note](releases/v0.3.313.md).

## Letters 120 and 123 index and feedback entry points

From v0.3.312, official index-backed search, structured zettel views, and mint
planning use the same current-index authority. `archive_index_rebuild_required`
means that the command returned no authoritative rows or mint decision. Run an
explicit `archive index --progress`, verify with `index-health --dry-run
--progress`, and then retry; do not use raw SQLite, stale rows, or a silent live
body scan as a substitute.

Large mint previews and approvals accept `--progress`. Stderr carries only
content-free progress while stdout remains the final result. Progress is not an
approval receipt.

Substantive operator feedback uses `operator-feedback-compose --dry-run`, the
unchanged digest-bound reviewed replay, and
`operator-feedback-body-check --dry-run`. The body digest is then bound through
the existing `operator-feedback-record` metadata lifecycle. A metadata row or
delivery status alone does not prove body completeness, external submission, or
human receipt.

## Letters 118-119 Credential And Reviewed Recovery Entry Points

v0.3.311 adds five CLI-only commands without adding any corresponding MCP
secret reader, provider caller, or archive writer:

| Command | Canonical role |
| --- | --- |
| `credential-adopt` | Dry-run hashes one stable public intake request. Exact `request_sha256` approval opens only a native masked Windows dialog in a fresh spawned child; no PAT/token/secret command option exists. |
| `credential-secure-list` | Lists unauthenticated content-free receipt metadata by default. `--verify` reads only the exact archive authentication-key target and verifies receipt/lifecycle MACs; it neither enumerates the native vault nor resolves a provider credential. |
| `credential-lifecycle` | Authenticates and digest-plans one human-selected active/current/default credential for an exact provider/workspace scope, then records only that unchanged approved decision. It never deletes or revokes another credential. |
| `notion-page-recovery-plan` | Validates the exact ignored-local two-group request of 577 plus 43 unique page UUIDs, exactly 620, and digest-plans a bounded slice with zero credential reads, provider calls, or writes. |
| `notion-page-recovery` | Repeats the same plan in dry-run or, with the exact reviewed plan SHA and reviewer, invokes spawned authenticated read-only Notion recovery and writes only content-addressed objets plus private recovery evidence. |

The safe command shapes are:

```powershell
archive credential-adopt <archive-root> --account-label <safe-label> --workspace-label <safe-label> --reviewed-anchor-page-id <uuid> --interactive --dry-run --format json
archive credential-adopt <archive-root> --account-label <safe-label> --workspace-label <safe-label> --reviewed-anchor-page-id <uuid> --interactive --expected-request-sha256 <sha256> --approve --format json
archive credential-secure-list <archive-root> --format json
archive credential-secure-list <archive-root> --verify --format json
archive credential-lifecycle <archive-root> --provider notion --workspace-fingerprint <sha256> --default-credential-id <opaque-id> --dry-run --format json
archive credential-lifecycle <archive-root> --provider notion --workspace-fingerprint <sha256> --default-credential-id <opaque-id> --expected-plan-sha256 <sha256> --reviewed-by <actor> --approve --format json
archive notion-page-recovery-plan <archive-root> --request profiles/local/notion-page-recovery/<private>.json --max-items 5 --offset 0 --dry-run --format json
archive notion-page-recovery <archive-root> --request profiles/local/notion-page-recovery/<private>.json --max-items 5 --offset 0 --expected-plan-sha256 <sha256> --reviewed-by <actor> --approve --format json
```

The request path, reviewed anchor UUID, page UUIDs, page bodies, native
credential target, PAT, Authorization header, token, and derived key must never
be echoed. Recovery approval already permits credential reads, read-only
provider GETs, and archive evidence writes for the selected slice; locally
verified replay is only an optimization and not a separate approval authority.
The recovery lane never searches a workspace broadly, writes to Notion,
downloads media, rewrites canonical zets, infers edges, or mints pages.

This is an implementation and regression-test checkpoint only. No real PAT,
Windows vault, Notion provider, 620-item recovery, external source-archive operation,
PR/CI, exact tag, GitHub Release, wheel, fresh install, or human acceptance is
proved here. See
[Letters 118 and 119: credential continuity and reviewed Notion page recovery](letter118-119-credential-continuity-and-notion-page-recovery.md)
and [v0.3.311 release notes](releases/v0.3.311.md).

When the question is observed current canonical source-reference coverage
versus separately recorded storage evidence, use `python -B -m
wom_kit.archive_cli source-reference-coverage-audit <archive-root> --dry-run
--format json`. Its complete traversal state is not an archive-wide source
denominator or a live storage claim.

Search uses `archive search <archive-root> <query> --count-total --format
json`; raw grep and raw SQL are not authoritative WOM search. Before a global
claim that an objet or source does not exist, follow it with
`archive objet-rediscovery-plan <archive-root> <query> --dry-run --count-total
--format json`. That plan preserves index completeness separately and reports
unchecked or unimplemented layers; an index-only zero is not global absence.
The read-only `artifact-lifecycle-inventory` route gives one bounded,
content-free checkpoint over fixed local lifecycle roots. It grants no cleanup
authority and checks no provider or sibling object store. AI drafts use
`archive create-draft` preview and exact reviewed replay; a direct Markdown
write into `inbox/` is forbidden. Declared AI drafts require an explicit safe
abstract, non-empty facets, manifested source, fidelity mode, and audience;
their approved replay is bound to both the reviewed body and fidelity-plan
digests. AI provenance cannot use the human route. A same-title inbox draft
must be revised in place. A publication request starts mint preview, including
source/body re-verification when applicable, and is not complete until the
approved mint has canonical and receipt evidence; blockers must be reported
immediately. `archive version` does not verify remote
release freshness. `archive inbox-pipeline-audit --dry-run` returns
conservative structural signals, not proof or automatic repair. Saved-view
writes use only the review-gated `saved-view-write` and exact
`saved-view-revert` routes. Event-membership additions and removals use
separate digest-bound writers and separate recovery commands; neither path
infers membership or exposes an MCP writer. v0.3.284 routes explicit removal
from its read-only plan through approved write and interruption recovery.
Both operations share one global lock and fail-closed two-root evidence scan
while retaining separate request, journal, receipt, and recovery contracts. See
[AI Command-Path Routing](ai-command-path-routing.md).

## AI Runtime Order

When an AI enters an archive, use this order before interpreting or writing
anything:

1. Run `archive ai-start-here <archive-root> --dry-run --progress --format
   json`, or use quick `runtime-context` when the host specifically needs the
   raw packet. Do not run both back-to-back. Surface its `inbox_attention`
   before broad work; the content-free count is not repair, discard, or mint
   authority.
2. Follow `next_commands`; runtime-context is already listed under
   `completed_commands` with `run_required: false`.
3. Read `operational_context.session_start_injection` when present.
4. Read `canonical_entrypoints`, especially `archive.yml`, `AGENTS.md`, and
   `ops/operational-context.yml`.
5. Run `archive first-read-readiness <archive-root> --dry-run --progress
   --format json`. Repair explicit-abstract or unique-id gaps through reviewed
   flows before claiming memory-reconstruction readiness. Process exit zero
   means the diagnostic completed; only `readiness_met` proves this gate is
   ready. For a large legacy gap, use only the official three-zet pilot first.
6. Run `archive abstract-freshness <archive-root> --dry-run --progress --format
   json`. Treat stale, unverified, or missing rows as a human review queue;
   never auto-rewrite an abstract or body. Its progress is two stages;
   `stage=1/2` ending is not whole-command completion.
7. Run the complete private `zet-catalog-pass`, validate and read it from page
   zero, and distinguish generated zet coverage from actual host consumption.
8. Run `archive ai-response-concept-guide <archive-root> --topic all --dry-run`
   when the human is asking what to do next.
9. For Notion material links, choose the route from that guide:
   `notion-import-locator-loss-audit` to census omission markers, recorded
   counts, and source-page join-key presence,
   `notion-import-locator-evidence-plan` to validate a human-reviewed private
   occurrence mapping against exact current canonical bytes,
   `notion-objet-import-clue-audit` to check omitted-locator material clues,
   `notion-objet-source-map-link-plan` when source maps or ledgers can recover
   a candidate, or `notion-objet-link-index` / `notion-objet-link-plan` when
   body locators still exist.
10. Run `archive operator-feedback-plan <archive-root> --dry-run` (read-only)
   when the human reports tool friction, a workflow gap, or asks where
   feedback records live; recording still needs a separate
   `archive operator-feedback-record --approve` review gate. From v0.3.160 the
   record/receipt shapes ship as
   `wom-kit/schemas/operator-feedback.schema.json` and
   `wom-kit/schemas/operator-feedback-receipt.schema.json`.

After any approved `zet-revision-write`, run the separate CLI-only
`archive zet-revision-receipt-audit <archive-root> --dry-run --progress
--format json` before session handoff. This is a bounded history and
transaction-lock check, not another archive startup scan and not permission to
delete a leftover lock.

For a v0.2 ordinary revision receipt, first use CLI-only `archive
zet-revision-restore-proposal-from-snapshot <archive-root> --receipt
<canonical-revision-receipt> --expected-receipt-sha256 <sha256> --dry-run
--format json`, then approve only its unchanged plan digest. This creates an
independent private review copy and does not approve a restore. For a legacy
v0.1 receipt, a human must still recover complete old zet bytes from a trusted
private backup. Then use CLI-only `archive zet-revision-restore-plan <archive-root>
--receipt <canonical-revision-receipt> --expected-receipt-sha256 <sha256>
--restore-proposal .wom-scratch/revisions/restores/<private>.md --dry-run
--format json`. A green plan only prepares private human review and grants no
manual-copy authority. The selected receipt must be the actual newest event,
even when current bytes repeat an older state. Since v0.3.239, pass the exact
plan hashes through CLI-only `zet-revision-restore-write --dry-run`, then use
its unchanged write digest and event time only after explicit human approval.
The approved writer installs exact reviewed bytes and appends one restore
receipt; rerun the exact approved command after interruption. MCP has no
restore writer.

This order keeps archive identity, operational mission/state, local
instructions, beginner-facing wording, and material-link safety gates aligned
before any later approval-gated write.

Runtime context treats `archive.yml principal` as the archive principal
declaration and `archive-identity.yml` as the identity and ownership core. Its
`identity_consistency` block reports whether duplicated metadata agrees. A
non-aligned result routes first to `archive identity-reconcile <archive-root>
--dry-run --format json`; it never grants automatic write authority.

To inspect only the operational handoff, run:

```powershell
archive operational-context <archive-root> --dry-run --format json
```

Before ending or resetting the AI session, verify that current work has a
durable handoff rather than trusting chat memory:

```powershell
archive session-handoff-checkpoint <archive-root> --dry-run --format json
```

The checkpoint requires receipt-backed operational-context bytes and a complete
reviewed AI artifact inventory. Its separate confirmation and approval flow is
described in [Session Handoff Checkpoint](session-handoff-checkpoint.md). It
does not read the host chat and does not prove remote backup.

Before an AI describes backup condition, use the local-only evidence surface:

```powershell
archive backup-evidence <archive-root> --dry-run
```

It reports receipt-time object coverage separately from the still-unverified
GitHub and external-database lanes. It performs no remote check and never turns
configuration or a declared label into backup completion. See
[Backup Evidence Status](backup-evidence-status.md).

The same order is returned in JSON:

```text
canonical_entrypoints.ai_runtime_order
canonical_entrypoints.recommended_first_commands
canonical_entrypoints.completed_commands
canonical_entrypoints.next_commands
canonical_entrypoints.remaining_ai_runtime_order
canonical_entrypoints.action_routing
canonical_entrypoints.material_link_routes
action_routing
operational_context.action_routing
operational_context.session_start_injection
```

The route list includes `notion-import-locator-loss-audit`,
`notion-import-locator-evidence-plan`, `notion-objet-import-clue-audit`,
`notion-objet-source-map-link-plan`, `notion-objet-link-index`, and
`notion-objet-link-plan`, with each route marked as read-only and
provider-free.

## Start Here

The first authoritative file is:

```text
archive.yml
```

It identifies the archive, type, principal, root policy, and write policy. The
runtime entrypoint summary then lists other archive-relative files/directories
and their roles:

- `AGENTS.md`: local agent instructions,
- `archive-identity.yml`: owner and principal identity context,
- `source-bindings.yml`: source catalog,
- `provider-bindings.yml`: provider setup metadata,
- `ops/operational-context.yml`: AI-facing mission, scope, state, gotchas, and
  reviewed decisions,
- `zettels/`: canonical zets,
- `inbox/`: draft inbox,
- `objects/manifests/files.jsonl`: objet manifest,
- `objects/manifests/derived-text.jsonl`: derived-text manifest,
- `views/`: saved views,
- `db/schema.sql`: SQLite schema context.

Each item reports only a role, expected kind, required flag, status, and
archive-relative path. Missing optional files remain optional. Missing required
files should make the human or AI stop and repair the archive before treating
the workspace as authoritative.

## Privacy Boundary

The entrypoint check is mostly a map, not an import. The operational context
field intentionally reads only `ops/operational-context.yml` so the AI can
rehydrate the current mission/state. Apart from that bounded record:

- it reads no other file bodies,
- it writes no files,
- it calls no providers,
- it reads no secrets, keyrings, vaults, browser stores, mailboxes, or source
  documents,
- it echoes no local absolute paths by default.

Use `runtime-context --no-redact-local-paths` only for trusted local debugging.
Use `runtime-context --full-doctor --progress` only when complete validation is
needed. Quick mode reports `doctor_summary.checked: false` and is not an archive
health claim.

## Exact New-Archive AGENTS Routing Contract

New archive templates include exactly one versioned positive routing block:

```markdown
<!-- WOM-RUNTIME-GUIDANCE-ROUTING v0.3.293 BEGIN -->
This is the current authoritative WOM runtime guidance routing contract. Follow every directive in this block.
Run `archive ai-start-here <archive-root> --dry-run --progress --format json` before choosing an archive action.
Read and follow the returned `action_routing`.
Read `inbox_attention` and surface every unpublished-draft count before broad work.
Use `archive search <archive-root> <query> --count-total --format json` for official WOM search.
Raw grep and raw SQL are not authoritative WOM search results.
For operator feedback, run `archive operator-feedback-plan <archive-root> --dry-run --format json`, inspect `archive operator-feedback-ledger <archive-root> --dry-run --format json`, compose and approve the six-section body through `operator-feedback-compose`, verify it with `operator-feedback-body-check --dry-run`, require human review, preview `archive operator-feedback-record <archive-root> ... --feedback-ref feedback-body-sha256:<digest> --intent create|update --dry-run --format json`, and only then use the reviewed `--approve` replay; create never overwrites, while update also requires the fresh `--expected-record-sha256`.
<!-- WOM-RUNTIME-GUIDANCE-ROUTING v0.3.293 END -->
```

`runtime-guidance-readiness` accepts the block only when both sentinels occur
once, in order, and the inclusive block matches these bytes after CRLF-to-LF
normalization only. The fixed authority sentence is part of that canonical
machine-readable unit; deleting it or changing it into a negation or historical
label makes the unit non-current. A quoted, fenced, duplicated, truncated,
reordered, or otherwise edited copy is also non-current. Arbitrary prose
outside the sentinels is not natural-language parsed as an override of an
otherwise exact active unit; an example or historical copy must therefore be
quoted, fenced, or byte-distinct. Legacy phrases elsewhere are migration hints
only and never support `ready: true`. Existing `AGENTS.md` files are never
rewritten automatically.

## Not Implemented

The quick/default path does not enforce migration, auto-upgrade project folders, scan broad
file contents, choose between competing exports, synchronize providers, write
material links, or run IMAP adapters. It gives AI runtimes a deterministic
archive-relative map, a bounded operational-context rehydration record, and the
read-only guide command or material-link route to run next.
