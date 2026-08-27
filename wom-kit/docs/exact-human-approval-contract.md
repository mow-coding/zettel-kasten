# Exact Human Approval Contract

Status: v0.4.10 bounded batch intake/capture authority plus prior exact-operation boundaries; v0.4.0 one-use authority baseline preserved

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

The fixed v0.4.0 fail-closed set includes mint, draft-retirement, and edge
batches; edge and batch reverts; canonical revision write and restore write;
zettel-objet link apply and revert; Notion objet-link conversion; the
relation-candidate accept branch; activity-group membership add, remove, and
both recovery executors; abstract-backfill write, revert, and recovery; title-
remap write, revert, apply recovery, and revert recovery; never-minted draft
discard and restore; and mint/retired-draft receipt reconciliation. Their
plans, previews, and audits remain available, but an approve attempt returns
`compound_exact_human_approval_binding_required` before any private target read
or mutation.

That fixed blocker also covers project update/collision mutation and bytecode
repair; standalone AI scratch cleanup; credential lifecycle selection;
saved-view write/revert; private objet source-metadata write; identity
reconciliation; legacy-coordination cleanup; archive migration and revert;
markup normalization apply/revert/recovery; Principal register/unregister;
objet-capture enable/revoke/reenable, general selection/capture, and batch;
external import; source registration; ownership transfer; object-storage
mutation; Notion recovery; external-locator mutation; source-intake
batch; quarantine decisions; and delegation. These routes have no
v0.4 exact-human writer binding. Their approval branches fail before private
archive, project, input, credential, or target reads and before provider calls,
mutation, or receipt publication. Historical receipts do not reactivate them.

Operation-specific exceptions do not reopen those general routes. v0.4.9 added
one exact create-only `source-intake-record` writer. v0.4.10 separately opens
only bounded 1–1,000 item `source-intake-batch` and its generated local
`objet-capture-batch` handoff. Intake uses one exact manifest, native decision,
durable checkpoints, same-claim resume, and independent verification. Capture
requires a second native decision and accepts only the authenticated upstream
claim, checkpoint chain, final receipt, current receipts and bytes, and same
archive identity. A partial capture requires a fresh exact dry-run and new
decision; automatic retry and same-claim resume remain unavailable. Provider
mutation and every unscoped legacy approval remain closed. Their parser
allowlists and exact evidence contracts are the authority.

## Machine verification binding

WOM, not the person, verifies and binds the content-free evidence for one
operation plan:

- operation kind and exact operation-plan digest;
- body and frontmatter digests when the operation writes a document;
- warning-code set and its digest;
- checklist-code set and its digest;
- target-set digest and other operation-specific safe digests;
- reviewer label and one-use policy.

Private body text, titles, labels, paths, source locators, provider values, and
credentials are never written into an approval request, popup result, claim,
CLI result, MCP result, or log.

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
