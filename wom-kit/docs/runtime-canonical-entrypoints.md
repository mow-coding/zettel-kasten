# Runtime Canonical Entry Points

Status: v0.4.1 Letter 140 recovery and command-truth checkpoint

Previous checkpoint: Status: v0.4.0 exact human approval and operator-friction checkpoint

Previous checkpoint: Status: v0.3.320 one-use credential capability broker checkpoint

Previous checkpoint: Status: v0.3.319 native credential popup and causal-evidence checkpoint

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

## v0.4.1 Current Runtime Delta

Start command planning from the parser-derived inventory instead of guessing
from a command name or an older document:

```powershell
archive capabilities --machine --format json
```

Its `data.approval_status_inventory` distinguishes
`approval_available`, `approval_fixed_closed`, and `approval_not_exposed` for
every canonical executable command path and its aliases. In v0.4.1, the parser
matches all 78 supplied fixed-close entries and reports zero unmatched entries.
This is parser evidence only: it does not evaluate archive prerequisites, and
`approval_not_exposed` does not mean that a command is read-only.

The one current writer change is
`zettel-objet-link --dry-run|--approve`. Approval requires the exact digest from
a fresh private plan, reviewer attribution, a local native exact-human dialog,
an authenticated durable claim, writer-side revalidation, and a v0.2 link
receipt. The binding covers the canonical zettel, a strict complete manifest
read plus its exact unique matching record set,
exact before snapshot, create-only receipt generation, and persistent
per-zettel control artifact. MCP exposes no link writer.

`zettel-objet-link-revert`, all Objet capture mutation routes, and
`project-version-update` plus its collision/bytecode repair writers remain
fixed closed. Their documented plans, previews, and audits remain available;
approval still returns `compound_exact_human_approval_binding_required`. The
remaining historical fixed-close commands retain the same boundary, so the
current parser count is 78 rather than v0.4.0's historical 79.

When an installed v0.4.0 global CLI must be bootstrapped and the exact public
v0.4.1 GitHub Release wheel has been independently confirmed, use the public
wheel directly:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.1/wom_kit-0.4.1-py3-none-any.whl"
archive --version
```

Run `archive --version` in a new process. This replaces only the global `uv`
tool installation. It does not update the project-local WOM-kit source mirror,
change a project pin, or make the fixed-closed `project-version-update` writer
available.

JSON usage and repaired high-risk command failures use
`wom-kit/cli-error/v0.1`. Usage errors return exit code `2`; policy and
precondition failures return `1`. `effects_state: none` means the protected
workflow did not start. `effects_state: unknown` is reserved for a caught
failure after the exact-human workflow began; inspect the durable claim and do
not auto-retry.

## Historical v0.4.0 Exact Human Control Entry Points

An AI may prepare a dry-run, but it cannot assert that a person approved an
exact write. Supported high-impact single writes must continue in the same
local interactive Windows CLI through this fixed sequence:

```text
TaskDialog -> authenticated durable started claim -> writer -> workflow finalize
```

Runtime prerequisite: the Windows Python host must provide a Comctl32 v6
activation context. Microsoft documents `TaskDialogIndirect` as requiring
[Comctl32.dll version 6](https://learn.microsoft.com/en-us/windows/win32/api/commctrl/nf-commctrl-taskdialogindirect).
WOM-kit verifies `DllGetVersion` immediately before dialog construction and
requires major version 6 or newer. Missing, older, or unverifiable activation
returns `exact_human_approval_activation_context_required` before dialog
display or claim creation.

There is no separately issued approval receipt or expiry window. The claim is
created after the native confirmation and before the writer. The writer
re-derives its operation binding immediately before mutation. Only the workflow
may finalize the claim. A remaining `started` state is an unknown outcome that
requires reconciliation and must not be replayed automatically.

The new operator routes are:

- `source-fidelity-session-evidence --dry-run|--approve` for private exact-byte
  session evidence;
- `facet-vocabulary --dry-run` for read-only stable facet discovery;
- `human-artifact-register-root --project-root|--external-root <root>
  --root-kind external_project|external_delivery --dry-run|--approve`, always-
  read-only `human-artifact-scan`, and
  `human-artifact-transition --dry-run|--approve`; `external_project` scans
  only `<root>/.wom-scratch`, while `external_delivery` scans the reviewed root
  itself; no Downloads/home auto-scan exists;
- `duplicate-object-reconcile --dry-run|--approve`, which may remove only
  unchanged byte-identical manifest repeats;
- read-only `approval-integrity-audit` and `approval-integrity-guard`, followed
  by `approval-integrity-overlay --dry-run|--approve` for an append-only
  reviewed overlay; and
- the existing AI create, mint, promotion, single-edge, and single-retirement
  routes after their exact dry-run bindings are reviewed.

MCP exposes only plan, scan, audit, and guard variants for these new local
approval operations. It cannot run the native dialog or accept an approval
claim supplied by the caller.

The runtime parser exposes one canonical fixed-close inventory of exactly 79
top-level commands. Every affected `--approve` help entry says that approval is
unavailable in v0.4.0 and directs the operator to the command-specific dry-run,
plan, preview, or audit surface; the exact list is published in the v0.4.0
release note and enforced against parser construction.

Nested `derive-text capture`, non-exact/non-AI `create-draft`, non-dry-run
CLI/MCP `init`, and `parcel`/`pack` are separately fixed closed. The existing
exact reviewed AI draft route and read-only previews remain available.

Compound writes have no complete target-set approval in v0.4.0.
`mint-zet-batch`, `retire-draft-batch`, `zettel-edge-batch`, `revert-edge`,
`revert-batch`, `zet-revision-write`, `zet-revision-restore-write`,
`zettel-objet-link`, `zettel-objet-link-revert`, and
`notion-objet-link-convert` remain dry-run only. So do the write/recovery
executors for activity-group membership add/removal, abstract backfill, and
title remap; `discard-draft`, `discard-draft-restore`, `remint-reconcile`, and
`retire-draft-reconcile`. Their read-only plan, preview, and audit commands
remain available. The `accept` branch of `relation-candidate-decide` is also
closed. Any affected approve request fails before private target read or mutation with
`compound_exact_human_approval_binding_required`.

The same fixed blocker covers project update/collision mutation, bytecode
repair, saved-view write/revert, private objet source-metadata write, identity
reconciliation, legacy cleanup, archive migration/revert, markup normalization
apply/revert/recovery, Principal register/unregister, objet-capture
enable/selection/single/batch, external import, source registration, ownership
transfer, object-storage mutation, Notion recovery, external-locator mutation,
source-intake record/batch, quarantine decisions, and delegation. These routes
have no exact-human v0.4 writer binding. Their plans, previews, and audits remain
available where documented; approval fails before private archive, project,
input, credential, or target reads and before provider calls, mutation, or
receipt publication.

Authenticated approval links for strict historical evidence require an exact
matching `succeeded` claim. Only `effect=created` proves that the approved
invocation created the original effect; `already_present_exact` records a later
review without rewriting history.

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

v0.3.300 historically added plan/write/recovery routes for provider-neutral
external locators, local relation candidate judgment, migration-markup
normalization, bounded batch Objet capture, project derived-bytecode repair,
Principal lifecycle, and selected base link-type adoption/revert. In v0.4.0
their mutation branches are fixed fail-closed as listed above; only read-only
plans, previews, audits, and Principal listing remain current entry points. The
relation rule reserves `continues` for the next
week/installment of the same course or work and `sequence` for the next
reviewed generic process step. Candidates and plans remain non-authorizing. A
plan digest and actor label do not substitute for an exact-human binding.

v0.3.302 historically added saved-view write/revert receipts. In v0.4.0 both
approval branches are fixed fail-closed before private request/target read or
mutation; direct AI writes to `views/*.yml` remain forbidden.

v0.3.308 historically extended the locator route with read-only
`external-locator-deactivate-plan` and mutation/revert executors. In v0.4.0
record, deactivate, and revert approvals are fixed fail-closed before private
target read or mutation. A runtime must never choose a duplicate by itself.
Different occurrence anchors, missing keeper
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

Only the read-only `project-bytecode-repair-plan --dry-run` eligibility and
repair plan may continue in v0.4.0. Historical v0.3
`project-bytecode-repair` could apply one reviewed bounded cleanup. In v0.4.0
its approval is fixed fail-closed before private project read or mutation with
`compound_exact_human_approval_binding_required`; it removes no cache artifact.
Mixed or unsupported sets remain `inspected_remediation_unavailable`.

The preview does not fetch, change `HEAD` or a pin, retry an updater, or grant
update authority. The updater approval is also fixed fail-closed in v0.4.0.
Verify import/source/pin/tag agreement from a new process. See
[Project Version Update](project-version-update.md),
[Bounded Operation Control](operation-control.md), and the
[v0.3.316 release note](releases/v0.3.316.md).

## v0.3.315 Update-Collision And Paired-Batch Entry Points

When `project-version-update` returns a bound collision, do not guess a local
path or repeat approval. Preserve its `materialization_plan_sha256` and opaque
`update-entry:NNNN` reference. Use the CLI-only
`project-version-update-collision --action inspect --dry-run` surface first.
Only an explicitly eligible ignored regular entry can proceed through a
separate `preserve-relocate` preview. In v0.4.0 collision mutation and updater
approval are fixed fail-closed; they do not delete, overwrite, copy, fetch,
retry the updater, or change a pin. Treat `recovery_required` and nullable write/relocation fields as a
stop signal and retain the private case and owned lock.

For one reviewed multi-item request containing originals with paired derived
text, `objet-capture-batch --dry-run` can inspect the bounded request. In
v0.4.0 batch approval is fixed fail-closed before private source read or
mutation. Historical v0.3.315 results partitioned original and derived
requested, written-or-ready, skipped, and blocked counts separately. `partial`,
`evidence_incomplete`, `recovery_required`, or
`batch_capture_outcome_unverified` is not success and must not be replayed
automatically. Historical evidence does not grant replay authority. If the staging originals are unavailable,
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
and raw draft body. In v0.4.0 human-declared/non-AI non-dry-run creation is
fixed closed; an old AI draft needs the attributed `legacy_source_fidelity_reviewed` affirmation,
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
| `credential-adopt` | First enrollment or explicit replacement only. Dry-run hashes the helper AI's public-safe task/reason with the stable request and opens no popup. Exact digest approval starts one isolated child and separate native Windows popup. Production hard-codes `CredentialPopupInputIntent.live_registration` and the blue `실제 자격 증명 등록` banner. A standard password EDIT retains ordinary editing/paste while an opaque sibling hides value, mask, caret, count, and length; WOM never reads the clipboard. The child detaches and sends `popup_child_detached` before live work. The parent restores its start-signal lease, accepts acknowledgement → final mapping → EOF, and joins every normally started child. A matching registration returns without another popup only after authenticated receipt, exact saved-secret fingerprint, provider/workspace-scope, and reviewed-anchor revalidation; no PAT/token/secret command option exists. |
| `credential-secure-list` | Lists unauthenticated content-free receipt metadata by default. `--verify` reads only the exact archive authentication-key target and verifies receipt/lifecycle MACs; it neither enumerates the native vault nor resolves a provider credential. |
| `credential-lifecycle` | Authenticates and digest-plans one selected active/current/default credential for an exact provider/workspace scope. In v0.4.0 the legacy approval writer is fixed closed before archive-key or credential access; it never records, deletes, or revokes a credential. |
| `notion-page-recovery-plan` | Validates the exact ignored-local two-group request of 577 plus 43 unique page UUIDs, exactly 620, and digest-plans a bounded slice with zero credential reads, provider calls, or writes. |
| `notion-page-recovery` | Dry-run/verified local replay only in v0.4.0. The approval branch is fixed fail-closed before credential read, provider call, or archive mutation with `compound_exact_human_approval_binding_required`. Historical v0.3.320 capability and recovery receipts remain auditable. |

The v0.3.319 correction replaces the rejected terminal-input prototypes with
one separate native Windows popup. Production hard-codes
`CredentialPopupInputIntent.live_registration` and shows the blue
`실제 자격 증명 등록` banner. The standard password EDIT retains ordinary
editing and paste behavior, but a fixed opaque sibling hides value, mask,
caret, count, and length. WOM never reads the clipboard. Empty input cannot be
confirmed; Cancel, X, and Escape stop before store/provider work.

The child detaches and sends `popup_child_detached` before
popup/native/store/provider/archive access. The parent restores its narrow
`SIGINT`/`SIGBREAK` start lease before receiving, accepts only
acknowledgement → final mapping → EOF, and joins every normally started child.
Raw input and exception text never cross IPC.

The child and parent v0.3 envelopes publish only
`credential_input_received`, `complete_line_received`,
`temporary_store_write_attempted`, and `provider_request_attempted`;
unknown child state projects four nulls. `provider_auth_rejected` requires an
actual provider request, and rollback `deleted` requires a fresh exact
post-delete absence probe. `credential_input_boundary_failed` with action
`repair_secure_input_boundary_and_create_a_new_plan` preserves truthful
`1000` or `1100` evidence and keeps store/provider false. Complete local
malformed/control/provider-shape, over-limit, or byte-oversize input uses
`credential_input_invalid_for_provider`. A temporary write without provider
transport uses `provider_request_not_attempted`.

The popup-only manual helper hard-codes
`CredentialPopupInputIntent.synthetic_acceptance`, emits
`wom-kit/windows-credential-popup-acceptance/v0.1`, and uses the red
`합성 입력 테스트 · 실제 키 입력 금지` banner plus fixed public challenge. It
requests no PAT and performs no registration, store write, or provider call.
The human synthetic row remains failed and is not repeated as a recovery
prerequisite. Actual registration remains `not_performed`; it may proceed only
after published-runtime verification and explicit confirmation of the blue
live-registration banner. Automated evidence is not human/live evidence.

The v0.3.320 historical correction left that popup and every public command unchanged.
After historical exact recovery approval, the parent issued one
`wom-kit/credential-capability/v0.1` document bound to request, plan, reviewer,
selected authenticated scopes, fixed read-only endpoints, registered
capabilities, a claim deadline, one use, and a request budget. The isolated
worker exclusively creates an archive-key-HMAC claim before the first native
secret read. TTL is only the claim deadline; a successfully claimed bounded
invocation is not cut off mid-run. Any existing id leaf blocks replay. Each
provider authorization maps to exactly one adapter transport attempt and
reauthenticates current authority.

The HMAC claim stores id/digest, request/plan, budgets, final status, and count.
The durable recovery receipt stores only
`wom-kit/credential-capability-reference/v0.1` schema/id/digest. The parent returns
a separately validated `wom-credential-capability-use-summary/v0.1`. A fully
verified replay creates no claim, reads no credential, and calls no provider.
See the [Credential Capability Contract](credential-capability-contract.md).

For internal integrations, current scope authority comes from Notion's
`bot.workspace_id`. A person PAT has no provider-returned workspace ID, so WOM
uses the archive-keyed fingerprint of the exact saved PAT under
`notion_pat_token_scope_v1` and also rechecks the current person plus reviewed
page. The same saved PAT can therefore serve another reviewed page. Another
PAT is not silently merged into that scope. One compatible authenticated
v0.3.311-v0.3.316 receipt may receive a
no-prompt, append-only local scope evolution after exact revalidation; absent
lifecycle still needs a human
default, and duplicate or complex lifecycle state stops for review.

The safe command shapes are:

```powershell
archive credential-adopt <archive-root> --account-label <safe-label> --workspace-label <safe-label> --task-summary "<public-safe current task>" --connection-reason "<public-safe reason>" --reviewed-anchor-page-id <uuid> --interactive --dry-run --format json
archive credential-adopt <archive-root> --account-label <safe-label> --workspace-label <safe-label> --task-summary "<same public-safe current task>" --connection-reason "<same public-safe reason>" --reviewed-anchor-page-id <uuid> --interactive --expected-request-sha256 <sha256> --approve --format json
archive credential-secure-list <archive-root> --format json
archive credential-secure-list <archive-root> --verify --format json
archive credential-lifecycle <archive-root> --provider notion --workspace-fingerprint <sha256> --default-credential-id <opaque-id> --dry-run --format json
archive notion-page-recovery-plan <archive-root> --request profiles/local/notion-page-recovery/<private>.json --max-items 5 --offset 0 --dry-run --format json
```

`credential-lifecycle --approve` is intentionally not a runnable v0.4.0
example: it returns `compound_exact_human_approval_binding_required` before
archive-key or credential access and writes nothing.

The request path, reviewed anchor UUID, page UUIDs, page bodies, native
credential target, PAT, Authorization header, token, and derived key must never
be echoed. In v0.4.0 recovery approval is fixed fail-closed before credential
read, provider call, or archive mutation; locally verified replay is not a
separate approval authority.
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
conservative structural signals, not proof or automatic repair. In v0.4.0
saved-view write/revert and event-membership add/removal/recovery approvals are
fixed fail-closed before private target read or mutation with
`compound_exact_human_approval_binding_required`. Their read-only plans and
audits remain available, and historical request/journal/receipt evidence stays
separate and immutable. Neither path infers membership or exposes an MCP
writer. See
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

To audit historical `zet-revision-write` evidence, run the separate CLI-only
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
even when current bytes repeat an older state. Pass the exact plan hashes
through CLI-only `zet-revision-restore-write --dry-run`, then stop. In v0.4.0
restore approval is fixed fail-closed before private target read or mutation
with `compound_exact_human_approval_binding_required`; it writes no canonical
byte or restore receipt. MCP has no restore writer.

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
