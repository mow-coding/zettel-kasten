# Work-session integration implementation record

Date: 2026-09-05
Status: parallel preparation; not integrated, released, or client-verified

## Scope and sequence

The accepted recovery train remains unchanged. This task-only worktree starts
from the reviewed v0.4.19 candidate while that candidate's complete CI runs.
There is no v0.4.20 integration PR or release yet. Further v0.4.19 corrections
must be incorporated before v0.4.20 integration, and release order is serial.
Private client archives, runtimes, credentials, providers and ledgers are not
modified. Human-readable app and task labels remain in ignored local storage.

## Reuse decisions

1. Add a strict immutable `WorkSessionBinding v1`, not another approval system.
   Its public document contains opaque references, revision, archive identity,
   label digests and its own SHA-256, never human labels or machine identity.
2. New manifests bind an optional explicit extension; absence preserves the
   exact historical canonical bytes, approval and execution digests. Existing
   approvals and checkpoints are never rebuilt with the current session.
   A separate responsibility assignment can authorize future custody, not
   fabricate historical authorship or change old write authority.
3. Reuse the archive-wide OS lock. For new scoped operations, the orchestration
   must wait cancellably, acquire the lock, reobserve the plan and only then
   ask for approval. Pass a held lock to existing domain boundaries rather than
   reacquiring it. A heartbeat or TTL cannot revoke an operating-system lock.
4. Reuse the native approval surface and its sensitive-preview filters. Common
   collection previews are count-first, with read-only pages of twenty rows.
   Detail navigation does not grant approval, and view data is not serialized
   into a public result, error, binding or receipt.
5. Git selection v2 must partition the complete observed change set into
   selected groups and explicit exclusions. Existing `commit --only`, exact
   runner and non-force push remain; excluded staging and worktree bytes must
   survive. Mixed and unattributed changes are not assigned by inference.
6. Inventory cursors bind the whole generation and scope/filter, independently
   of a page digest. A larger hard cap is not a pagination implementation.

## Independent implementation slices

- Binding and legacy manifest/checkpoint compatibility.
- Common local-only target collection and native read-only pagination.
- Git selection partition and excluded-change preservation.
- Root integration: durable private CAS registry, session lifecycle, held-lock
  orchestration, CLI/MCP/context/inventory surfaces and complete user journeys.

Pure contracts and real synthetic filesystem/Git cases precede broader writer
integration. Available writers remain available while the explicit session
start path is added; they are not indiscriminately made fixed-closed.

## Verification required

Two simulated apps must prove handoff, duplicate-claim CAS rejection, concurrent
consistent reads, serialized writes, process-death lock release and exact
resume. Historical v0.4.19 approval bytes must survive v0.4.20 replay unchanged.
Inventory tests must reach every item in a cohort exceeding 6,772, and Git
tests must cover at least sixty mixed-scope changes. Preview fixtures include
1, 2, 5 and 1,000 targets, paging, cancellation, same titles, sensitive text
and target drift. Synthetic success is not a client result.

## Component implementation evidence

- Strict session binding and optional exact-manifest extension preserve golden
  v0.4.19 manifest, approval, checkpoint and result digests when no session is
  present. New bound operations carry the same session digest through execution
  and receipts; old claims are never rebuilt with a new session.
- Registry generations use immutable CAS publication under the existing OS
  lock. Review found and corrected unhashable-input error leaks and a private
  pending-write parent race. Native Windows parent rename is prevented by a
  retained full directory chain; POSIX creation is descriptor-relative. The
  latter race still requires Linux CI, not a Windows-host claim of coverage.
- The target collection rejects deletion/mutation and reentrant approval during
  detail navigation. Optional workflow integration retains old calls unchanged;
  fixed work-session action codes determine human wording without placing
  private labels in the claim. The final approval group passed 91 tests and
  192 subtests using synthetic native input and real authenticated claim files.
- The internal session-decision adapter now appends a registry generation as
  one existing exact-manifest field. It requires the real authenticated claim,
  checks the complete factory context, signs completion evidence, and preserves
  historical generation bytes. Synthetic cancellation, wrong authority, cut
  after publication, same-claim resume and independent old-generation reading
  are tested. This is not yet a public CLI or identifier-free resume workflow.
- The binding/registry/adapter group passed 29 tests with 69 subtests and two
  documented platform/capability skips before independent adversarial review.
  The review found a missing full factory-context comparison. After correction,
  its focused set passed 25 tests with 54 subtests and two host skips, including
  wrong review codes, forged transitions and historical generation tampering.
  Actual completion MAC verification and corrupted-MAC refusal also passed.
  A failed intermediate run exposed missing workflow `ok` projection;
  it was corrected at the adapter, not by changing the common runner contract.
- Git v2 complete partition, content preservation and session source/provenance
  binding are implemented in the domain slice. The latest full run passed thirty
  tests and nineteen subtests; one test reused a stale plan after bundle storage.
  Its fixture ordering was corrected and that case passed independently. A
  separate read-only security review remains in progress.
- That review then reproduced an approval/effect binding failure: mutable
  selected-change convenience rows could diverge from their approved source
  bytes. A synthetic bare-remote case also reproduced the legacy v1 path.
  The correction reuses the existing strict bundle decoder to validate and
  independently freeze execution input; permanent refusal tests and the minimal
  v0.4.19 backport are in progress. Earlier green Git tests did not cover it.
- Lifecycle pagination passed 27 tests with 25 subtests and one host skip,
  including every one of 6,773 real synthetic files. Its CLI now accepts and
  forwards the snapshot cursor; a real parser/service test traverses pages and
  rejects changed generations. AI-artifact complete fate aggregation and cursor
  integration are still in progress. No slice alone closes release acceptance.
- Cancelable session waiting now wraps the same archive-wide OS lock instead of
  adding a competing lease. It emits content-free progress, never steals on TTL,
  and yields only after acquisition for fresh planning before human approval.
  Review of the old lock found that callback exceptions could leave an opened
  attempt descriptor; acquisition now closes owned descriptors on all failures.
  Only documented nonblocking contention errors are retried. Unknown primitive
  failures stop rather than impersonating a busy owner indefinitely.
  Actual contention, cancellation, process death, progress failure and legacy
  exact-operation/session-adapter cases passed thirty tests and nine subtests.
  The real five-second wait produced timely progress. Private holder-name
  display and public CLI integration remain separate unfinished work.
- Independent waiting review added cancellation and root-change injection in the
  acquired-status callback. Rechecking after that callback closed the final gap
  before yielding to a caller. Eleven wait tests passed independently; the
  combined binding/manifest/registry/adapter/wait/preview/pager/workflow group
  then passed 73 tests and 128 subtests with two documented host skips.
- Corrected final Git source passed all 23 v2 tests and 25 subtests. The separate
  v0.4.19 legacy writer and security group passed thirteen tests and two subtests.
  These frozen component results support a development checkpoint, not a public
  v0.4.20 activation or a client recovery claim.

- The complete AI-artifact collector now reuses the existing bounded metadata
  and control-file observation boundary. It aggregates fates across the full
  generation before paginating, detects overlapping roots and changed controls,
  and leaves incomplete counts unknown. Ordinary artifact bodies remain unread.
- Handoff review corrected an incorrect intermediate assumption that the legacy
  public checkpoint writer was unavailable. Its actual CLI approval route is
  still open and must remain compatible. The existing v1 digest and receipt
  bytes are preserved; full-generation diagnostics are additive and explicitly
  not an alternative approval digest. A 1,201-row case exposes the final
  unreviewed artifact despite a 1,000-row display. The legacy truncation blocker
  remains until the new session handoff writer binds the complete generation.
  Ten handoff/public-CLI tests and ten subtests passed in 31.34 seconds before
  the root agent's independent combined rerun. A local-offset timestamp change
  was also reverted to keep the existing same-host digest basis compatible.
- Prepared session plans now have private, bounded, immutable disk payloads.
  Loading replays the exact request against its original predecessor and never
  rebinds it to the latest registry. The payload is not approval authority.
  Independent root review and 24 bundle/operation tests with 19 subtests passed
  in 10.45 seconds; two POSIX-only cases remain for Linux verification.
- Public resume integration uncovered a separate missing input: the original
  approval context, including its reviewer claim, cannot be reconstructed from
  a stored claim hash after process/output loss. The next integration must
  persist the exact private context before approval and verify it on resume,
  rather than inventing a reviewer or weakening the existing claim checks.
- The root agent's combined AI/lifecycle pagination, handoff and prepared-bundle
  run then passed 48 tests and 45 subtests in 95.37 seconds, with two documented
  platform skips. All four release-readiness hygiene checks and resource
  synchronization passed. These are development-checkpoint results only.
- Original-context private storage is now implemented with a separate explicit
  schema while preserving pure payload bytes and APIs. The bundle, operation
  and registry group passed 49 tests and 50 subtests in 47.06 seconds, with
  four documented platform skips. Rehashed reviewer substitution still cannot
  reuse the original authenticated claim; payload hashes are not authority.
- Independent review tightened registry reads to retain ancestors through
  enumeration, current/historical generation reads and final identity checks.
  Windows real rename refusal and handle release were tested. POSIX descriptor
  replacement cases remain for Linux CI. A root review also included pending
  entries in the directory scan limit rather than counting only generations.
- The internal session execution slice now connects lock-before-plan, native
  review, exact context persistence, authenticated claims, the real runner and
  independent terminal verification. It explicitly distinguishes a started
  pre-checkpoint cut, partial checkpoints and succeeded/output-lost completion.
  Review corrected a misleading inherited checkpoint-validation flag in the
  pre-checkpoint branch. No chain is claimed to exist before its first record.
- Common target details now include app/workstream kinds and only already-bound
  private labels. Native drift is checked before key/claim/payload creation;
  omitted sensitive previews retain exact target identity. Execution plus
  preview tests passed 37 tests and 37 subtests in 32.15 seconds. The expanded
  execution-only group passed thirteen tests in 34.38 seconds, including two
  valid but ambiguous claims and rehashed reviewer substitution refusal.
- The first new pre-checkpoint test incorrectly expected the private common-lock
  directory to be absent. Its assertion was narrowed to absent checkpoint and
  final-receipt directories; production behavior was not changed to fit it.
- Genuine child-exit tests are written for three durable boundaries, but their
  run is deliberately queued behind the active v0.4.19 installed-wheel timing
  measurement. These source-checkout tests will not be called public CLI,
  automatic app attachment or installed-wheel session proof.
- After that timing run ended, all three real `os._exit` child journeys passed
  in 79.16 seconds: started-before-checkpoint (26.19 seconds), registry-published
  (26.41 seconds), and succeeded-before-output (26.31 seconds). Every crash child
  exited with the expected test code and every fresh resume child exited zero.
  No second native approval, claim or generation was created. Parent-process
  OS-lock acquisition, original-context/claim authentication, receipt MAC and
  independent target verification passed. Public task-scoped discovery and
  installed-wheel session acceptance remain separate requirements.

Pending integration remains explicit: public work-session CLI and MCP routing,
native production orchestration, durable private plan discovery and automatic
resume, cancellation-aware lock waiting, all-writer ownership enforcement,
consistent read generation across writers, complete-generation handoff approval, responsibility
assignment and session-scoped Git selection assembly. No public v0.4.20 version
bump, PR, tag, wheel or client application has occurred.

## Writer coverage audit and next integration

- Checkpoint `1077042f` committed and pushed the original-context bundle,
  retained reads, internal orchestration and genuine process-loss tests after
  all four readiness gates and resource synchronization passed. The worktree
  was clean before the next integration edits; it is not a v0.4.20 release.
- An independent actual-parser audit found 47 approval-available paths, but
  only 46 represent a writer or local record. `operation-control` exposes an
  approval option for unsupported cancellation. Its availability correction
  belongs to v0.4.19; the working control functions remain read-only.
- The audit separates ten manifest paths, fifteen native/custom paths, one
  mixed link path and twenty existing local-record paths. One broker edit
  cannot cover all of them. The exact names and migration lanes are preserved
  in the [writer coverage decision](../wom-kit/docs/archive-infra-decision-log-2026-09-05-v0420-writer-coverage.md).
- The next narrow guard checks actual claimed ownership under the existing
  held archive lock. It is for fresh domain writes, not historical resume or
  read-only access. It must reject changed app/claim/revision without rejecting
  unrelated generation changes or pretending opaque identity is app attestation.
- That store guard is now implemented. Seventeen focused tests passed under
  independent root execution in 15.51 seconds (36 subtests); the implementer's
  combined registry/binding/operation run passed 42 tests and 90 subtests with
  two documented platform skips. Readiness and resource synchronization passed.
  The first fixture mistakenly read the held Windows byte-range lock using a
  second descriptor; its no-write comparison now checks that lock's identity
  while the actual held-lock verifier checks its bytes. No production guard
  was weakened. Rejected operations preserve files and have fixed-code errors
  with no private exception chain. Historical binding/read/resume behavior is
  unchanged. This prerequisite is not yet all-writer integration.
- Native/custom session composition was examined before implementation. Its
  existing durable approval schemas and historical receipt readers also need
  an explicit compatible transition. A half-wired receipt format was not added
  while the current v0.4.19 CI failures and public integration lanes are open.
- A bounded follow-up audit found approval-free effects outside the 47-path
  inventory: index regeneration, dry-run result files and tracking journals,
  catalog JSONL, and optional Doctor result/progress output. The coverage
  decision now separates approval from actual invocation effects. This is not
  a claim to have audited every approval-unexposed command. Ordinary read-only
  and credential-read paths were checked rather than guessed to be writers.
  Generated artifacts and child records inherit the responsible execution;
  no new human approval is proposed for each automatic diagnostic or index file.

## Public query and invocation-effect integration checkpoint

- After the user's request to continue, development remained split between the
  v0.4.19 candidate and this unreleased v0.4.20 branch. No client runtime,
  archive, credential, provider or feedback status was modified.
- The bounded invocation-effect classifier now distinguishes audited index,
  scratch/output, operation-journal, explicit input-file and credential reads
  from approval availability. Unknown coverage has null effects, not an empty
  read-only claim. Resume/bootstrap intent grants no authority. Independent
  review found the external `--deferred` input read and that classification was
  corrected, including final repeated-option semantics and privacy tests.
- Actual CLI dispatch attaches this shared pure classification before the
  existing runtime guard. Audited persistent writes now require runtime
  alignment even without an approval switch. Ordinary reads and historical
  explicit write/approval/resume guards remain intact. Bootstrap and emergency
  feedback exceptions are unchanged. Session ownership enforcement, all-command
  effect coverage and matching MCP writer enforcement are still pending; this
  integration does not claim to cover every writer.
- `archive work-session` now exposes read-only list/inspect queries. The shared
  service projects one complete registry generation, keeps labels and claim
  tokens private, reports selected and excluded registry counts, and uses the
  existing snapshot pager. It explicitly does not evaluate legacy artifact
  attribution. An actual 6,773-session fixture is returned through four pages
  without truncation or per-row full-registry validation.
- Independent review caught argparse reflecting invalid private values before
  the service's safe error boundary. Work-session's default JSON errors are now
  established before parsing. Invalid action/kind/page-size/format/unknown
  option, malformed ref/cursor and help behavior have regression coverage.
  Read-only queries also continue under another held writer lock, and a registry
  append after capture cannot mix the earlier rows with later summary counts.
- A separate process runs the public CLI entry module against the real synthetic
  registry while the parent holds the writer lock; it returns the same generation
  without changed bytes. This is source-install routing evidence, not a wheel
  install or full session lifecycle proof. The existing content-free no-console
  startup reporter is reused for this command and can be disabled explicitly.
- `archive_work_session` in MCP shares exactly the same query service and cursor
  semantics. Its strict read-only input rejects lifecycle/approval/native/key
  injection, respects the existing root allowlist, and never prints outside the
  JSON-RPC stream. Five real routing/stdio tests and nine subtests passed in
  19.41 seconds; the full MCP regression suite remains separate.
- Before adding MCP/startup integration, root's query/effect/dispatch cohort
  passed 33 tests and 68 subtests in 47.21 seconds. Independent query/privacy
  and dispatch review passed seven tests and fourteen subtests. The initial
  dispatch fixture omitted required low-level runtime result fields; only the
  fixture was corrected, not the production guard. A final combined cohort
  and readiness checks are pending this checkpoint.
- That final combined query/MCP/effect/dispatch/startup and existing capability
  cohort passed 87 tests and 238 subtests in 79.25 seconds. All four readiness
  gates, synchronization of 169 packaged resources and the whitespace check
  passed. Final independent read-only MCP/startup review found no additional
  blocker. Two existing actual MCP initialization/list/error-envelope regression
  tests also passed in 35.87 seconds, followed by all four readiness gates and
  resource synchronization. No release or installed-wheel claim follows from
  these source tests.
- The next public vertical slice is app registration, human-approved work
  creation, one CAS claim and fresh-process continuation with private actor
  context. Lifecycle `--action resume` and original-operation `--resume` must
  stay distinct. Current query help does not advertise those writers yet;
  internal decision/process-loss tests are not substituted for public routing.

## Single-lock public lifecycle preparation

- The existing decision and original-context resume runners now have private
  held-lock composition seams. Their prior entry functions still acquire the
  cancelable archive OS lock once. A facade can therefore re-read its private
  actor context, plan and invoke the broker without trying to acquire the same
  lock twice. A typed, live, same-archive lock is verified before planning or
  loading a resume bundle. This is not a new approval or a public bypass.
- Root ran the new held-lock tests with the existing actual broker/claim/
  registry/receipt/resume cohort: sixteen tests passed in 25.181 seconds.
  Actual create and completed-output-loss resume retain the same lock, claim
  and terminal receipt with one native decision. Foreign, unheld and released
  locks fail before plan/native/claim. Independent source review found no new
  blocker; all four readiness gates and resource synchronization passed.
- The next actor store reuses the registry's opaque client-app reference as
  the installation selector. It does not mint a second app identity or infer
  the current app/session from labels, PID, time or the newest entry. Its
  selected binding/claim and pending original manifest/context remain private
  routing assertions, not current write authority. Fresh writes still require
  the independent claimed-binding guard; original approved work still requires
  its existing authenticated claim and checkpoint.
- Public registration and claim also need a durable original transition intent
  before commit, so output loss cannot create another app or a replacement
  claim. That bootstrap/discovery integration is explicitly pending; internal
  components are not advertised as a completed public lifecycle.
- Review then exposed a narrower routing mistake before public lifecycle
  exposure: an app installation can host two simultaneous tasks. A single
  per-app current selection would let task A adopt task B's otherwise valid
  claim after B updates that selection. Checking the claim alone would not
  detect that the caller had silently switched tasks.
- The private actor key is therefore being corrected to require an explicit
  opaque task-route selector beneath the existing app selector. It is a routing
  key, not a second app identity or authority. Each caller retains its own route,
  including before a new session is created; there is no current/latest default.
  The facade must also check any explicit work-session reference against that
  route. Missing or conflicting task context is not resolved by guessing.
  The earlier per-app design is not being exposed publicly or marked complete.

## Task routing and original registration intent checkpoint

- The actor correction is implemented as an explicit app/task-route pair.
  Its immutable private generations retain the selected session, observed
  binding, private claim and original pending manifest/context pair. Missing
  selectors never select the latest app or task. A fresh write additionally
  compares the caller's explicit session with that route before consulting the
  existing held-lock claimed-binding guard. Two otherwise valid claims cannot
  make a mismatched task selection valid. Actor assertions are not authority.
- Register-app and claim now have bounded private original transition intents.
  The original immutable predecessor, generated reference and request are
  retained before commit. Re-observation after an actual child-process exit
  recognizes that same committed transition without creating another reference
  or generation. Historical success explicitly does not evaluate current claim
  authority. Bootstrap selector discovery and public lifecycle routing remain
  separate unfinished integration work.
- Independent review reproduced a late parent-directory replacement between
  pending-file verification and publication. The common no-replace mover now
  accepts an optional expected parent identity for these same-parent callers;
  both intent and actor publication bind the retained directory to it. Default
  two-argument callers retain their existing behavior. Windows retains handles
  through publication; POSIX uses retained directory descriptors and refuses
  named-path drift. Uncertain bytes are not deleted or blindly retried.
- Root's final combined actor, task-selection, original-intent, parent-move and
  held-execution cohort ran 58 tests in 55.818 seconds: 55 passed and three
  platform/capability-specific tests were skipped. Two skips require Linux and
  one requires host symlink support; these are not cross-platform success
  evidence. Five existing transaction move/terminal-delivery regressions also
  passed in 2.931 seconds. Independent final source and test review found no
  additional blocker. No client or installed-wheel success is claimed.
- The next integration must persist the task's original pending selector before
  approval claim publication, then reconnect create/claim/resume through CLI
  and MCP without requiring a human to copy IDs, hashes or checkpoint names.
  This internal checkpoint is not advertised as a completed public workflow.

## Task-scoped start and terminal-output-loss continuation

- The held decision runner now publishes the original context-bound private
  bundle, invokes an internal pending-selector callback, then revalidates its
  immutable original manifest/context/source/predecessor and held lock before
  the existing broker publishes an approval claim. The native decision and
  key/empty claim-directory preparation may already have happened at this cut;
  that is not a durable approval claim. Callback failure cannot invoke the
  registry writer, and its private exception chain is not exposed.
- Private actor images now distinguish a pending human decision, a pending
  registry transition and the last completed operation selector. Only strict
  typed selectors are retained; no selector is approval or completion proof.
  Pending-to-completed moves in one actor CAS image, so a process exit after
  terminal publication but before stdout cannot lose the original discovery
  pointer. An older caller omitting the optional fields preserves them, and
  an explicit null cannot erase an existing completed selector.
- A regression exposed a real optional-field migration bug: the no-op compare
  indexed a new field absent from an old actor image. The comparison now checks
  key presence, with old-image-to-pending and old-image-to-completed tests.
  The first root integration cohort had one error; its later corrected run is
  recorded separately, not retroactively marked passed.
- Root connected registered-app task creation and original continuation through
  these components. The real broker/runner authenticates original claims and
  verifies immutable target bytes before actor finalization. Completed-only
  continuation cannot execute a started operation even if a local selector
  incorrectly calls it completed. Cancellation saves no actor/claim; new work
  does not silently replace another task's selection or skip a pending registry
  transition to return an older completed result.
- Independent review reproduced copying an original pending approval into a
  different blank task route of the same app. The prior app-only comparison
  could not distinguish it. New task-created manifests now bind the explicit
  route using one additional existing operation-evidence digest; the private
  bundle reconstructs that exact digest during load. The facade compares its
  caller route with the validated original route before resuming. Legacy null
  route source/manifest/bundle/context bytes and their original core resume
  remain unchanged; old approval is never rebound to a current route.
- Root's corrected final lifecycle/ownership cohort passed 19 tests in 51.081
  seconds. It includes a real child exit after terminal actor publication and
  a separate process recovering the same completed receipt without changed
  bytes, cross-route refusal, native-decision actor drift and pending-registry
  fallback refusal. Component cohorts and independent source reviews are
  separate evidence; these source tests do not establish installed-wheel,
  platform-matrix or client completion.
- Remaining integration is explicit: registration selector discovery, claim,
  public CLI/MCP dispatch, all writer-family enforcement and the native
  re-review path when a process stops before an approval claim is recorded.
  A bundle without an authenticated claim does not authorize automatic resume.
  The current refusal is safe but is not a completed user recovery workflow.

## Original app-registration discovery service

- Registration now has two shared service calls: a read-only original preview,
  and apply-or-resume of that same retained selection. Preview generates one
  opaque app reference and binds its original predecessor, label digest and
  plan digest without writing an intent or taking the writer lock. The AI
  harness retains those selectors before apply; a human does not copy them.
- Apply detaches and strictly validates the selection, checks the original
  private label and archive, obtains the existing cancelable OS lock, then
  loads the original intent by its plan digest before considering a new write.
  Only a genuinely missing intent with the same unchanged predecessor can be
  reconstructed using the original app reference. A committed app missing its
  intent is not repaired by manufacturing historical evidence.
- Actual child exits before intent publication, after intent publication and
  after registry commit recover one original app reference, one generation and
  one original intent. Registration remains self-declared routing, not native
  approval, app attestation or claimed-session write authority.
- An initial drift-injection test incorrectly reinjected its change during the
  registry's own replay verification. The fixture was narrowed to one original
  preview boundary; neither production replay nor its success result was
  replaced. Root's final unchanged registration cohort passed ten tests in
  18.142 seconds after the strict schema/key type correction. Independent
  source review found no additional blocker. Public command/tool routing and
  downstream claim integration remain pending.

## Original claim intent and present ownership

- The internal claim composition now connects an explicitly selected, human-
  created task to its original registry claim intent. It verifies the original
  human claim/MAC and immutable receipt, retains the original intent before
  actor pending publication, then commits and separately proves current
  ownership. A completed pointer uses a read-only intent observer; it cannot
  execute a merely pending intent or manufacture a replacement claim.
- Root review found that copying a completed selector into another blank task
  route of the same app could reuse the original claim without proving its
  route. The new claim intent therefore retains an optional original-create
  manifest/context selector. Pending and completed continuation verify the
  original human-bound app, route and session, not only the intent's own hash.
  This is an added check on the existing approval, not a rewritten approval.
- Legacy intents without that optional selector retain their exact bytes,
  hashes and existing low-level reader/observer behavior. The new task facade
  refuses to retroactively attach them to a human-created route. A subsequent
  pause can leave the historical commit verified while current ownership is
  unavailable; these are deliberately different results.
- The final focused seven-test/nine-subtest run passed in 125.32 seconds,
  including real exits after intent, pending actor, registry commit and final
  actor publication, followed by fresh-process continuation. It also covered
  copied routes, missing/rehash-tampered origin, old-byte compatibility, paused
  ownership and read-only refusal of a forged completed pointer. The earlier
  ten-test run preceded the route correction and is not final evidence.
- Root's independent current-claim, paused-ownership and copied-route cases,
  together with the existing original-intent cohort, then passed all nineteen
  tests in 54.635 seconds. No further actionable source finding remained in
  that bounded review; complete supported-platform integration is still needed.
- Public CLI/MCP claim routing, original pre-claim human re-review and all
  writer-family integration remain pending. These internal tests do not mean
  that v0.4.20 has shipped or that the client's operations have completed.

## Original decision re-review after a pre-claim exit

- The internal recovery path now distinguishes an absent authenticated claim
  from an existing, failed, corrupt or ambiguous claim. A genuinely pending
  original bundle without a claim requires another native human decision; it
  does not silently become approved. Existing authenticated work follows its
  original resume path without another approval window.
- Re-review retains the original app, task route, reviewer, manifest, context
  and session. It cannot accept replacement labels or approval identifiers.
  It rechecks the actor, predecessor, immutable target and original bundle
  after the human decision and immediately before claim publication. A change
  stops the operation instead of creating a different approved task.
- Authenticated presence discovery exits its key consumer before invoking the
  broker. Publication checks do not nest another key consumer. This reuses the
  existing claim, runner, receipt and actor finalization rather than adding a
  second approval protocol.
- The final combined regression run passed 26 tests and six subtests in
  70.71 seconds. Root independently reran the twelve re-review tests unchanged:
  all passed in 48.896 seconds. Genuine child exits covered the cut before a
  claim and the cut after its publication, followed by original fresh-process
  continuation. Cancellation, selector/claim drift, failed/corrupt/ambiguous
  evidence and absent/foreign locks were also checked. Independent source
  review found no further actionable issue in this bounded component.
- A pre-existing test forwarding wrapper omitted the optional task-route
  argument; it now forwards keyword arguments unchanged to the real function.
  Its assertions and the production validator were not weakened.
- This is still an internal, unpublished checkpoint. Public command/tool
  routing, installed-wheel journeys and complete writer-family scope coverage
  remain open. No client archive, credential or provider was modified.

## Next public routing boundary (reviewed, not implemented)

- The existing public query remains read-only. A future management tool must
  declare write effects separately; adding mutation to the read-only MCP tool
  would misrepresent its contract. The same action/mode facts must drive CLI
  capability presentation, dispatch and runtime write guards.
- Registration already has a real read-only preview and an original selection
  for apply/resume. Task creation currently has no read-only preview: its
  default native argument means the actual approval dialog, not a dry-run.
  Do not advertise a create preview by passing a null callback to that writer.
- The AI/harness retains app registration selection and an explicit task route
  before mutation. Humans do not copy hashes or manufacture JSON. Missing
  original selection does not authorize choosing a latest app/task or silently
  generating a replacement route for continuation.
- The existing invocation-effect audit assumes its audited dry-run handlers
  require that flag. Session management is action-dependent, so its effect
  classification must precede that generic branch. Registration, claim and
  continuation still require the runtime write guard even without a new human
  approval. An empty effect list here would be a bug, not permission to write.
- Existing cores already acquire the archive writer lock. Public composition
  must reuse their held seams, not acquire the same lock twice. Original
  re-review exposes neither key-provider nor native-test callbacks publicly.
- These are integration constraints, not implemented commands or release
  evidence. Public routing, installed-wheel session journeys and all-writer
  enforcement remain pending after the internal component checkpoint.

## Public management integration checkpoint (not released)

- The user asked to continue the approved recovery train after an apparent
  interruption. Development continued in the two unfinished version worktrees;
  the client archive, runtime, credentials, providers and feedback ledger were
  not changed. v0.4.19 installation acceptance and its remaining CI are a
  separate release gate, not evidence that v0.4.20 has shipped.
- `work_session_service.py` connects registration, native task creation,
  original creation continuation, original pre-claim re-review and original
  claim continuation to the existing authorities. Each mutation takes the
  archive lock once, rechecks the actually loaded runtime while held, and
  calls the existing held implementation. It does not accept public native,
  key-provider, approval-ID or test-context injection.
- `project_runtime.project_write_guard` now has an optional internal CLI-origin
  observation argument. Existing callers retain the exact former forwarding.
  The new service supplies its own loaded module origin separately from the
  actual loaded CLI origin. It does not guess a CLI filename to pass a runtime
  check. Source tests cover the original contract, actual CLI origin, missing
  or substituted origin and runtime drift during lock waiting.
- `work_session_command_modes.py` provides the shared action/flag classifier.
  The CLI, input router, invocation effects and capability display consume it.
  Invalid combinations stop before input dispatch. A same-family read-only
  `request-init` prepares a new opaque routing reference for an explicitly
  registered app; it is neither a create dry-run nor a saved/approved task.
  The AI retains that response before mutation and uses the original selector
  on continuation. No latest-task inference or replacement resume route is
  introduced. Humans are not asked to manufacture IDs or JSON.
- `work_session_command.py` bounds private input to one UTF-8 JSON object,
  rejecting duplicate keys, invalid constants, unexpected fields and oversized
  requests with fixed errors. Labels are accepted through private stdin/MCP
  input, not command-line arguments, and are not copied into public output.
  This input channel is not a credential-entry feature.
- `archive_cli.py` exposes the supported management modes within `work-session`.
  `mcp_server.py` preserves the original read-only query tool and adds a
  separately write-declared management tool. Source integration actually calls
  CLI main and MCP dispatch through registration, native creation, original
  resume, claim and claim resume. Only the synthetic native interaction and
  production key provider are replaced; the original writers, locks, runtime
  checks and receipt validation execute.
- Independent review found that inventory-only capability projection could
  incorrectly advertise action-dependent dry-run support. It now requires a
  trusted parsed action/mode before reporting availability. Follow-up review
  caught both a stale top-level approval-availability field and loss of the
  unevaluated-scope reason in parser-free suggestions. The exact predicate
  result is retained, and namespace-free results remain conservative. The
  regressions check inventory, trusted namespace and suggested-command output.
- The first root public test invocation had a missing test-list delimiter;
  the next exposed an incorrect test call to a nonexistent MCP helper and an
  older all-dry-runs assertion that did not describe action-dependent session
  management. These test wiring errors were corrected, not hidden. A later
  37-test/239-subtest cohort passed in 55.55 seconds, but capability amendments
  were being finalized during that run; it is not the frozen final candidate
  evidence. The frozen seven-module root cohort then passed 59 tests and 303
  subtests in 187.93 seconds, including the public routing-only request-init
  response and original create/resume/claim flow. A separate existing
  capability/query/read-only MCP regression cohort passed 41 tests and 93
  subtests in 75.79 seconds. These are real source handler invocations in one
  process, not installed-wheel or actual MCP-stdio transport acceptance.
- Final bounded source review found no further blocker in the public
  routing/request-init slice. All four release-readiness checks passed, and
  the current 169 packaged resources remained synchronized. The package is
  still the unpublished integration base version; no v0.4.20 release is implied.
- Remaining work includes app installation attachment, lifecycle handoff,
  all-writer session coverage, installed-wheel session journeys, final version
  integration and full supported-platform CI. The source-level public path
  does not establish client recovery, a released feature, or completion of
  v0.4.20 through v0.4.24.

## MCP transport follow-up (audited, not implemented)

- After the public management checkpoint, a bounded source audit identified
  another unfinished transport boundary. The current stdio loop finishes a
  request before reading the next message, discards notification parameters,
  and does not forward progress/cancellation callbacks to session management.
  Passing source handler tests therefore does not prove visible, cancellable
  lock waiting through a real AI client's MCP connection.
- Retain the server's existing negotiated protocol versions. The relevant
  [2025 progress contract](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/progress)
  requires a client-supplied active token and increasing progress values;
  completed requests must stop emitting progress. Unknown total work is not a
  reason to invent a percentage. Arbitrary client labels or cancellation
  reasons must not be copied into logs or progress messages.
- The [stdio contract](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
  requires newline-delimited JSON-RPC on stdout. Stderr may be ignored by the
  client, so writing there does not establish visible progress. A serialized
  stdout write/flush boundary is needed if a managed request runs concurrently
  with the input reader and safe read-only requests.
- The smallest proposed execution model is one managed mutation worker and a
  bounded serialized queue for legacy work. Keep reading cancellation, ping,
  tool listing and the already generation-consistent session query. Do not
  turn arbitrary legacy tools into concurrent writers or replace all their
  existing behavior with a busy error. Overflow must have a fixed no-execution
  result; request IDs and progress tokens need active-connection tracking.
- Existing work-session cancellation is observed during lock waiting and
  immediately before yielding that lock. It is not a promise to interrupt a
  native dialog or roll back an already executing writer. Under the
  [cancellation contract](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation),
  an accepted cancellation may suppress the original response, while an
  uncancellable or completed operation retains its actual result. Never
  relabel a successful receipt as cancelled merely because a late notification
  arrived. The ordinary request ID is not a WOM session or approval identity.
- Fresh-process stdio tests must cover waiting, progress, a concurrent registry
  read, correct/foreign/late cancellation, duplicate IDs/tokens, queue bounds,
  EOF and broken output. A client that does not read stdout can itself block
  the transport; this must not become an unsupported universal cancellation-
  latency guarantee. This follow-up is a required implementation boundary,
  not a feature shipped by the preceding source checkpoint.

## Implemented MCP transport checkpoint

- The audited transport gap is now implemented in `mcp_server.py` and the
  shared `_mcp_session_transport.py`. Legacy-only connections remain inline;
  the first actual management mutation starts one serial worker and a bounded
  FIFO. Only ping, tool listing and the existing generation-consistent session
  query bypass that lane. Native approval, runtime guard and original writers
  remain the same authorities; transport request IDs grant none of them.
- A single queued-only timer and the existing OS-lock wait callbacks send
  increasing progress for a supplied active token. Cancellation removes a
  queued management request immediately or is observed at the original lock
  wait boundary. It does not kill an approval dialog, interrupt an entered
  writer, undo a commit or hide a success when cancellation arrives too late.
- Review corrected active integer/legacy-float ID collisions, ambiguous
  duplicate-ID error responses, malformed metadata masking such collisions,
  and a completion race when the client reused a just-completed progress
  token. Terminal state now precedes identity-checked entry retirement and
  response transmission; old cleanup cannot remove a newer request entry.
  Collision errors that cannot name a unique request use a null ID.
- EOF and broken output stop new queued mutations and cancel existing waits.
  Already entered writes retain original checkpoint/receipt semantics. Stdout
  serialization preserves complete newline-delimited JSON responses and
  notifications. Queue capacity and retained message size are bounded; the
  preexisting unbounded individual input-line parse and stdout backpressure
  are not fixed by this checkpoint. A blocked stdin read is not guaranteed to
  wake immediately when another thread detects broken output.
- Final implementer tests passed 43 tests and 63 subtests in 68.98 seconds;
  the final legacy compatibility cohort passed 15 tests and 30 subtests in
  4.95 seconds. These cohorts overlap and are not added together. Real fresh
  stdio tests exercised the OS lock, queued cancellation, concurrent queries,
  EOF, and original registration resume in another process. The initialized
  connection's first progress arrived in under 0.001 seconds, with observed
  OS-lock and FIFO intervals of 5.078 and 5.063 seconds. This does not measure
  cold application startup or prove how a specific AI app renders progress.
- Independent source review found no further blocker after the terminal
  retirement correction. The reviewer did not rerun the implementer's tests.
  Root verification, exact checkpoint commit and subsequent installed-wheel
  acceptance remain separate results; no public release or client update is
  implied by this source implementation.
- Root independently reran the two new transport/stdio modules unchanged:
  nineteen tests and 25 subtests passed in 14.57 seconds. All four readiness
  checks and the 169-file packaged-resource synchronization also passed.
- Root's separate unchanged public-management and MCP query regression cohort
  passed thirteen tests and 38 subtests in 38.28 seconds. This source checkpoint
  can be backed up independently while v0.4.19 acceptance remains blocked.

## Next bounded integration: pause and paused-session resume

- Source audit confirmed that registry transitions already implement pause,
  resume, handoff, accept, complete and recover. Native exact execution already
  supports the meaningful human actions. The missing layer is durable public
  routing and original-operation replay, not another approval system.
- Integrate pause and paused-session resume first. `--action resume --apply`
  means a new ownership transition for the same paused session, while
  `--action resume --resume` replays that exact earlier operation. Missing or
  mismatched original evidence must not silently create a new claim.
- Reuse archive locking, runtime guards, registry before-hash/revision CAS,
  original create-route evidence and private actor pending/completed selectors.
  Pause needs the current exact claim. Paused-session resume needs exact
  paused state and no current claim; applying the claimed-only guard there
  would incorrectly close a supported transition. New claim generation is
  fixed once in the durable original intent, never repeated on resume.
- Keep public claim secrets, approval capabilities, internal callbacks and
  actor selection creation out of the request. Preserve existing readers and
  approval bytes. Test cuts before actor publication, after registry commit
  and before output, wrong-action replay and cross-app/route/session copies.
  Public handoff, accept, complete and recover remain subsequent work rather
  than being advertised as completed by the narrower pause/resume slice.

## Pause/resume implementation and verification in progress

- The existing private registry intent reader/writer now accepts the exact
  pause and paused-resume shapes. These new actions require the original
  create selector; the historical register/claim format is preserved. Pause
  consumes the current private claim without generating another reference;
  resume binds one generated claim in its original intent for all replays.
- `work_session_state.py` composes those intents with existing actor CAS,
  original create MAC verification, exact route selection and state-specific
  current checks. Fresh apply refuses a pending original operation. Original
  continuation loads only the selected same-action intent. Completed original
  evidence and current state/ownership are reported separately.
- The shared mode classifier, service, CLI and MCP expose only those two new
  actions. Eighteen explicit input combinations are supported across the
  eight public actions; all 256 boolean combinations were checked against an
  independent oracle. Pause/resume accept no native/key/claim capability,
  label, reviewer or replacement approval input. Both fresh and original
  continuation keep the same archive lock and actual runtime guard.
- Root's initial public CLI/MCP and mode cohort passed fifteen tests and
  291 subtests in 52.34 seconds. Its real synthetic journey registered an app,
  created a task with the original synthetic native/key seam, claimed it,
  paused through CLI, replayed pause through MCP, resumed through MCP and
  replayed resume through CLI. Only the original create opened the decision
  seam. Replay preserved registry generation, a new resume used a different
  private claim, wrong-action replay was refused and no private claim or label
  appeared in public output. This is not installed-wheel or client evidence.
- Source review and the dedicated actor/interruption tests remain separate
  gates for this new slice. Existing service tests now also audit the explicit
  new signature, reject malformed modes before waiting, and verify all four
  supported state-write modes stop at cancellation/runtime guards before the
  held state facade. No wider lifecycle or approval capability is opened.
- The consolidated root service/public-mode/MCP/transport cohort passed
  52 tests and 358 subtests in 170.66 seconds. Independent source review found
  no additional blocker in those paths and the held state facade; the separate
  interruption cohort was then completed on the same frozen source.
- The intent cohort passed 24 tests and 54 subtests in 90.78 seconds, followed
  by one added semantic-rehash negative test with four subtests in 9.68 seconds.
  It exercised actual child interruption and a fresh-process replay of the
  same original references. Existing register/claim raw bytes and hashes
  remained compatible. The separate held state-facade cohort passed eleven
  tests and thirteen subtests in 315.02 seconds. It covered original MAC/route,
  actor CAS, pending/committed/output-loss cuts, wrong selectors, changed
  current state and key failure. Actual child exit released the OS lock before
  original-plan continuation; this is not installed automatic discovery proof.
- Final source review reported no additional blocker and did not duplicate
  those tests. All four readiness gates and the 169-file resource check passed.
  This bounded state-transition slice is ready for its own source backup;
  final v0.4.19 integration, installed v0.4.20 acceptance and the remaining
  human lifecycle actions still block a complete v0.4.20 release claim.

## Completion checkpoint

- The same state-transition path now exposes `complete --apply` and original
  `complete --resume`. Completion consumes the exact current claim and records
  completed state, no claim and no active session for the workstream. It does
  not delete archive data, retire artifacts or grant cleanup responsibility.
  Completed replay uses the original evidence without another transition.
- The completion/core cohort passed nine tests and thirty subtests in 226.31
  seconds. A Python-version compatibility review then found three fixture uses
  of `TestCase.enterContext`, unavailable on supported Python 3.10. They were
  replaced with the same patch start/addCleanup lifetime, without changing
  product code or assertions. The existing pause/resume path then passed one
  test and two subtests in 30.47 seconds. The local interpreter is Python 3.12;
  actual Python 3.10 execution remains a CI obligation, not this local result.
- Root's public flow, shared modes and service cohort passed 28 tests and
  361 subtests in 120.82 seconds. The public journey now ends in completion and
  original completion replay, with unchanged archive metadata bytes and no
  exposed private claims. All 288 flag combinations across nine public actions
  are covered by the independent mode oracle. Source-only independent review
  found no further blocker in the completion delta.

## Human handoff origin audit and next contract

- The existing accept transition creates a successor in created state, without
  a claim; it does not directly confer claimed ownership. The required path is
  accept, then ordinary exact claim, then ordinary pause/resume/backup. Current
  create-only origin checks would reject the legitimate accept successor.
- Recover has a related gap: it replaces the claim under its own original
  human decision, but recording that as the last completed human operation
  would obscure the original task-establishment evidence for later state work.
  An establishment selector and a last-operation selector have different jobs.
- Preserve original manifests, context, approval MACs and receipt bytes. Use
  a typed create-or-accept establishment reference in new private records and
  normalize a historical original-create selector only when reading it. Do not
  rewrite old approved evidence or copy a predecessor's create approval onto a
  successor with a different app, session or route. Current ownership, original
  establishment and the last completed operation must each be verified.
- This is a WOM integration decision informed by immutable-event/projection
  distinctions in [Microsoft's event-sourcing guidance](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
  and the separation of entities, activities and agents in
  [W3C PROV-O](https://www.w3.org/TR/prov-o/#description-starting-point-terms).
  Reuse current storage, CAS and approval runners; this does not introduce an
  event-sourcing backend, event broker or claim conformance to a new ontology.
  App handoff does not transfer predecessor artifacts or legacy cleanup
  responsibility by inference. Public human lifecycle integration remains open.

## Establishment implementation and accepted continuation checkpoint

- A typed create-or-accept selector now checks the original bundle, action,
  archive, app, task route, session and context. Its held verification delegates
  to the existing completed-only MAC, receipt and immutable postimage runner.
  It does not execute a started operation, confer a current claim, or turn a
  stored selector into authority. The helper/intent cohort passed 36 tests and
  95 subtests in 131.64 seconds, including a real synthetic create/handoff/
  accept sequence. Independent source review found no additional blocker.
- Actor images may explicitly append an immutable establishment origin in a
  new CAS generation. Omission preserves old absence or the existing pointer;
  recorded origins cannot be removed, substituted or moved to another session.
  Existing raw images, hashes and legacy summaries are unchanged. Actor proof
  remains separate from pointer storage. Eight dedicated/legacy tests and
  twenty subtests passed in 12.67 seconds.
- The held lifecycle shares create and accept establishment while retaining
  create-only compatibility wrappers. A first independently verified terminal
  save records the origin; a completed legacy replay does not migrate its
  bytes. Accept establishes a new unclaimed successor in the same workstream,
  not ownership of predecessor artifacts. Ten existing lifecycle tests passed
  in 39.019 seconds, and five accept/legacy lifecycle tests in 65.660 seconds.
  These include wrong route/action, cancellation, started and pre-terminal
  publication cuts, original resume and unchanged completed evidence.
- Claim and pause/resume/completion use normalized original intent selectors
  plus independently verified original approval and actor CAS. Fresh records
  use the typed origin; old actor/intent/approval bytes remain valid without
  rewriting. Nine tests and twenty subtests passed in 162.73 seconds, covering
  actual accept-to-claim/state work, committed cuts, origin forgery, current
  binding drift and a real recover operation followed by state work with the
  unchanged original establishment. Public recover routing is not yet open.
- Two accept-specific genuine child exit/new-process continuation tests passed
  in 44.03 seconds: after authenticated claim publication before checkpoint,
  and after terminal actor publication. Original claim files, prior succeeded
  bytes, original bundle, registry postimage, receipt, OS lock reacquisition
  and accept-origin MAC were checked independently. An initial test-only
  projection assumed an optional started-branch diagnostic always existed;
  it now preserves absence as null instead of inventing false. These are source
  child-process tests, not installed-wheel or client acceptance evidence.
- Explicit re-review also supports the original accept cut before claim
  publication. Its old default remains create. Existing authenticated claims
  resume without a new native decision; only genuinely absent claim plus the
  original pending operation can reopen its exact unchanged context. Wrong
  action, cancellation and target drift cannot approve replacement data.
  The three new accept tests and twelve existing re-review tests passed in
  99.324 seconds, with source-only independent review finding no blocker.
- Public accept/handoff/recover routing, installed package session journeys
  and all-writer integration remain separate unfinished gates. The outgoing
  handoff facade is being prepared separately; these results do not publish
  it or transfer legacy cleanup responsibility. No private client data changed.
- Root reran the unchanged public CLI/MCP flow, mode matrix and service guards
  against the new origin implementation: 28 tests passed in 138.349 seconds.
  Registration, creation, claim, pause, resume and completion still follow the
  same public routes and original approval; all 288 mode combinations remain
  checked. Independent source review found no additional claim/state blocker.

## Outgoing handoff internal checkpoint

- The outgoing held facade verifies the selected actor's exact current claim,
  original establishment, source app/session/route and target app, then uses
  the existing native broker and before-claim actor publication. The original
  resume follows only that handoff's pending or completed selector. It accepts
  no replacement reviewer, raw claim, key or native implementation inputs.
- Terminal publication separately checks current handoff-pending state with
  no claim and the exact target. If a successor has already accepted, the
  original committed result remains verified but current state is unavailable;
  old ownership is not restored or advertised. Neither artifact ownership nor
  legacy cleanup responsibility is transferred by this operation.
- Ten dedicated tests and five subtests passed in 197.19 seconds, including
  actual process exit after authenticated completion and original continuation
  in a new process, started/pre-checkpoint and terminal publication cuts,
  original receipt preservation, wrong scopes and later-accept separation.
  A further legacy-image test passed in 27.33 seconds: old bytes remain intact
  and verified origin is attached only in a new approved pending CAS image.
  Independent source review found no additional actionable issue.
- This is an internal source checkpoint. Public CLI/MCP routing and explicit
  original native re-review after a handoff pre-claim cut remain unfinished.
  Automatic approval or a successful resume is not inferred from that cut.

## Public human lifecycle integration in progress

- The existing management service, CLI and MCP routing now compose handoff
  and accept through the same mode classifier, runtime guard and held facades.
  Fresh accept takes a new caller-retained task route and explicit predecessor;
  original accept resume/re-review takes only its original app and route.
  Handoff always retains the exact source session and target app. Only fresh
  human decisions accept the private reviewer field; original continuation
  rejects replacement reviewer, target, context and secret inputs.
- Native pre-claim re-review is shared rather than duplicated. The original
  claim scanner must exit its key consumer before the broker can run. Existing
  claim evidence resumes the same selected operation; genuinely absent evidence
  permits only explicit review of that original pending context. Handoff
  preserves committed evidence separately from later current-state changes.
  The shared-core and service cohorts are still being collected.
- Adding the target-app option initially invalidated the strict invocation
  option audit as intended. After reviewing its effects, the exact one-option
  whitelist was updated without weakening the parser comparison. Nine mode and
  grammar tests passed; the independent oracle covers 352 flag combinations
  across eleven actions and exactly twenty-six supported combinations.
- Root's frozen public cohort then passed nineteen tests in 162.802 seconds.
  Actual synthetic CLI/MCP calls covered two registered apps, outgoing handoff,
  original replay, successor acceptance, claim, pause, resume and completion.
  A second journey exercised a genuine pre-claim handoff cut with explicit
  original re-review and a started accept cut with original resume. The old
  public registration/create/claim/state path still passed. Private labels and
  claims were not returned; archive metadata bytes were unchanged. A stale
  outgoing replay after acceptance retained old committed evidence but did not
  claim current handoff state. These are public source dispatch tests, not an
  installed wheel, interactive host UI or private client execution result.

## Public human lifecycle checkpoint validation

- The frozen service slice passed eight new tests plus the existing exported
  signature test in separate focused runs: nine unique tests and 43 subtests.
  One initial test incorrectly blocked the original bundle loader's pure
  manifest reconstruction. The test, not production code, was corrected to
  forbid fresh execution and generated references while preserving exact old
  bundle bytes and the claim set; that selected test then passed.
- Shared original re-review now serves create, accept and handoff. The final
  single cohort passed 24 tests in 311.02 seconds: nine new handoff tests,
  twelve existing create tests and three accept tests. A genuine child exit
  before claim publication followed by original re-review in a fresh process
  passed. Existing started/succeeded records continue through original resume;
  absence, corrupt evidence and ambiguous evidence are not interchangeable.
- Independent cross-review of the shared engine/handoff wrapper and the public
  service found no actionable blocker. Review checked native/key lifetime
  separation, original manifest/context identity, post-click actor/source CAS,
  strict public arguments, and old committed evidence versus current ownership.
  Readiness's four gates, 169-file resource synchronization and diff checks
  passed. These results supplement, not replace, the public 19-test source
  cohort above. Test counts from overlapping earlier runs are not added again.
- This checkpoint exposes handoff and acceptance through existing CLI/MCP
  entrypoints. It does not yet complete recovery routing, all-writer session
  binding, session Git selection, installed-wheel acceptance or v0.4.20 release.
  Existing client data and the public v0.4.18 release remain unchanged.

## Same-session human recovery continuation (2026-09-06 local time)

- The public handoff/accept checkpoint was committed and pushed as `bc4ce2d4`;
  the exact remote branch ref matched and that worktree was clean before this
  next slice. The unfinished integration worktree was preserved, not deleted.
- The existing human `recover` transition now has an actor-aware held facade.
  It keeps the exact app, task route and existing session. An authentic original
  create/accept decision is verified before a new native approval; stale actor
  claims are historical routing, not current authority. The current claimed,
  active same-app registry generation is bound separately. No heartbeat age,
  PID, path inference or nonhuman recovery intent grants ownership.
- Pending and terminal actor CAS reuse original bundles and the shared
  re-review engine. The exact newly generated claim is verified against the
  prepared postimage and current registry. Old evidence is not rewritten, and
  an already committed recovery whose current state later changed cannot write
  an actor or claim present ownership on replay.
- CLI/MCP/service expose fresh approval, original resume and explicit original
  pre-claim re-review with the same strict request shape and existing runtime
  guard/OS lock. There are 29 valid combinations among 384 tested action/flag
  combinations. No new top-level command, public native/key/context/claim input,
  target-app recovery, or replacement resume reviewer was added.
- Thirteen unique held-facade tests passed in focused groups, including actual
  create/accept-origin continuation and a child-process exit followed by fresh
  original re-review and terminal replay. An initial new-test oracle treated
  authenticated failed and malformed claim evidence as the same error phase;
  the test was corrected to the existing earlier origin-scanner rejection,
  while retaining no-native/no-write byte checks. Product code was not changed
  for that oracle. Independent source review found no actionable blocker.
- Review suggested making the actor-drift no-write assertion explicit. The
  final test also checks unchanged registry SHA and claim reference; that one
  selected test passed in 13.420 seconds, with no production change.
- Root's five public recovery tests plus seven mode tests passed together:
  12 tests in 116.987 seconds. These include real CLI/MCP recovery, original
  replay, pause/resume/complete, pre-claim and started interruption, and actual
  runtime-pin mismatch before either held facade. The existing public
  management/handoff and service signature cohort passed 13 tests in 157.722
  seconds. Four readiness checks and 169-resource synchronization passed.
- Public-route independent review caught a stale MCP description that still
  said recover was unsupported although its schema and handler allowed it.
  The description now states the supported approval/original modes and exact
  app/task/session, no-target and no-replacement-reviewer contract. A focused
  description regression was added; this was a real discovery/help mismatch,
  not dismissed because the execution tests passed.
- The final description/grammar/mode cohort passed ten tests in 0.260 seconds
  (excluding import/startup). Independent review confirmed that the description
  finding was closed, with no remaining actionable public-route issue.
- This is still source integration, not an installed v0.4.20 or client result.
  All-writer attribution, session-scoped artifacts/Git and the final installed
  journey remain open. Public v0.4.19 acceptance is separately blocked; no
  private client or global launcher was changed.

## Session backup and artifact provenance: reuse before expansion

- The user requested continuation after an apparent interruption. Work resumed
  from the clean, remotely preserved `1ad9e489` checkpoint. Client data, runtime,
  credentials and feedback state remain outside this development session.
- Independent audits confirmed that both artifact inventories already paginate
  their complete collections; the 1,000/2,000 values are page limits, not total
  truncation. Existing tests cover 6,773 items. Actual scan/control budgets can
  still produce incomplete coverage, which must not become a zero count.
- Git selection v2 already enforces a complete disjoint selected/excluded
  partition and preserves excluded changes while using non-force push and
  remote-ref verification. These components will be reused, not recreated.
- The missing link is authenticated producer provenance plus current actor
  authority. A session digest in a caller's selection declaration is neither
  proof of document creation nor a current claim. General source-record/mint
  outputs still lack that connection. Artifact names, timestamps and historical
  references must not be used to infer it.
- The next bounded internal implementation verifies new work-session exact
  completion receipts using their original contexts, immutable generations and
  completion MACs. Only complete authenticated receipt bytes that are absent
  from HEAD and absent or identical in the index may enter automatic selection.
  Generic documents, malformed evidence and other sessions remain excluded.
  This first adapter proves receipt provenance and selection eligibility only;
  it has not executed a backup and proves no canonical document ownership.
- Completion receipts belong under `receipts/ops/exact-operations`; private
  checkpoints, actor context and labels stay ignored. Custom ignore rules are
  respected without force-add. Historical bindings retain their own revision;
  fresh writer entry will check the current actor/claim separately.
- Public backup orchestration still needs the same held lock before approval,
  post-click revalidation and durable original-operation discovery/resume.
  Calling the existing post-approval-lock writer from a held facade would nest
  locks, so a deliberate internal seam is required. The original v1 context and
  approval contract must remain unchanged.
- Later artifact scope will join explicit producer evidence into the existing
  full projection and snapshot-bound cursor. Responsibility assignment remains
  separate from creator provenance. No new artifact scanner or guessed
  ownership index was authorized by these findings.

## Authenticated receipt selection checkpoint

- Added internal `work_session_git_provenance.py` with the existing Git planner's
  complete private snapshot, completed-only original claim/MAC verification and
  selection-v2 partition validator. It reads real whole receipt bytes and
  preserves the original binding revision, even after the session later changes.
  Current claimant authority is deliberately not supplied by that history.
- Source classification never invokes the writer, repairs missing evidence or
  creates a credential. Tests compare actual claim/checkpoint/receipt bytes
  before and after classification. Other sessions and unknown changes remain
  explicit exclusions; a zero eligible count is not an empty archive or a
  completed backup. Custom ignored paths are not force-added.
- Receipt verification has an explicit 128-candidate work budget. Exceeding it
  rejects the entire classification; it does not truncate a page or hide a
  remainder. This limit is not general artifact pagination or scale acceptance.
- Ten actual synthetic Git/evidence tests passed in 251.100 seconds. Cases
  include two sessions, later revision, forged/corrupt/noncanonical receipts,
  changed MAC and started claims, index disagreement, existing HEAD paths,
  ignore rules, and snapshot drift. An initial test assumed only two unknown
  fixture files; its oracle now covers the full actual snapshot while separately
  asserting the two generic document refs remain unknown. No product behavior
  changed for that correction.
- The fixed-code error constructor now accepts only exact strings before set
  membership. Its separate hostile/invalid-input test passed. Eleven unique
  tests passed in those focused runs; repeated tests are not added to the count.
- Root review caught Python 3.10 incompatibility in the new fixture's use of
  `TestCase.enterContext`. Explicit `ExitStack` plus `addCleanup` now preserves
  LIFO cleanup without that Python 3.11 API. The two-session test passed again
  in 22.442 seconds on Python 3.12. Independent rereview found no other such API
  and both files passed 3.10 grammar parsing. Only Python 3.12 is locally
  installed; this does not replace actual supported-version CI.
- Independent source review found no remaining blocking issue. Readiness's
  four gates, 169-resource synchronization and diff checks passed. Public
  CLI/MCP backup, current actor guard, held writer/original resume and general
  document producers remain separate integration work. No backup was performed
  by this adapter and no client data was changed.
- The next bounded change reuses an already held archive lock in the existing
  Git exact writer while leaving its historical public route unchanged. That
  seam alone will not be declared a complete session backup workflow; original
  context discovery, actor authority and producer provenance must still meet.

## Same-lock Git execution checkpoint

- The private held Git entrypoint now verifies a real same-archive lock before
  native review, reuses it through claim creation and exact application, and
  returns without closing it. The caller still owns release. A missing,
  unheld, released or foreign lock is rejected rather than replaced.
- The existing public executor keeps its original signature and native-before-
  default-lock behavior. Approval context, manifests, private bundle codecs,
  receipt/result composition and legacy resume were not changed. This internal
  seam alone grants no current actor or document provenance authority.
- Seven new held tests passed in 136.622 seconds. Real temporary Git and local
  bare remotes exercised commit/push/requery, original v1 bytes, bound-v2
  exclusions, a competing lock through native/application/return, and native-
  time lock/selection/prepared-data drift. Eleven existing writer tests passed
  in 254.648 seconds and 23 existing v2 tests in 416.327 seconds, including
  crash/resume, large grouping and staged/remote drift.
- Independent review identified a private exception-chain leak in the new
  lock guard: `raise ... from None` hides display but retains `__context__`.
  The fixed error is now raised outside the handler. A new path-bearing OS/
  nested-lock error test verifies empty cause/context; it passed, followed by
  the real successful held-Git path again in 27.806 seconds. There are 42 unique
  tests across these cohorts, not 43 from double-counting that rerun.
- Final independent review confirmed the privacy fix with no remaining
  blocking issue. Python 3.10 grammar/API checks passed, but native 3.10
  execution remains a future integration-CI requirement. Four readiness gates,
  169-resource synchronization and diff checks passed.
- The remaining public workflow requires durable original Git context and
  actor routing. Full planner recapture is appropriate before preparation but
  not after its own ignored context/claim files are written: doing so creates
  an approval-digest cycle. Reuse the existing exact source checks and separate
  actor/provenance revalidation, without reconstructing an approved manifest.
  Terminal commit evidence must also be distinguished from new completion
  receipts that legitimately make the worktree dirty after push.
- No client project or real provider was changed. These are developer-side
  source/fixture results, not a public session-backup release or client receipt.

## Standard references

- [OpenTelemetry service identity](https://opentelemetry.io/docs/specs/semconv/resource/service/)
  informs opaque instance identity; WOM does not claim this is app attestation.
- [CPython filesystem operations](https://docs.python.org/3.12/library/os.html#os.replace)
  distinguish atomic replacement from synchronization and safe target binding.
- [Windows TaskDialogIndirect](https://learn.microsoft.com/en-us/windows/win32/api/commctrl/nf-commctrl-taskdialogindirect)
  provides the existing native dialog and callback model; detail navigation is
  separate from the original approval button.
- [CPython nonblocking locks](https://docs.python.org/3.12/library/fcntl.html)
  and [Microsoft nonblocking byte locks](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/locking?view=msvc-170)
  identify waitable contention separately from invalid handles or arguments.
