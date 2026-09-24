# Exact Human Approval Contract

Status: v0.4.24 per-session permission modes; v0.4.22 operator abandon of a started project-update claim; v0.4.19 field-level updater revalidation; v0.4.0 one-use authority baseline preserved

## Purpose

A caller-supplied actor label or command-line affirmation does not prove that a
human reviewed exact archive changes. v0.4.0 therefore separates ordinary
operator intent from one-use exact human approval.

v0.4.19 keeps the existing human decision boundary but makes its machine
preconditions explicit. Project-update preparation is re-observed as separate
privacy-safe dimensions for Git, refs, pins, policy, supply, bootstrap,
launcher, materialization, and the prepared runtime payload. Each dimension is
`passed`, `failed`, `not_reached`, or `unavailable`; expected transaction
effects such as the reservation, lock, private candidate, and progress output
are excluded. A changed or unavailable required dimension stops before the
project mutation rather than being reduced to one unexplained false boolean.
The record exposes only fixed dimension names and reason codes, never compared
values, paths, refs, labels, or digests.

v0.4.18 lets a completed project-update transaction whose post-image the
project has since left prove its cleanup authority from the archive claim
store. The transaction journal binds the digest of the succeeded claim's public
reference at `approval_bound` and on every later checkpoint; identifier-free
`--resume` re-reads the bound claim store with the production key and accepts
exactly one MAC-verified `succeeded` claim that reproduces that digest. No
approval context is rebuilt, no live component is classified, and no key or
claim is created. The authenticated claim, not the retained plan, is the
authority, and the result attributes no past success. When the exact-human
workflow wraps a service failure as `exact_human_approval_state_unknown`, the
error may carry one fixed code-shaped `cause_code` and its fixed `cause_stage`;
the CLI copies only allowlisted literals into the redacted failure artifact and
never raw exception text.

v0.4.17 does not turn cleanup into a new human decision. Fresh project-update
dry-run and approval use one read-only namespace classification before native
approval. Exact terminal control history requires identifier-free `--resume`;
WOM verifies its fixed evidence and cleanup authority, while the person only
affirms that other writers for the same project are paused. Exact preapproval-
abort compaction enters no project-domain writer, grants no fresh approval
authority, and retains canonical proof history. Partial, malformed, changing,
mixed, ambiguous, or unsafe evidence stays fail-closed. A known gate returns a
fixed privacy-safe reason and next action, never private identifiers or raw
exception text.

v0.4.16 does not create a second approval or broaden the approved domain
effect. For project update, the exact succeeded claim signs a private terminal
record before cleanup; later resume reauthenticates that record and the exact
postimage before reusing the exact bound privacy-safe output, without reentering
the domain writer. The terminal journal stays immutable while the handoff moves
through `active`, `display-pending`, and hash-named `consumed`; display is
identical at-least-once, consumed state is history, and delivery
acknowledgement does not prove that a person or model saw stdout. One complete
legacy cleanup tombstone is recoverable only after exact structure,
checkpoint, claim, postimage, and cleanup-authority validation. Cleanup proof
alone grants neither past-success attribution nor cleanup, retry, or handoff
authority; proof-only state requires a fresh approval for a new update, while
partial or malformed residue fails closed.
For incident preservation, the existing exact-approved
`operator-feedback-compose --intent create` lane may also run when project
runtime alignment is the blocker, but still cannot revise, register lifecycle
metadata, deliver, resolve, change runtime/pin state, or unlock another writer.

The contract applies to the v0.4.0 high-impact writers whose exact bindings are
implemented: AI-assisted draft creation, source-fidelity session-evidence
approval, minting, promotion, zettel-edge writes, draft retirement, warning
overrides, human-artifact registry changes, duplicate-object reconciliation,
and approval-integrity repair. Compound and batch mutations remain fail-closed
unless an explicitly documented operation-specific manifest binds the complete
target set. v0.4.10 adds only the bounded local intake/capture exception defined
below; it does not reopen any other compound writer.

The fixed v0.4.0 fail-closed set historically included mint, draft-retirement,
and edge batches; edge and batch reverts; canonical revision write and restore
write; zettel-objet link apply and revert; Notion objet-link conversion; the
relation-candidate accept branch; activity-group membership add, remove, and
both recovery executors; abstract-backfill write, revert, and recovery; title-
remap write, revert, apply recovery, and revert recovery; never-minted draft
discard and restore; and mint/retired-draft receipt reconciliation. In the
current release, only explicitly documented operation-specific modes have been
reopened. Their legacy or unscoped forms remain fixed closed: an approve attempt
returns `compound_exact_human_approval_binding_required` before any private
target read or mutation.

That v0.4.0 blocker also historically covered project update/collision mutation
and bytecode repair; standalone AI scratch cleanup; credential lifecycle
selection; saved-view write/revert; private objet source-metadata write;
identity reconciliation; legacy-coordination cleanup; archive migration and
revert; markup normalization apply/revert/recovery; Principal
register/unregister; objet-capture enable/revoke/reenable, general
selection/capture, and batch; external import; source registration; ownership
transfer; object-storage mutation; Notion recovery; external-locator mutation;
source-intake batch; quarantine decisions; and delegation. Except for the
explicit operation-specific modes documented below, those routes still have no
current exact-human writer binding. Their approval branches fail before private
archive, project, input, credential, or target reads and before provider calls,
mutation, or receipt publication. Historical receipts do not reactivate them.

Operation-specific exceptions do not reopen those general routes. v0.4.7 added
receipt-bound local recovery modes for the exact locator, title, link, edge,
and capture effects documented in the capability matrix; every legacy form
remains closed. v0.4.9 added one exact create-only `source-intake-record`
writer. v0.4.10 separately opens
only bounded 1–1,000 item `source-intake-batch` and its generated local
`objet-capture-batch` handoff. Intake uses one exact manifest, native decision,
durable checkpoints, same-claim resume, and independent verification. Capture
requires a second native decision and accepts only the authenticated upstream
claim, checkpoint chain, final receipt, current receipts and bytes, and same
archive identity. A partial capture requires a fresh exact dry-run and new
decision; automatic retry and same-claim resume remain unavailable. Provider
mutation and every unscoped legacy approval remain closed. Their parser
allowlists and exact evidence contracts are the authority.

v0.4.12 upgrades the already-open operation-specific single
`zettel-objet-link` apply with generation-bound authority. The current SQLite
projection, exact target row,
unique zet and Objet identities, manifest descriptor, stable file evidence, and
one generation remain bound through planning, approval, and apply. An exact
existing link returns deterministic `already_present` before approval and
without a durable write. A missing or stale projection fails before approval or
canonical mutation. Once a supported indexed writer begins, it must either seal
the exact same-generation delta or leave that generation dirty and report
`archive_index_rebuild_required`; ambiguous partial effects are never reported
as success.

v0.4.13 keeps the same human boundary for exact emergency object-storage
preservation. WOM verifies canonical setup evidence, the complete local source
set, content-addressed targets, conditional create semantics, provider call
budget, HEAD plus complete GET rehash, durable resume ledger, and terminal
receipts. The person sees the plain effect and chooses run or cancel; they do
not count objects, compare hashes, or inspect internal identifiers. The
approval grants no overwrite, remote deletion, conflict merge, formal adoption,
or whole-archive backup claim.

v0.4.14 improves the information shown at that boundary without weakening it.
An operation may derive a short local-only filename, title, gist, object role,
or relation endpoint from current bytes already covered by the exact plan. The
clue is optional display context, not approval authority. If optional prose
contains a path, URL, email address, credential/token shape, provider locator,
private UUID/compact source id, unsafe control characters, or cannot be tied to
the current plan, WOM omits that prose and may fall back to a safe local
identity. Unsafe optional prose does not block an otherwise valid exact
operation. A required identity with one of those private shapes instead fails
closed before the native dialog, so a secret is never exchanged for
availability. Conversely, displaying a clue never repairs a stale plan or
authorizes a different target.

v0.4.15 adds two narrow interruption rules without turning a lock or old receipt
into new authority. First, `project-version-update --resume` validates the live
lock, reopens the authenticated sealed plan, reconstructs the unchanged exact
update context, and accepts only one authenticated, checkpoint-valid existing
`started` or `succeeded` claim. It requires no caller-supplied `--target`,
`--transaction-ref`, `--approval-id`, or `--reviewed-by` and displays no second
native decision. A zero-claim transaction cancels its scaffold only when the
durable transaction is proven untouched preapproval, after which a fresh
approval is required. Zero claims for an approved or indeterminate transaction,
ambiguous candidates, forged evidence, context drift, journal drift, or
checkpoint drift fail before another project write. Second,
while that update remains locked, only exact-approved
`operator-feedback-compose --intent create` may append a new feedback body and
body receipt. Revision, supersession, feedback metadata, resolved or delivered
state, and every other writer remain blocked; the exception does not change
`version-update.lock` or any update target.

The v0.4.15 recovery guarantee is bounded to a live `version-update.lock` or
the exact lockless unlock tail while the original transaction directory still
exists. Its first unsupported boundary is after `completed`, once the original
transaction directory has been successfully renamed to a terminal cleanup
tombstone. A tombstone or cleanup proof is not authenticated outcome or cleanup
authority: WOM reports `terminal_cleanup_outcome_unknown` with a nonzero exit
and does not infer success, failure, or cancellation, automatically retry, or
delete that evidence. A full authenticated terminal handoff and terminal
cleanup outcome reconstruction remain a v0.4.16 follow-up.

The current parser-derived inventory is 79 approval-available, 45 fixed-closed,
and 204 not-exposed paths (v0.4.38 adds two approval-gated writers and two other commands; v0.4.36 added `operator-feedback-archive`; v0.4.33
reopened `object-storage-upload`). v0.4.21 added `source-intake-chain` (the
record → selection → capture intake of one staged original under one exact
approval; each step re-verifies the chain claim before it writes, and the
exact-operation receipts of the record and selection steps bind that claim's
reference) and reopened `discard-draft`,
`discard-draft-restore`, `zettel-edge-batch`, `mint-zet-batch`,
`retire-draft-batch`, `revert-batch`, `zet-revision-write` and
`zet-revision-restore-write` through operation-specific exact
human approval; each writer re-derives its plan under its own lock, binds
the fresh plan, and re-authenticates the one-use claim before the first
byte changes. A batch claim is re-authenticated by every item write against
the batch context; an item is written only if its fresh binding is an
approved pair, or its exact target digest is an approved target while only
review context drifted, or its stable identity is approved and the batch
has verified that the only change to its source since the dialog was the
batch's own earlier write.
The fixed-closed set includes 58 compound-approval
migrations and the separately unsupported `operation-control` cancel writer,
whose reason is `operation_cancel_not_supported`. Its status, wait, and
recovery-plan actions remain read-only and available with `--dry-run`.
`zet-revision-restore-proposal-from-snapshot
--approve` and the canonical standalone command path `derive-text capture
--approve` remain fixed closed before private snapshot, target, text, source, or
manifest reads. The paired derived-text handling inside the separately approved
`objet-capture-batch` route is not that command path. Dry-run surfaces and
historical evidence do not grant authority.

## Machine verification binding

WOM, not the person, verifies and binds the content-free evidence for one
operation plan:

- operation kind and exact operation-plan digest;
- body and frontmatter digests when the operation writes a document;
- warning-code set and its digest;
- checklist-code set and its digest;
- target-set digest and other operation-specific safe digests;
- reviewer label and one-use policy.

Full private body text, source locators, provider values, and recognized
credential/secret-like values are never written into an approval request,
popup result, claim, CLI result, MCP result, or log. The native popup may
display one bounded, privacy-filtered,
local-only filename, title, gist, zet/objet identity, role, or relation when
that value comes from current bytes already covered by the validated operation
plan. Unsafe optional clues are omitted without weakening the exact machine
binding or forcing the person to inspect identifiers. Preview values are
ephemeral: they are not copied into
the popup result, public binding, claim, CLI/MCP result, machine details,
receipt, or log.

The person is not asked to count targets, compare digests, or determine whether
the canonical state is complete. A mismatch, drift, or incomplete machine
precondition blocks the writer automatically.

## Human-presence boundary

Dry-run never opens a window and never issues authority. Approval uses a native
Windows modal owned by the foreground WOM invocation. Its primary surface asks
one ordinary-language question: whether to perform the described operation now.
It names the operation's effect, provides one specific action button, and makes
clear that cancellation performs no change. Full digests, machine review codes,
warnings, and the reviewer label remain available under collapsed technical
details and in durable receipts; reading or comparing them is not a human
precondition. The live dialog has no verification checkbox.

The Windows Python runtime must provide a Comctl32 v6 activation context;
`TaskDialogIndirect` is a Comctl32 v6 API according to the
[Microsoft Win32 reference](https://learn.microsoft.com/en-us/windows/win32/api/commctrl/nf-commctrl-taskdialogindirect).
Immediately before constructing the dialog, WOM-kit calls `DllGetVersion` and
requires Comctl32 major version 6 or newer. A missing, older, or unverifiable
activation returns `exact_human_approval_activation_context_required` before
TaskDialog display and before claim creation.

Synthetic UI acceptance is a separate test-only intent and cannot create a
live claim. Unsupported platforms and any modal, focus, cleanup, or result
ambiguity fail closed before a claim is created.

The authority-bearing claim class, claim-minting factory, injectable native
dialog and authentication-key-provider seams, and generic writer-callback
orchestrator are private implementation details. They are absent from the
module public exports and package root. Public callers can construct safe
operation bindings and preview documents, but cannot turn a synthetic decision,
caller key, or arbitrary callback into live authority. Tests reach the private
cores explicitly with synthetic dependencies; that evidence proves invariants,
not a production human confirmation.

The modal proves a local explicit action-button event, not a legal identity,
biometric identity, or protection from a malicious process already controlling
the same desktop session. The reviewer id remains a claimed provenance label;
it does not delegate machine verification work to the person.

Since v0.4.24 a claimed work session may carry a permission mode granted by
one such dialog (`work-session --action set-permission-mode --approve`):
`manual` (every write opens the dialog), `limited` (the operation kinds shown
in that dialog run without one; since v0.4.27 a refused kind is reported by
its position with the fixed grantable and always-dialog name lists, never
by echoing the value) or `allow_all`. A write the mode permits
produces its decision without a dialog, but nothing else changes: the same
one-use claim is minted for the exact plan and target digests, the grant is
re-resolved immediately before the claim is published and fails closed if
the session was paused, handed off, completed or recovered in the meantime
(`exact_human_approval_permission_revoked`), and the claim records
`interactive_intent.mechanism: work_session_permission_mode` instead of a
task-dialog mechanism. Such a claim is not a human-presence proof for that
write; it is the session decision's authority applied to one exact plan,
and results say so (`exact_human_approval.approval_mechanism`,
`live_dialog_shown: false`). Until v0.4.35 an implementer's exclusion list
kept eighteen kinds (project update, remote providers, the session
lifecycle, repairs, overrides) behind the dialog in every mode; the user
had decided otherwise on 2026-09-17 and v0.4.36 (beta letter 168 ⑥)
restores that decision — see the v0.4.36 paragraph below. Credential
writers use the Windows credential native path and are unaffected.
Dry-run still never opens a window and never issues authority.
Since v0.4.32 `set-permission-mode --dry-run` is that dry-run made useful:
mode `permission_mode_preview` returns `would_set`, the fixed
`permission_modes`, `grantable_operations` and `always_dialog_operations`
lists (the latter empty since v0.4.36, with `dialog_only_actions` naming the
grant action), or the refusal code with its positional detail, reading no
session state and echoing no value, so a valid grant request can be
composed before the one dialog is opened; since v0.4.36 the preview also
accepts the approve request as is (`reviewer_claim` ignored) and a refused
shape names `required_keys` / `optional_keys`.

Since v0.4.34 (beta letter 165) a `limited` / `allow_all` grant is
presenter-bound and time-boxed. The approve mints a random presenter secret
before its dialog, so the reviewed plan binds `presenter_sha256`, `granted_at`
and `expires_at` (`grant_hours` 1..24, default 8; one more dialog line names
the box); the secret is returned exactly once in that approve result
(`presenter_token`) and is never stored. A write that presents the three refs
without the matching secret, after the expiry, or under a grant made before
v0.4.34 gets the dialog and says why on its result
(`session_permission_refused.reason_code`: `work_session_presenter_missing`,
`work_session_presenter_mismatch`, `work_session_grant_expired`,
`work_session_grant_legacy_shape`, `work_session_grant_unavailable`,
`work_session_grant_warning_review_required`). The token is a secret of the
granting conversation's process (`WOM_WORK_SESSION_PRESENTER`; an
MCP-hosted approve returns it once the same way and also holds it in the
server process); it binds the grant to whoever received the approve result
— with either transport it is visible once in that conversation — and the
claim's presenter fingerprint, the expiry, the operator's `recover` route
and the draft/intake privacy gates (which refuse a pasted
`WOM_WORK_SESSION_PRESENTER=` line) are the guards against reuse elsewhere. Each grant claim carries the optional key
`session_presenter` (the presenter hash, an HMAC'd fingerprint of the first
non-launcher ancestor process or `unavailable`, how many other
presenters used the session before it, and whether that bounded scan was
truncated); results carry
`exact_human_approval.presenter` and warn
`work_session_second_presenter_observed` when another presenter already used
the grant. Claims written before v0.4.34 stay immutable and count as
`presenter_unknown_count` in the listing. The refs and the token stay in the
granting conversation; another conversation continues a task through
handoff / accept, never by reusing them.

Since v0.4.36 (beta letter 168 ⑥; the 2026-09-17 decision restored) a grant
means what the desktop apps mean by it: `allow_all` covers every operation
kind — project update, remote storage, recovery, deletion, session control,
claim finalization, feedback archival included — and `limited` covers the
kinds chosen at grant time, with no kind keeping a dialog of its own. The
one action the mode never removes is the grant itself
(`work-session --action set-permission-mode --approve`), because a grant
cannot mint, extend or replace itself: that is the single switch the human
flips, and its allow_all line says what it covers. The grant also stands in
for an explicit original re-review. Everything else is unchanged: the same
one-use claim, the presenter binding and the time box, the revocation
routes, and the claim's record of the mechanism.

## One-use claim and durable linkage

There is no separately issued, expiring approval token. After the live dialog
returns an approved decision, the workflow immediately authenticates and
publishes one exclusive durable claim in `started` state. Only then may the
writer run. The writer recomputes its operation-specific binding and asserts
the same current `started` claim immediately before its first mutation. An
existing claim blocks replay.

The workflow is the only finalization owner. A well-formed successful result
changes the claim to `succeeded`. Any non-success after the writer boundary is
entered leaves the claim `started`, including a well-formed `ok: false`
result, a writer exception, a malformed result, process interruption, or
finalization ambiguity. A generic result boolean cannot prove that zero
durable effects occurred: an immutable operation receipt may already exist
even when a later index update or final verification failed. The returned
content-free `approval_claim_reconciliation_required` code means the claim
requires reconciliation and must never be reported as clean failure or
retried automatically. Terminal `failed` is reserved for a path with
verifiable before-mutation proof. Since v0.4.22 `project-version-update
--resume --abandon-started-approval` is that path for one operation: after
human review it finalizes the started claim of the exact transaction context
as `failed` with `operator_abandoned_before_domain_write`, only while the
transaction journal proves that no component write started (journal state
`exact`, verified phases `lock_backlinked` only, live classification
`prewrite_exact`) and only when the claim's own authenticated checkpoint guard
passes; it opens no dialog and writes nothing else. Resume discovery treats
exactly that failure code as absence, so the ordinary claimless cancellation
can release the lock and reservation; a claim that failed for any other reason
still blocks discovery. Since v0.4.22 a failure raised by the approved writer
or the claim broker also carries a content-free `cause_code` and `cause_stage`
(`domain_writer` or `key_or_claim`), restricted to fixed codes of the
project-update and approval families; exception chaining stays `from None`.
Since v0.4.26 the count-first paged target preview (v0.4.20) treats a
page whose native confirmation has not arrived yet as inert rather than
as a failed navigation: every button except cancel is refused until
`TDN_NAVIGATED` is delivered, which Windows 11 posts after the navigation
call returns; a dialog destroyed while a navigation is pending is still
`exact_human_approval_native_call_failed`.
Since v0.4.25 a failure the service raises directly before any result —
resume preflight, reopen, cleanup classification — carries its own fixed
code as `cause_code` and the operation journal's stage as `cause_stage`
(`project-preflight`, `verify-release`, ... or `unknown`), under the same
allowlist plus the `operation_` family.
Since v0.4.30 (beta letter 163) the started claims of every other operation
are visible and closable: `exact-approval-claims` lists the claim store after
MAC verification, projecting only the approval id, operation, status,
timestamps, failure code, approval mechanism, context digest and bound codes
(never the reviewer id, the archive id or a path); and
`exact-approval-claim-finalize` closes reviewed started claims as `failed`
with `operator_closed_started_claim_after_review` through the claim's own
compare-and-swap finalizer, behind a native dialog or (since v0.4.36) the
session grant. The plan refuses a claim younger than
`--min-age-minutes` (default 30; 0 is a bound warning) because a writer may
still be running, a claim that any receipt JSON under `receipts/` or the
version-update receipts names (that write happened; audit it instead), and a
`project_version_update` claim (its abandon path above owns that store); it
runs under the exact-operation writer lock, re-scans receipts inside the
lock, writes one receipt per closed claim under
`receipts/exact-human-approvals/claim-finalize/` (backfilled on the next run
when a crash separated the swap from its receipt) and records that its write
evidence is receipts only. Because the code is not the abandon code, resume
discovery never treats a closed claim as absence. `mint-zet` now checks its
source-fidelity plan digest before the claim exists
(`mint_source_fidelity_plan_sha256_required` / `_mismatch` /
`_not_applicable` in `reason_codes`), so the letter-163 orphan claims are not
created again, and its failure envelope carries the writer's `cause_code` /
`cause_stage` (`mint_preflight` or `domain_writer`).
Since v0.4.31 a `project-version-update` failure that carries no fixed token
still records a cause: the exception family as a fixed literal
(`project_version_update_failure_family_<family>`, `cause_code_source:
exception_family`) with the journal stage, so `result_unavailable` never
travels alone; a broker wrapper keeps its allowlist rule. A dry-run blocked
by an existing transaction adds `existing_transaction` (journal shape only:
status `reserved` / `started` / `in_progress` / `terminal`, verified phase
count, last phase, `abandon_applicable` and the recovery flag that applies),
so the operator no longer loops between `terminal_cleanup_required` and a
refused `--resume`.
Since v0.4.32 (beta letter 164) the finalize scan reads every receipt as a
byte stream (`scan_method: byte_stream_search`, 256 MiB per-file ceiling), so
a malformed or large receipt is searched rather than counted as unreadable;
`oversize_skipped_count` / `oversize_skipped_receipt_paths` are separate from
`unreadable_file_count` / `unreadable_receipt_paths` and both name the
archive-relative file, and only those two make the scan incomplete. The
update preflight's `git_transaction_snapshot` check, when `unavailable` or
`failed`, carries `detail.probes` — each Git probe's name, availability,
exit code and fixed `failure_kind` (`timeout`, `probe_budget_exhausted`,
`output_cap_exceeded`, `launch_failed`, ...) — and never any output.
There is no claim expiry: one workflow invocation consumes the one-use
authority. A later attempt normally requires a new live review. The narrow
v0.4.8 exception is `duplicate-object-reconcile --revert --resume`: when one
authenticated `finalization_pending` revert exists, the command requires the
same `--reviewed-by` value, discovers and reauthenticates that revert's existing
`started` or `succeeded` claim, and opens no second native approval dialog. A
`started` claim resumes the writer idempotently; after the workflow changes the
claim to `succeeded`, terminal finalization completes. An already `succeeded`
claim skips the writer and completes only the finalizer. Both branches preserve
the source journal, perform no second manifest write, and rely on separate
authenticated terminal-compensation evidence to block forward replay. Missing,
forged, or ambiguous pending authority fails closed; production read-only
planning audits existing approval state without creating a key or claim.
If the initial revert stops as `duplicate_object_revert_state_unknown` or
`exact_human_approval_state_unknown`, JSON carries only the fixed
`next_safe_actions` value `rerun_duplicate_revert_resume_with_same_reviewer`
and text gives that same-reviewer resume instruction. The guidance echoes
no approval id, private value, or path. An explicit resume failure remains
fail-closed and does not recursively recommend another resume.

The v0.4.15 project-update exception follows the same no-second-decision
principle but remains operation-specific. WOM derives the target, transaction,
reviewer, and approval context from authenticated durable state, searches the
bound claim store, reauthenticates each bounded candidate, applies the
operation's `started` or `succeeded` checkpoint guard, and proceeds only when
one candidate remains. Candidate discovery returns no identifier or path.
Ordinary recovery derives every identifier from authenticated durable state;
the person never needs to inspect or supply one.

Operation receipts that can safely carry the reference record the content-free
approval envelope directly. Strict legacy source-fidelity receipts use a
separate create-only, HMAC-authenticated approval-link receipt. That link binds
the approval id, operation, plan, target set, and immutable source-operation
receipt digest. Only a verified link with `effect=created` and a matching
authenticated `succeeded` claim upgrades the original operation; an
`already_present_exact` link records a later review without rewriting history.

Public privacy projections expose neither the private duplicate-reconciliation
plan object nor verified source-evidence bytes. CLI and MCP compose those
private engines internally and return only content-free plan/result documents.

Together these records preserve five separate facts:

1. the exact content-free context shown in the native dialog, or bound
   without one under a session permission mode;
2. whether its one-use authority reached `started`, `succeeded`, or `failed`;
3. what the archive operation durably reported;
4. whether a separate approval link proves the original effect was created by
   that claim;
5. since v0.4.24, how the decision was obtained: a live task dialog or the
   work session's permission mode (`interactive_intent.mechanism` in the
   claim; the receipt names the claim).

## Legacy evidence

v0.3 receipts remain readable and immutable. A legacy `reviewed_by` or
affirmation field without the v0.4 exact approval reference is classified as
legacy unbound approval. It is not silently upgraded.

The approval-integrity audit can identify affected evidence without reading or
echoing private content. Quarantine, supplementation, withdrawal, and repair
are append-only operations; they never edit an old receipt or canonical file in
place merely to make the history look cleaner.
