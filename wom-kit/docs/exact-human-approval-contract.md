# Exact Human Approval Contract

Status: v0.4.15 authenticated project-update resume and create-only incident-report preservation; v0.4.0 one-use authority baseline preserved

## Purpose

A caller-supplied actor label or command-line affirmation does not prove that a
human reviewed exact archive changes. v0.4.0 therefore separates ordinary
operator intent from one-use exact human approval.

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

The current parser-derived inventory is 47 approval-available, 67 fixed-closed,
and 201 not-exposed paths. `zet-revision-restore-proposal-from-snapshot
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
retried automatically. Terminal `failed` is reserved for a future path with
verifiable before-mutation proof.
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

Together these records preserve four separate facts:

1. the exact content-free context shown in the native dialog;
2. whether its one-use authority reached `started`, `succeeded`, or `failed`;
3. what the archive operation durably reported;
4. whether a separate approval link proves the original effect was created by
   that claim.

## Legacy evidence

v0.3 receipts remain readable and immutable. A legacy `reviewed_by` or
affirmation field without the v0.4 exact approval reference is classified as
legacy unbound approval. It is not silently upgraded.

The approval-integrity audit can identify affected evidence without reading or
echoing private content. Quarantine, supplementation, withdrawal, and repair
are append-only operations; they never edit an old receipt or canonical file in
place merely to make the history look cleaner.
