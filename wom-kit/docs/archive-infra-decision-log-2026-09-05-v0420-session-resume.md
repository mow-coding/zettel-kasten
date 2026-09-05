# Session resume preserves original human authority

## Context

Session ownership preparation must not invalidate older approvals or require a
person to reconstruct hashes, reviewer strings and checkpoint identifiers after
a process exits. A stored manifest alone is not evidence that anyone approved
it. The existing broker authenticates claims against the full original context.

## Decisions

1. Reuse the existing archive OS lock, native broker, authenticated claim,
   exact runner, checkpoint and terminal receipt. Do not add a competing lease
   or a new approval system.
2. Acquire the archive lock before planning and native review. A waiting caller
   can cancel; acquisition requires fresh state observation before approval.
3. Save the exact prepared payload and original content-free context in the
   ignored private registry after approval and before claim publication. The
   reviewer claim remains a claim, not Windows identity attestation. Preserve
   the original values; do not infer them from hashes or new session metadata.
4. Pure prepared payloads retain their old byte format. A missing context is a
   blocker, not permission to upgrade or overwrite an existing payload. Even a
   self-consistently rehashed context must match its existing authenticated claim.
5. Resume a started claim with a real checkpoint through the existing strict
   checkpoint validator. A reachable started-before-first-checkpoint cut is a
   different branch: require the exact current predecessor, absent immutable
   target and absent final receipt before beginning the original exact runner.
   Report this preimage evidence separately; do not claim a nonexistent chain
   was validated or manufacture old success evidence.
6. An authenticated succeeded claim never reopens the domain writer. Recheck
   the existing terminal receipt, claim MAC and immutable target independently.
   Later unrelated registry generations do not change historical authority.
7. Retain ancestor directories throughout registry and historical generation
   reads. On POSIX read relative to the retained descriptor; on Windows retain
   the existing no-delete-sharing handles. Unavailable observations are not
   empty registries. Count pending entries toward bounded directory scans too.
8. Show app/workstream labels only through the existing memory-only target
   collection. Persist opaque references and label digests in public evidence,
   not duplicate titles in receipts or JSON. Reobserve the exact registry before
   approval; sensitive previews may be omitted without losing target identity.
9. One app installation can host simultaneous tasks. Require an explicit
   opaque task route beneath the existing app selector, never a newest/current
   default. New task decisions bind its archive/app/route digest in existing
   manifest evidence. Legacy approvals keep their original bytes and resume
   path; do not add a current route to an old approval.
10. Keep original pending and last-completed selectors in the same private
    actor CAS image. After verified completion, atomically retain the original
    completed pointer while releasing the pending gate. Output loss after that
    save must still find the same receipt. Optional-field omission by old
    callers preserves completion pointers; explicit null cannot erase them.
11. A completed pointer is not proof. Completed-only resume rejects a started
    claim and can only verify an original succeeded claim, terminal MAC,
    receipt and immutable target. Pending registry work cannot fall through to
    an older completed human decision. Fresh writes independently check the
    caller's selected session and actual current claimed binding.
12. Persist the pending selector after the native decision and original bundle
    save, before authenticated claim publication. Revalidate the original
    source/context/manifest/predecessor and OS lock after the callback. A cut
    before claim publication is not approved work; a native re-review path is
    required before this branch can become a complete public recovery flow.

## Original claim composition amendment

New task claims retain their original human-create manifest/context selector
inside the existing private registry intent. Pending and completed continuation
authenticate that original receipt and its app, task route and session. A
private selector or a rehashed intent alone is not sufficient. Completed
continuation is read-only and must separately prove current claimed ownership;
a later pause does not erase the verified historical commit.

Old intents without the optional origin retain their exact bytes and existing
low-level observation. The task facade does not retroactively assign them an
original human route. A copied completed selector from another route is refused.
No new approval protocol, claim token input or duplicate claim is introduced.

## Original pre-claim re-review amendment

An explicitly requested re-review may redisplay only the original pending
human decision whose authenticated claim is genuinely absent. Failed, corrupt
or ambiguous claims are blockers, not absence. An existing claim uses original
resume and does not reopen the approval window. No new manifest, reviewer,
label, task route or approval identifier is accepted by this recovery path.

Presence discovery must finish its key consumer before the broker is invoked.
After the native decision, rescan for claims and revalidate the original
actor, bundle, predecessor and target before entering claim publication. Keep
publication checks independent of nested key consumers. Continue through the
existing runner and terminal verification, preserving original authority.

The source-level re-review cohort passed twelve tests in an independent root
run, including genuine pre-claim and post-claim process exits. Public routing
and the installed package journey remain separate, unfinished acceptance gates.

## Evidence and remaining integration

The combined execution/preview group passed 37 tests and 37 subtests. After
additional original-reviewer substitution and ambiguous-claim cases, all 13
execution tests passed. These use real claims, filesystem writes, checkpoints
and MAC verification with synthetic native/key input only. All three genuine
child-exit/fresh-process-resume tests then passed in 79.16 seconds, covering
started-before-checkpoint, post-publication and succeeded-before-output cuts.
The parent independently reacquired the OS lock and verified the original
claim, terminal MAC and disk generation. POSIX-specific
retained-parent race tests still require Linux execution.

The later task lifecycle/ownership integration passed 19 tests in 51.081
seconds, including an actual exit after final actor save and a new process
recovering its original completed receipt without rewriting bytes. Independent
review found and helped correct same-app cross-route pointer substitution and
old-image optional-field migration. These are source-level regression results,
not installed-wheel or client completion evidence.

This is an internal integration checkpoint, not a public release. Public CLI
and MCP routing, app installation attachment, task-scoped payload discovery,
all-writer scope enforcement and installed-wheel session journeys remain open.
No private client archive, credential, provider or feedback ledger was changed.

See [integration minutes](../../meeting-minutes/2026-09-05-v0420-work-session-integration.md).

## Public management routing amendment

Keep the existing query tool read-only and expose supported mutations through
a separately write-declared MCP tool and the existing CLI command family.
Reuse a single pure action/mode classifier for dispatch, effects and
availability. Parser inventory alone cannot establish action-dependent mode
availability. A trusted predicate result must not be lost in another display
field, and unevaluated scope is not a completed negative mode check.

Private requests are bounded structured stdin/MCP input; labels are not argv
or output. Mutation facades wait for the existing OS lock once and check the
actual loaded runtime while held before invoking the existing held writer.
The service module and the loaded CLI origin are distinct observations, not
interchangeable filenames. Old guard callers retain their original behavior.

A routing-only request initialization may return a new opaque task route for
an explicitly registered app without writing the archive or creating an
approval. The AI must retain that response before create and reuse the same
selector for resume. Missing original evidence does not authorize silently
initializing a replacement request. Do not advertise this preparation as a
create preview or write authority.

These changes are an unpublished source integration checkpoint. Installed
session workflows, later lifecycle actions, all-writer coverage and actual
client outcomes remain separate gates.

## State transitions and establishment distinction

Pause, paused-session resume and completion reuse original private intents,
the exact actor selection, current-state guards and existing claim/MAC checks.
New state transitions use apply; original resume never creates a replacement
intent or claim. Completion closes only session metadata, not archive data or
cleanup responsibility. Public and held-runner tests are recorded separately
in the integration minutes, and do not replace installed or client acceptance.

Before exposing human handoff, accept and recover, separate the original
task-establishment selector from the last completed operation. Accept creates
a successor needing its own claim; its legitimate establishment is accept,
not the predecessor's create. Recover changes the current claim but does not
replace establishment history. The new integration must verify each original
human operation with the existing completed-only runner and exact app/session/
route, while preserving old manifests, context, receipts and raw hashes.

Use typed create-or-accept origins in new private records and read-normalize
old original-create references without in-place evidence migration. Preserve
current storage and CAS, not a new event store. This planned origin contract
does not yet make the human lifecycle commands publicly available, transfer
old artifact ownership or assign legacy cleanup responsibility.

## Establishment implementation boundary

The typed origin and old-selector read normalization are implemented in the
existing private storage. Original create/accept identity and completed human
MAC/receipt verification are shared by claim and state transitions. Actor CAS
preserves an explicitly recorded origin independently of the latest completed
operation; omitted old fields keep their original bytes and interpretation.

Create-only compatibility entrypoints remain create-only. The shared internal
accept path requires its own exact successor approval and records created state
without a claim. Started, succeeded and pre-claim re-review paths retain their
separate authority requirements. Missing claim evidence never silently grants
approval; old completed evidence is not migrated during read-only replay.

Source and genuine child-process results are recorded in the integration
minutes. Public human lifecycle routing, installed-wheel acceptance and private
client execution remain incomplete; this contract is not a release claim.

## Public handoff and acceptance integration

The public service now connects explicit human handoff and successor acceptance,
including original resume and explicit original re-review. CLI and MCP share
one exact mode classifier and bounded private request contract. Handoff binds
both apps and the outgoing session; acceptance binds the explicit predecessor
on a new caller-retained task route. Original accept continuation selects that
route's saved decision rather than accepting a replacement predecessor.

Extract the existing claim-presence/native re-review protocol into one private
engine shared by create, accept and handoff. Only genuinely absent claim
evidence on the pending original permits another native review of the same
context. Existing started/succeeded claims use original execution; corrupt or
ambiguous evidence is not absence. Publication rechecks the exact current actor
and source after review. A completed handoff followed by acceptance keeps the
old verified commitment but does not report current ownership or write again.

Public native/key injection remains unavailable. All five service entrypoints
reuse the existing runtime guard and one OS lock. This source checkpoint and
its process-loss tests do not establish installed-wheel or client completion;
recovery, all-writer binding and session Git backup remain unfinished.

## Same-session human recovery

Connect existing human recover through the same public service and actor CAS.
Keep the original create/accept identity immutable. A stale actor is not proof
of a currently owned claim: authenticate its explicit original route/session,
bind the current same-app claimed active registry preimage, then obtain an
exact human decision under the existing OS lock. Never infer recovery authority
from time or PID, and do not treat recover as a cross-app handoff.

Resume and explicit pre-claim re-review select only the saved recover. Reuse the
shared claim-presence/native protocol and verify the exact generated claim in
the committed postimage and current registry before terminal actor CAS. If the
current state changed after the original commitment, report those facts
separately; do not restore an old actor or manufacture present authority.

Source/public/process-loss tests are recorded in the integration minutes.
All-writer binding, session Git backup, installed acceptance and client outcomes
remain separate unfinished gates.

## Scoped Git original-operation composition checkpoint

The existing Git reconciliation CLI now composes current app/task/session
selection with the existing wait/runtime guard, native broker, exact writer,
signed terminal storage and independent remote anchor checks. Fresh scope binds
authenticated establishment context and the complete selected/excluded change
partition. Original continuation selects the saved actor intent, never a new
planner, reviewer, provider configuration or approval identifier. A completed
original is verified without signing or committing it again. Verified historical
commitment remains separate from current ownership and completion.

This first lane admits only whole, newly created authenticated completion
receipts. It does not grant whole-document Git authority from a field-scoped
change, infer responsibility for legacy files, or prove all artifacts backed up.
An absent original claim remains explicit pre-claim re-review acceptance work;
corrupt claim evidence must not be interpreted as absence.

Mutation workers retain the existing archive lock until actual settlement,
including cancellation. Public progress uses a separate hidden, content-free
observer with bounded startup and cleanup ownership; observation is never write
authority. This avoids arbitrary callbacks while mutation is in flight without
silencing progress. The integration minutes record source and actual synthetic
Git tests, final observer cancellation regressions and their different source
snapshots. Installed acceptance, full writer coverage and client results remain
unfinished; no released or recovered-client claim follows from this checkpoint.

## Explicit original Git review after pre-claim interruption

The next source slice connects `--approve --review-original` to the same retained
Git decision when its authenticated claim is genuinely absent. Keep the saved
context, manifest, reviewer, scope and pending actor unchanged. Authenticate
establishment and producer proofs and the exact preimage around native review;
only successful terminal verification performs the pending-to-completed CAS.
Existing claims take original resume; failed, corrupt or ambiguous claims are
not absence, and a completed actor cannot gain a replacement missing approval.

Extract the existing authenticated scanner once. Normal fresh execution keeps
its signature, order and bytes; the separate private original-review entry uses
one closed internal review kind to require same-key absence immediately before
publishing the claim. No provider callback intervenes between that scan and
publication, and no second key consumer, signature model or public authority
parameter is added. This closes the key-provider-entry insertion window without
changing the ordinary existing approval path. Source test outcomes and installed
acceptance limits are recorded separately in the integration minutes.

Original review requires the existing archive authentication key; unlike fresh
approval, it must not generate a key when evidence is unavailable. The existing
lifecycle original-review helper uses this same private broker entry. Its
previous typed context, exact preimage and held publication checks remain;
historical approval and context bytes are never rewritten by the migration.

## Scoped intake and retained original input

Extend the existing `source-intake-batch` command only when explicit app/task/
session references select the new lane. Existing calls keep the legacy path.
The AI prepares the private request and retains opaque routing; the person is
not asked to write JSON, copy hashes, find receipts or select checkpoints.

Fresh work binds original request bytes, exact source/receipt evidence and the
current claimed session in a new exact manifest. A bounded private retained
context is input evidence, never ownership or approval authority. On resume,
load that original context and authenticate its claim; do not accept a new
request, reviewer, digest, approval ID or replacement scope. Current ownership
and the original establishment remain independently checked before domain
mutations. A blocked domain write may still leave recoverable private control
evidence; it must not be described as zero filesystem activity.

Completed replay verifies the original authenticated common result and actual
output bytes even when the caller JSON and source inputs no longer exist.
It does not replan, rehash missing sources, sign another receipt or enter the
writer. Historical completion, present ownership and final actor publication
are reported as separate facts. A missing original approval remains a blocker
in this first slice; explicit original re-review is not yet available here.

The intake effect creates source-intake evidence and a prepared capture request,
not preserved source bytes. Do not claim a downstream capture or scoped Git
backup until its authenticated producer/consumer path is connected and tested.
The existing legacy capture route must not be opened to a new scope merely by
accepting another schema name. Reuse the same approval key consumer when a
historical proof is needed inside another active approval; never nest providers.

The CLI emits closed counts, booleans and digests, not request item names or
private retained payloads. It distinguishes preview readiness from completion
and read-only domain effects from interrupted writes. Callback-window findings,
the actual synthetic public journey and final regression results belong in the
integration minutes; this decision is not a release or client-recovery claim.

## Historical intake completion as downstream evidence

Share one strict completion-evidence expression with the existing intake
verifier; keep that verifier's own succeeded-context checks unchanged. Expose
separate private data-image and authenticated-completion types. A hash-matching
image is not approval. The authenticated historical reader verifies original
establishment, original succeeded MAC, complete checkpoint/final chain and
every approved output, without requiring current actor ownership or missing
caller/source inputs. An active same-archive Git or capture claim can audit the
old terminal MAC using its existing key context; it does not gain intake write
authority. The downstream concrete writer still checks its own approval and
current ownership. Standalone reads use a noncreating provider and refuse
claim-directory or selected-evidence changes across the provider boundary.

Use retained contexts only as bounded discovery hints for intake Git output
classification. Preserve the human-decision producer; never infer ownership
from source-shaped filenames or parsed JSON. Commit only exact whole new
outputs, and keep other-session/unknown changes excluded with complete coverage.
Historical v1 Git scope bytes are not upgraded. The new v2 scope records the
original intake context and exact output membership; original continuation
reauthenticates that stored set without new inventory or selection. A common
receipt already in Git may prove remaining new outputs from its original batch.

Count prepared capture requests as outputs, not receipts or preserved source
files. Keep artifact/source-custody completion false. Joined public source
tests, installed acceptance, full writer coverage and release are separate
stages; the integration minutes state which stage was actually exercised.

## One metadata receipt remains one operation

Bind the existing single source-intake record to its own retained exact inputs
and explicit actor route. Do not impersonate a batch or manufacture its capture
request. Share the original session/origin guards, exact broker, checkpoints and
atomic no-replace primitives. A reconstructed ready plan is not proof that a
destination is absent or a caller still owns the session; check those facts at
the held publication boundary. Preserve old unbound manifest/context bytes.

Keep the original reviewed JSON verbatim in ignored private control storage.
Fresh approval revalidates that input; original continuation uses the retained
original and authenticates its original claim. A missing claim does not trigger
new approval automatically. Succeeded output verification and current-owner
completion acknowledgement are distinct. Unknown destination bytes and stale
pending files are never overwritten, inferred as success, or silently removed.

CLI and MCP call the same single-record service. The asynchronous MCP lane
reuses the existing scheduler and cancellation boundary. Its heartbeat may say
that it is waiting for another observed status; it must not invent processed
items. Metadata receipt completion is neither source capture nor Git backup
producer authentication. Those downstream contracts remain separate work.

## Single-record proof shares the historical engine, not batch identity

Extend the same closed historical reader for record and batch originals.
Select only known family codecs, exact evidence expressions and strict output
verifiers; never accept caller-supplied modules or authentication callbacks.
Distinct exact record image/authenticated types prevent a batch consumer from
silently accepting an unrelated operation. Preserve every original approval,
scope digest, batch proof byte and v1 Git scope.

The explicit single-record Git producer proves just its original source
receipt and whole common completion file. Reuse the existing v2 proof shape,
selective writer and original-resume pipeline. Two fixed context inventories
remain bounded hints, not authorship or approval; a stored Git continuation
uses retained producer references rather than rediscovering either directory.
Unknown, other-session and conflicting authenticated attribution cannot be
silently committed. Source/capture custody is still outside this proof.

Tests must authenticate actual original record and establishment MACs, refuse
wrong-family and linked outputs, and execute real selective commit/push with
interruption and identifier-free original continuation. Source-level evidence,
installed-wheel acceptance and client execution remain separate milestones.

## Git continuation across CLI and MCP

Expose the existing session-scoped Git service as `git_backup_reconcile_plan`;
do not add another CLI command, writer, approval protocol or selection format.
Fresh preview/apply needs the explicit claimed route. Original resume and
original re-review accept the retained app/task route and optional same-session
assertion, never replacement inputs, reviewer, approval IDs or expected hashes.
Reject forbidden parameters by presence, including null/default values.

Only the MCP presentation layer projects the result to fixed states, booleans,
bounded counts and digests. Keep the original CLI result and private authority
checks unchanged. Verified original commits, current ownership, independent
remote observations and actor completion remain distinct facts. A late owner
failure cannot erase a verified historical commit; eligible or empty selection
is not backup completion. Never forward nested operation evidence, Git anchor
documents, private paths or retained original locators to MCP output.

All four Git modes use the existing serial management lane and archive lock.
Select the progress family from a fixed tool name, not caller arguments. Reuse
the closed Git event projector without invoking arbitrary mapping/document
callbacks or the CLI stderr observer. A heartbeat repeats only the last
observed stage and valid count pairs; it does not invent work or completion.
Read-only requests can still use the audited bypass. Queue bounds, request/token
identity checks and the cooperative waiting cancellation boundary remain.
Do not terminate an entered Git process or dismiss a native approval dialog.

The [MCP progress specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/progress)
requires an active supplied token and monotonically increasing notifications;
the existing sequence denotes notifications, while message counts denote
observed work. Stop progress at the terminal boundary. The
[MCP cancellation specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation)
allows completion/cancellation races and operations that cannot be cancelled.
Suppress only an observed, known wait-cancel failure, never an already verified
original Git result. This is not the separate MCP task extension.

Verify grammar/privacy/scheduling separately from actual cross-surface Git
journeys. Real commit/push/ref/blob and excluded-change checks use isolated
synthetic archives and local bare remotes; in-process JSON-RPC tests are not
stdio, installed-wheel or client acceptance. Preserve those evidence labels.
