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

## Original Git approval composition: bounded next steps

- Independent read-only review confirmed three remaining gaps: the Git private
  bundle lacks the original reviewer/context and is persisted after claim;
  public legacy resume asks for identifiers and a pre-existing checkpoint;
  current Git completion does not authenticate the actual terminal commit OIDs.
  The already implemented held executor does not solve these by itself.
- Split the immediate internal work along existing contracts: one immutable
  original-context wrapper reusing the Git codec/context factory; one typed
  in-memory v2 selection adapter reusing the entire current preparation body;
  and explicit actor pending/completed operation kinds. None is public Git
  authority or a newly completed end-to-end backup feature.
- The memory selection avoids changing ignored inventory merely to pass JSON
  between the complete provenance snapshot and exact preparation. The existing
  planner, relation, full partition and source/hash validation remain mandatory.
  No extra temporary selection file or alternate planning algorithm is needed.
- Audit found lifecycle, recovery, handoff and re-review currently interpret
  every pending manifest/context pair as a human session decision. Before a Git
  pending kind can be stored, these consumers must explicitly refuse that kind,
  not reinterpret its approval as another operation. Narrow refusal guards are
  authorized; no new Git dispatch is exposed by this intermediate change.
- The wrapper at this stage preserves original context only: current Git
  manifests do not yet bind task route/current claim/producer-proof scope.
  Later composition must bind and revalidate those digests within operation
  evidence. An unsigned wrapper or a historical session binding is not current
  claimant authority. Legacy approvals must retain their original bytes.
- The later terminal path must authenticate ordered commit OIDs, the exact
  remote binding and common final receipt SHA. A cut after common receipt but
  before domain receipt requires original finalization, not a fresh Git run.
  Historical commit proof and current HEAD/remote/actor alignment remain
  separate. These requirements are not marked implemented by the three seams.
- Development remains synthetic and isolated. Actual client installation,
  provider operations, credentials, feedback status and shared PATH are outside
  this development session's write scope.

## Original context storage checkpoint

- `work_session_git_bundle.py` now retains the full existing Git prepared codec
  and exact original approval context under the private ignored control root.
  Loading reconstructs both through the original codec/context factory. Views
  are detached; no reviewer, route, claim or later binding is inferred.
- Publication uses the existing no-replace move, parent identity binding,
  pending-file fsync, directory durability and stable read-back machinery. An
  identical repeat confirms the original without rewriting it. Conflicting,
  corrupted, oversized, linked or legacy context-less evidence is not repaired
  or upgraded into authority. Error text and exception chains are content-free.
- The implementer passed ten synthetic Git preparation/storage tests in
  110.575 seconds and a separate pending/published read-back tamper test in
  11.806 seconds. Root review then identified a repeated-save race: its first
  load preceded the durability flush, but it did not read the file again after
  that flush. The repeat now reloads through the safe held reader and compares
  the originally requested exact bytes before returning.
- A fully valid alternate-reviewer context substituted during that flush is
  rejected and preserved, never overwritten. This new case plus the original
  successful repeat passed in 26.413 seconds. There are twelve unique passing
  cases, not thirteen from double-counting the repeated normal case.
- Independent review of the final read-back correction found no blocking
  issue. The wrapper remains storage only: no approval authentication, current
  task ownership, Git execution, automatic resume or terminal completion is
  claimed. Those still require exact route evidence and authenticated domain
  completion composition.

## In-memory Git selection checkpoint

- A private immutable typed v2 selection now enters the existing preparation
  algorithm without writing JSON into the archive. The public file-based
  signature remains unchanged. Both routes re-use the same full Git planner,
  exact plan comparison, remote relation and live selected/excluded partition
  validation. An in-memory object is not an ownership or approval capability.
- The declared syntax is validated before any planner callback; immutable bytes
  are captured before that callback can mutate the caller's object. Actual
  completeness is checked against the fresh real plan, not the declared refs.
  Invalid, uninitialized or malformed inputs use fixed content-free errors.
- Nine new tests passed: three pure cases in 0.002 seconds and six real
  synthetic-Git cases in 118.172 seconds. Equivalent file/typed preparations
  produced identical private bundles, manifests and approval contexts; no
  ignored selection file was created. Actual source/ref and partition drift
  were rejected, and the existing held writer still committed/pushed only the
  selected changes in its synthetic fixture.
- Eleven original writer tests passed in 261.052 seconds; 23 existing v2 tests
  passed in 413.345 seconds. These are 43 distinct tests. Source-body AST
  comparison confirms the shared original algorithm differs only at selection
  acquisition. Independent root review found no blocking issue; Python 3.10
  grammar checks passed under 3.12, not as native 3.10 execution.
- Four readiness gates and 169-resource synchronization passed at this source
  checkpoint. Session route evidence, original auto-resume and authenticated
  terminal Git receipts remain necessary before public workflow integration.

## Typed original-operation routing checkpoint

- Actor context now has a typed `PendingOperationSelector`; explicit Git
  pending/completed selectors carry only kind and original manifest/context
  digests. They are routing metadata, not approval or completion proof. An
  omitted kind preserves the old human-session digest-pair meaning and exact
  old JSON; clearing pending also clears its kind. The old untyped pair API
  cannot silently relabel a saved Git pending operation as human.
- Lifecycle, recovery, handoff and re-review now refuse explicit Git originals
  before opening the human-session bundle, key consumer, approval or writer.
  Post-callback paths also require the expected human kind. Claim/state/fresh
  execution already block an outstanding digest pair and retain that behavior.
  This change does not yet open a Git dispatch or automatic backup resume.
- Seven new tests passed in 11.938 seconds, including eight original public
  API paths for both pending and completed Git selectors. The final-source
  lifecycle plus new tests passed seventeen cases in 65.351 seconds after the
  final post-callback guard. Root independently reviewed all five source diffs
  and found no blocking issue.
- The nine-module existing regression cohort finished 111 tests in 804.172
  seconds, with one skip and no failures. Together with the seven new tests:
  118 distinct discovered, 117 passed and one skipped. The seventeen-test
  rerun is overlapping evidence, not seventeen additional tests. Python 3.10
  syntax and diff checks passed; actual runtime here is Windows Python 3.12.
- Readiness's four checks and 169-resource synchronization passed for the
  frozen source checkpoint. The branch remains unreleased, with final scope/
  authenticated completion/auto-resume composition still outstanding.

## Current dispatch-coverage correction

- The user requested continuation after an apparent interruption. Work resumed
  from the existing candidates, preserving all unfinished workspaces and the
  read-only client boundary. The v0.4.19 exact candidate remains on its own CI;
  follow-on source work does not cancel or alter that candidate.
- A fresh independent parser/dispatch audit distinguishes 316 canonical paths
  from 259 aliases. Of 48 approval-available canonical paths, `work-session`
  is publicly connected and `operation-control` is unsupported/non-mutating.
  The other 46 legacy domain/local-record paths still need session composition.
  Eleven conditional modes must keep their original limits. No availability
  percentage or general all-writer coverage is claimed.
- The existing writer-coverage decision log now records this exact gap and
  the common integration sequence. The all-writer session coverage gate and
  responsibility assignment remain unimplemented. Neither a requirements table
  nor the receipt-only Git adapter proves ownership of real Zet/document
  changes. Approval-free index/artifact/journal effects are a separate axis.
- These are public source facts, not copied client letters, private archive
  evidence, provider credentials or client recovery results.

## Exact scoped Git evidence and original terminal checkpoint

- Added immutable private session scope over the existing v2 selection: actual
  task route, actor/registry preimages, claim reference, binding and whole-file
  receipt producer facts. Public manifest evidence contains bounded counts and
  digests only. The existing Git bundle reconstructs the scope and manifest;
  omitted legacy extensions retain their original bytes and public API.
- These source/hash/partition checks are not receipt MAC authentication or
  current ownership. Until the held owned-session workflow is composed, every
  scoped execution entry refuses before native review, key access or Git. Its
  public plan truthfully says scope context is required. No existing unscoped
  supported writer is closed.
- Independent review caught a private-core pre-UI gap: a subclass or stripped
  scope retaining scoped evidence could bypass the narrow entry guard. The
  guard now requires the exact type and the private core reconstructs/freeze-
  validates before native review. Both malformed cases across all five routes
  make zero UI/key/Git calls. Final-source scope/context, legacy writer/held,
  v2 selection and typed-selection cohorts passed 74 distinct cases (23 in
  245.908 seconds, 19 in 423.697, 23 in 440.349 and nine in 136.804).
- Added the original Git terminal authentication codec. It signs only with the
  real ready original started claim and a matching authenticated common final
  receipt/checkpoint set. It binds ordered OIDs, the exact approved URL/ref
  digest and common result, not only a set of commit names. Read-only historical
  authentication does not create evidence or upgrade unsigned legacy receipts.
- Root review required input detachment before authentication callbacks. The
  returned authenticated wrapper now retains separately frozen original bytes
  even if the caller mutates its record during a nested audit. Twelve final
  tests passed in 27.620 seconds, using real claims/MACs/common receipts; their
  synthetic OIDs are assertions, not a remote Git test.
- Added a separate read-only Git anchor observer that reuses the existing
  immutable commit parent/message/path/blob verification and approved remote
  query. It does not rerun a dirty-tree planner or invalidate old commit proof
  because HEAD or an unrelated file later changes. Remote advancement is a
  mismatch, not an inferred preservation success. Runtime/config/metadata and
  held-lock checks remain required. No approval/completion authority is granted.
- Its first real-Git fixture accidentally used ordinary Git newline conversion,
  correctly failing exact blob comparison. The fixture now stages with explicit
  no-conversion settings; the product validator was not relaxed. Independent
  review also moved the separate current-HEAD hint after the slow remote query.
  Six final tests passed in 104.900 seconds, including real later/concurrent
  commits while the original remote proof remains intact. Together these
  foundation cohorts have 92 distinct passing tests, not a public workflow run.
- Python 3.10 grammar checks passed under Windows Python 3.12; actual 3.10
  execution remains integration-CI work. Four readiness/privacy checks and
  169-resource synchronization passed. Original terminal publication, current
  actor/post-review authentication, fresh execution and identifier-free Git
  continuation still need composition before exposing the new public route.
  Public long operations must connect progress/cancellation to these bounded
  existing observers. No client or actual provider operation was performed.

## Public scoped Git routing and cancellation review checkpoint

- Extended the existing `git-backup-reconcile-plan` route with app/task/session
  selectors and identifier-free original `--resume`. No additional top-level
  command or duplicate backup action was added. Fresh scoped work computes its
  selection internally; original continuation accepts neither a replacement
  plan nor a reviewer, provider override or approval identifier. Explicit
  stored-credential choice remains necessary for fresh authenticated backup.
- The original unscoped missing-plan parser error still exits with status two
  and redacted CLI JSON. An initial regression caught its accidental move to
  handler validation; the parser condition was restored rather than weakening
  the established test. Eleven conditional command paths are now asserted,
  including the exact limited `work-session` namespace predicate; no writer
  availability policy was broadened by changing the count.
- The common public adapter enters the existing wait/runtime/held-lock path.
  Errors disclose fixed codes and distinguish no domain entry from unknown
  effects after entry. An independently verified historical original commit
  remains a separate fact if current ownership or completion fails. Independent
  review caught that this fact was initially discarded, and that keyboard
  interruption could bypass fixed JSON. Both were corrected; arbitrary progress
  callbacks cannot impersonate a trusted domain verification exception.
- Final public/legacy/status/availability regression cohort: 55 tests passed in
  23.735 seconds on Windows Python 3.12. Eight adapter/CLI tests in that cohort
  exercise real shared locking with a stub domain; they are not proof of actual
  Git execution through the installed public entrypoint. The actual held Git
  workflow has separate synthetic execution tests still under final review.
- Review of that workflow found a distinct outstanding issue: a heartbeat
  worker could outlive cancellation and the archive lock. Mutation-worker
  settlement and concrete scope checks must pass deterministic interruption
  tests before the workflow is considered ready. Fixing public error text is
  not sufficient. Progress during long mutations remains an explicit requirement.
- This checkpoint is unmerged development work. No client archive, project
  runtime, credential, provider or global PATH tool was changed. The separate
  v0.4.19 candidate has passed its installed Windows workflow gate, but its
  final platform CI is still running; release success is not assumed.

### Follow-on observed results

- All fourteen v0.4.19 candidate checks, including the required aggregate,
  subsequently passed at exact head `344c37746ff3c3a11656bea75272ea03bb2dc2ef`.
  PR #97 merged to `591bb3ce131d32d89c3e9e269da581e9c3aec5a8`; its first parent
  is the expected preceding main and its second parent is that reviewed head.
  Candidate and merge trees are identical. The main release gate also passed.
  Exact-merge wheel reconstruction/installation is now running separately;
  no tag, public v0.4.19 release or client success is asserted by this checkpoint.
- The new source public workflow test passed once in 124.759 seconds: actual
  CLI parsing, shared held runtime guard, session workflow, broker, signed
  storage and Git commit/push all ran against an isolated synthetic archive.
  Only native input, synthetic key, handoff and bare-remote transport seams
  came from the established fixture. Independent local/remote OIDs match,
  unselected document bytes remain untouched, and original `--resume` needs
  neither an approval identifier nor another native review. Fresh planner,
  writer, signature and actor rewrite are forbidden on that completed tail.
  This closes the source adapter-to-domain seam, not installed-wheel, real
  provider, full artifact attribution or remaining crash/progress coverage.

## Exact-merge local installation budget and follow-on review

- The unmodified v0.4.19 exact-merge wheel checker exhausted its local
  1,200-second aggregate runtime-journey deadline. This attempt is incomplete,
  not a passing installation or evidence that original resume failed in the
  product. Initial update (432.780 s), healthy no-op (119.609 s), next preview,
  both source/ref drift refusals, repair preparation (266.062 s), and the
  interruption preimage/checkpoint checks passed. Original resume began at
  1,084.655 s, leaving about 115 s; its same-tree hosted run alone took about
  189 s, with independent revalidation and launcher/Doctor checks still after it.
- Repeating the unchanged aggregate budget would discard another successful
  prefix without testing the missing tail. Independent read review confirmed
  there is no complete per-scenario substitute: the initial-only mode explicitly
  denies full journey completion, and the private repair worker alone is not
  the sequential contract. A local-only supplemental wrapper therefore runs
  the full unmodified checker with a 2,400-second aggregate runtime-child and
  matching cumulative phase-observation envelope. It intercepts exactly one
  original 1,200-second call and restores both temporary overrides afterward.
- All domain validators, original 600-second repair subprocess bounds,
  Doctor's 180-second limit, first-status/tick bounds, named timing-field limits,
  strict result shape, privacy, process containment and required CI remain
  unchanged. The separate supplemental JSON records the prior failed attempt,
  exact merge/tree/checker/journey identities, actual interpreter and new local
  budget. Even a later supplemental success must not be described as passing
  the original local 1,200-second gate. No product or released source was edited.
  At this checkpoint the supplemental run is still active and no tag or release
  has been published. Required candidate and exact-merge main CI already passed.
- The scoped Git worker now defers console cancellation only while a real
  worker may still run, settles against the explicit operation-done event, and
  restores original handlers with bounded attempts. Definitely-unstarted work,
  startup/return interruption, repeated cancellation and permanent restoration
  failure have explicit tests. Nine focused cases passed in 0.054 seconds;
  the final 26-case real-workflow cohort is still running. No independent
  reviewer test run is falsely counted as an execution.
- The CLI progress owner is being integrated separately from operation
  authority: a fixed-data hidden child can report during mutation without
  running arbitrary callbacks in that interval. Embedded non-fd output is
  explicitly synchronous; unavailable live observation stops before dispatch.
  Startup option-name detection gives only the new scoped route early status
  without changing the unscoped default. Public observation lifecycle errors
  preserve a verified historical original separately from current completion.
  Public/legacy/startup-boundary cohort: 28 tests passed in 8.118 seconds.
  Observer backpressure/cancellation review and the combined live-mutation
  heartbeat test are not yet complete.

## Frozen scoped workflow and observer checkpoint

- The final unchanged scoped workflow passed all 26 tests in 1,194.320 seconds:
  17 actual synthetic-Git cases, six worker settlement tests and three pure
  scope/privacy tests. This includes explicit synthetic key-provider forwarding,
  post-remote-observation terminal tampering, original completed continuation,
  partial/common-final tails and two-session selection. The independent source
  review is separate evidence, not another test execution.
- The source public CLI workflow then passed in 135.987 seconds, including a
  deliberately delayed 11.2-second push, live stderr observation, exact committed
  receipt-only paths and independent local/bare-remote OID comparison. The warm
  command emitted first status within two seconds and heartbeat gaps within ten;
  this is not cold startup, installed-wheel or real provider credential proof.
  The observer at that run preceded the final cancellation-only changes below.
- A combined observer/public/startup/Windows-process/status/availability/legacy
  cohort passed 99 tests in 83.466 seconds. This observer snapshot preceded the
  final cleanup-window correction; it must not be relabeled as a rerun of that
  newer source. The final observer's own complete 15-test cohort passed in
  23.253 seconds, including actual Windows SIGINT and SIGBREAK at both child
  publication and cleanup-thread-construction boundaries. Independent read
  review closed the original cleanup-cancellation finding at that final source.
- Observer setup and cleanup share one local, bounded signal lease. It restores
  original handlers and settles owned child/sender/reader resources before
  cancellation is propagated. It grants no write or completion authority.
  Product files are `work_session_git_progress.py`,
  `git_backup_session_command.py`, `work_session_git_workflow.py`, the existing
  CLI routes and common Git writer, plus their focused tests. The existing
  Git backup guide now explicitly describes this unreleased receipt-only lane,
  original-resume contract, excluded document changes and remaining missing-claim
  original re-review work. No full-document backup completion is claimed.
- The completed v0.4.19 implementation worktree and local branch were removed
  only after clean-status, exact merge ancestry and remote-branch deletion checks.
  Its 171 ignored files were verified generated bytecode/test caches, with no
  unclassified files; they are reproducible. All code remains in main and the
  remote. The unfinished v0.4.20 worktree and exact-merge release verification
  environment remain necessary and were preserved. The separate local release
  supplement is still running at this record; there is still no public v0.4.19
  success or client archive mutation implied by these source results.
- The final checkpoint passed the four release-readiness/privacy gates and
  169-resource synchronization. The first documentation pass caught a mixed-case
  product noun in the new guide; it was corrected to the established `zet`
  spelling without changing the naming gate. Python 3.10 runtime and the entire
  v0.4.20 platform CI remain unrun; checkpoint commits are not release candidates.

## Integration of the final v0.4.19 main

- Preserved the reviewed source checkpoint as `2c15c61a` and pushed it before
  bringing exact v0.4.19 main `591bb3ce` into this unfinished branch. No legacy
  evidence or unfinished worktree was discarded. The one conflicting file was
  the common Git writer: main's source/context-binding corrections were already
  present in the scoped composition. Resolution preserves the v2 scope decoder,
  deep-freeze checks, exact context comparison, legacy admission and shared held
  runner; the resolved writer is byte-identical to the reviewed checkpoint.
- Independent read review found no semantic conflict in the automatic CLI,
  service and availability merges. The added unsupported-mode diagnosis applies
  only to operation cancellation, not session writes; scoped Git and session
  mode predicates and runtime guards remain. Combined post-merge regressions
  are running separately; successful text merging is not their substitute.
- A read-only map of the ten common-exact command paths selects the existing
  source-intake batch as the next representative writer seam. It already has
  authenticated common completion and whole output-receipt targets. Its intake
  receipts/capture request are not captured source bytes or canonical documents.
  Other writers' unsigned legacy receipts must not be retroactively signed;
  field-local title/property proofs do not authorize whole-file Git selection.
  Reuse the concrete held runner and existing broker with a digest-bound current
  actor/route/claim scope, rather than treating a binding sidecar as authority.
  Full writer coverage remains unfinished.
- The preceding Git interruption gap is a real cut between retained pending
  context and authenticated claim publication. Explicit native original review
  must reuse the saved context/manifest/reviewer, keep pending actor bytes
  unchanged, and refuse corrupt/ambiguous claims rather than calling them absent.
  Existing authenticated claims always follow original resume. Claim absence
  must survive key-provider entry before publication; the shared authenticated
  scanner is the preferred seam, not a second signature or inferred approval.
  This is the next implementation slice, not a claim that the gap is already fixed.
- Post-merge validation completed: 126 CLI/runtime/availability regressions
  passed in 69.062 seconds; 32 exact-source/scope/held/legacy Git tests passed
  in 474.852 seconds. The common Git writer stayed byte-identical to its reviewed
  checkpoint. Four readiness gates, resource synchronization and diff checks
  also passed. Actual Python 3.10/Ubuntu execution remains the later full CI gate.
- The separate v0.4.19 local installation supplement subsequently passed all
  checks in 1,854.782 seconds, retaining the original failed observation. The
  exact-merge wheel was tagged/published and independently fetched anonymously;
  a fresh public-URL installation passed hash/resource/dependency checks and
  the actual installed bootstrap-origin reader. Detailed release evidence is
  recorded in that release's separate evidence PR, not as a v0.4.20 release or
  client-recovery result. No client project was updated.

## Original-review public route and release-evidence follow-through

- Added the existing Git command's explicit `--approve --review-original`
  mode. It selects only retained app/task context, optionally asserts the
  original session, and forbids a replacement reviewer, selection, approval
  identifier, plan or provider setting. Original resume remains no-review;
  missing or contradictory flags fail before dispatch. The adapter retains the
  existing wait/held/runtime and fixed private-error boundaries. The private
  authenticated re-review implementation is still being completed separately.
- The public routing, legacy Git, startup and availability cohort passed
  76 tests in 41.504 seconds. The new adapter cases use a stub domain through
  the actual held boundary; they do not prove original bundle selection or
  claim absence. Independent read review found no public-route blocker, and
  explicitly retained that distinction. Existing normal Git arguments and
  its missing-plan usage error remain compatible.
- v0.4.19 release-evidence PR #98, head `60481d64`, records the successful
  public artifact and exact-public-origin bootstrap verification. Independent
  evidence review compared retained JSON, actual wheel bytes, installed origin
  metadata and public release/tag/CI records without finding an actionable issue.
  Its full CI is running; no second full-matrix result is inferred from the
  already-passed main/tag readiness-only runs.
- Removal of the two completed, task-created external verification venvs was
  rejected by tool policy before the command ran. They remain preserved. No
  alternate shell, deletion mechanism or privilege workaround was attempted.
  The release worktree remains needed by PR #98; the unfinished v0.4.20 worktree
  also remains. Neither all cleanup nor client recovery is falsely marked done.

## Original-review broker and representative held-writer checkpoint

- The Git pre-claim interruption route now reuses the retained context and
  pending actor. Its explicit original review authenticates establishment and
  producer proofs, current ownership and exact Git preimage around the native
  decision. Existing authenticated claims follow original resume; ambiguous,
  corrupt or failed claims never become permission to obtain a replacement.
  The original pending record is not republished, and only authenticated
  completion performs its final CAS. Independent source review found no blocker.
- Review caught a key-lifecycle error in the first implementation: original
  review must never create a replacement archive key. The corrected common
  broker requests an existing key and performs authenticated same-key absence
  checking after provider entry and immediately before claim publication. Fresh
  approval preserves its original key-creation behavior. Six focused tests cover
  actual provider-entry claim insertion, missing-key refusal and fresh behavior.
  The existing lifecycle original-review helper now uses this same broker entry,
  not a second scanner. Independent review of both the common broker and helper
  switch found no blocker; the drift test still acts inside the real held claim
  publication boundary, not a vacuous replacement-key path.
- On the corrected common broker and lifecycle helper, 47 established approval
  and original-review tests passed in 86.400 seconds. The new actual CLI/Git
  interruption, original re-review and completed replay test passed in 116.866
  seconds. It checks unchanged original context, no replanning or pending
  rewrite, actual push/remote verification and no second completed execution.
  The earlier two-case public workflow run passed in 242.175 seconds before the
  key-lifecycle correction and is not relabelled as final-source evidence.
  These are source-tree synthetic tests, not installed v0.4.20 client results.
- Source-intake batch now exposes one private already-held runner using the
  original authority, request, exact store and completion authenticator. The
  legacy entry preserves its pre-lock authority and public error ordering,
  then delegates to that runner. Wrong/released/foreign locks, request drift and
  unsupported bound plans fail closed; it creates no extra lock or key consumer.
  Ten new held-runner tests passed in 3.707 seconds and four existing actual
  legacy/interrupt/identity-free-resume/drift cases passed in 2.683 seconds.
  Independent source review found no blocker. Session-bound source-intake
  composition is still absent; this extraction does not claim writer coverage.
- The final five actual private Git original-review tests passed in 464.901
  seconds, and the six common-broker tests passed in 0.683 seconds. This final
  source includes noncreating key use, same-key provider-entry insertion refusal,
  repeated interruption, cancellation/drift and completed original replay.
  The reviewer also noticed the fixed original-preimage progress stage was
  missing from the observer allowlist. Adding only that fixed stage and a
  private-context-stripping assertion closed the finding; all 16 observer tests
  passed in 21.972 seconds, including actual child and cancellation handling.
  Four readiness/privacy gates, 169-resource synchronization and diff checks
  passed. No full v0.4.20 platform or installed acceptance result is claimed.

## Representative intake composition and remaining acceptance work

- Checkpoint `0f9f0950` preserves and remotely backs up the reviewed original
  re-review, fixed progress stage and legacy held-intake extraction. It is not a
  v0.4.20 release. The next slice uses the existing broker and exact runner:
  retain the original request/context, bind current actor/claim/establishment,
  and verify completed output bytes with the already-authenticated live claim.
  Do not copy Git's remote-terminal or mutation-worker machinery into intake.
- A typed `source_intake_batch` actor selector is being added to the existing
  closed operation kinds. Human create/accept/handoff/recovery continuation must
  refuse domain selectors before key access or loading human proof. Legacy
  absent-kind actor bytes keep their human meaning. The selector is only routing;
  adding it does not open a writer or confer approval. Initial actor regression
  results are 48 tests in 66.003 seconds, with 47 passing and one host-capability
  skip. Public lifecycle/handoff/re-review regressions are running separately.
- Independent acceptance mapping found that public lifecycle and receipt-only
  Git tests existed separately, but not as one public create/write/handoff/
  accept/successor-write journey. A joined test is being added using real CLI,
  actor, broker, exact writer and bare-remote pushes. Native/key input and the
  legacy read-only Git planning handoff prerequisite remain synthetic; it is
  explicitly not final installed acceptance or whole-document custody proof.
- Do not treat the following remaining work as completed or quietly remove it
  from v0.4.20: a complete artifact generation bound to handoff approval; explicit
  legacy responsibility assignment; other writer and local-record families'
  actual session coverage; intake's typed authenticated Git producer; final
  installed-wheel/transport journey and exact-head platform CI. Existing large
  inventory/pagination and selection fixtures are useful primitives, not proof
  that those missing compositions work. Current receipt-only Git cannot claim
  canonical-document backup or predecessor artifact custody.
- Intake output provenance can cover the exact source-intake receipt, prepared
  capture-request file and common completion receipt after original-context/MAC
  and whole-byte checks. It cannot attribute the supplied request JSON, source
  binaries, later object capture or minted documents to intake. No filename,
  label, timestamp or path alone supplies ownership. Old unsigned evidence is
  never upgraded to a new authenticated success.
- The original-operation selector/refusal changes passed independent read
  review. The additional 22 public recovery/handoff/original-review regressions
  passed in 275.819 seconds. The earlier actor skip was independently identified
  as unavailable directory-symlink privilege; the hardlink refusal test passed.
  These observations do not substitute for the later cross-platform CI gate.
- The final joined public CLI journey passed in 205.000 seconds. Both pushes
  occurred against a real isolated bare remote. The test verifies the same
  workstream, the exact successor/predecessor link, former-owner claim release,
  successor claimed ownership, stale-app refusal before native/key/transport,
  exact per-session receipt commits and unchanged excluded bytes/index entries.
  Its earlier 190.054-second pass lacked the additional lineage oracle and is
  retained only as an earlier observation. No product source was stubbed to
  make the joined journey succeed; declared native/key/legacy read-only planning
  fixtures remain distinct from installed or provider acceptance.
- The private intake completion verifier passed independent review and its
  serial 44-test cohort: 43 passed, one existing host symlink skip, in 21.469
  seconds. It requires an actual succeeded claim under the same held archive
  lock, derives execution identity, verifies common completion/checkpoint MAC
  and whole output bytes, and reauthenticates evidence after observation. It
  does not open another key consumer, sign, finalize, replan or write. The test
  explicitly removes supplied JSON/source files after completion and still
  verifies only retained output bytes; foreign same-ID archive claims refuse.
  Legacy started-only writer authority, reconciliation and admission remain.

## Retained intake scale and the next complete chain

- Checkpoint `e366ee51` remotely preserves the joined public session/Git journey,
  typed intake selector refusals and claim-only completion verifier. Subsequent
  scope/context, owned writer and CLI work remains uncommitted development.
- The retained intake codec passed 17 tests in 5.624 seconds and independent
  root review. It preserves original request bytes and canonical planned source
  spelling without resolving missing inputs. Original source mapping is still
  verified by the actual writer, not inferred from an unsigned private bundle.
  Original operation evidence is recomputed through the planner's shared pure
  builder; inconsistent counts/digests refuse even if every outer scope and
  manifest hash is rebuilt. Its 32 MiB total metadata limit is explicit and does
  not change the legacy route. No source bodies or new approval live in it.
- A real synthetic 1,000-source metadata cycle passed with 1,001 exact targets,
  15,893 total source bytes and a 108,877-byte request. Retained preparation was
  8,333,515 bytes; original context was 8,334,305 bytes. Timings were: plan 29.180
  seconds, scope 1.058, preparation 1.175, context factory 1.110, save 16.189,
  independent load 8.105. There were 24 full input decodes across that complete
  storage cycle. This is cardinality/metadata evidence, not a large-source-byte,
  installed-runtime or completed domain-write performance result.
- That measurement exposed the importance of avoiding a full retained decode
  per output field: each 1,000-item decode is about a second on this host. The
  concrete runner is therefore using one validated private operation view per
  entry, exact retained-image/current-owner comparisons after callbacks and
  before mutations, and the original per-source byte recheck. A cheap scope-to-
  manifest/context invariant remains required; performance must not weaken it.
- Additional downstream gap found by source inspection: the existing capture
  batch's authenticated intake reader and chain validator admit only legacy
  intake evidence v2. A newly scoped intake must not be advertised as a working
  intake-to-capture chain until a typed authenticated scoped-intake reader is
  connected and the actual chain is tested. Keep legacy behavior; do not accept
  arbitrary new schema strings, infer capture ownership, or count metadata
  receipts as preserved source bytes. This remains v0.4.20 integration work.

## v0.4.19 release-evidence closeout and intake command review

- Release-evidence PR #98 passed all 14 checks on exact head
  `60481d649e93fc9a09b8f4ae2f7246f7c2c5e495` (run `33987880574`).
  It merged at `84d55bd5871e852eef97da6e4b89dcba252d0d8b` with the reviewed
  head and original release merge as its two parents. The existing v0.4.19 tag
  remains on the original release merge; a documentation merge is not a retag.
- The canonical development checkout was fast-forwarded and is clean, equal
  to origin/main. Open PR count is zero. The clean completed release-evidence
  checkout and its local branch were removed through normal Git operations;
  its remote branch was already deleted. Only the canonical checkout and the
  unfinished v0.4.20 worktree remain registered. The two previously policy-
  blocked temporary installation environments remain preserved, not bypassed.
  No client project, shared executable or provider was modified.
- The explicit scoped intake CLI adapter passed its final 23-test cohort in
  11.944 seconds: 17 new routing/projection/real held-lock-runtime tests with
  a mocked domain, five existing legacy CLI/error/resume tests, and one startup
  parser test. These are not actual scoped-domain or installed-wheel proof.
  Root read review confirms fixed preview/completed/blocked text, read-only
  preview domain-effect reporting, original route-only resume and closed
  progress/result projections. The unscoped route remains unchanged; missing-
  claim original re-review is deliberately not advertised by this first slice.

## Actual intake journey and independent callback-boundary correction

- The private first-slice cohort passed 11 tests in 233.249 seconds, including
  provider-entry drift, actual progress-callback actor drift, partial and final-
  receipt tails, original approval preservation and source-free completed proof.
  Full retained-input decoding does not repeat per output field or extra pulse.
- A separate actual public CLI journey passed in 40.575 seconds: public app
  registration, task creation and claim; approval; first receipt publication
  interrupted before its field checkpoint; deletion of only the caller JSON;
  app/task-only resume; independent original MAC/checkpoint and whole-output
  verification; then completed replay after both source files are removed.
  The first receipt, original context and approval identity remain unchanged;
  replay creates no claim, signature, actor change or domain write. Native input
  and the local key are synthetic; runtime is Python 3.12, with 3.10 grammar
  checked separately. This is not installed-wheel or client evidence.
- Independent review subsequently identified a distinct callback window: the
  low-level receipt publisher could invoke arbitrary progress after source
  validation. Current-owner reauthentication alone does not detect a source-
  bytes-only mutation in that callback. The above passes are pre-correction
  observations, not final acceptance. A deterministic source-only reproduction
  and narrow publication boundary correction are required before checkpointing.
  Preserve the independent fixed reporter, legacy callback behavior and source-
  free completed replay; do not rehash the whole batch for every metadata chunk.
- The next intake-to-Git/capture step needs original typed context, completion
  MAC and whole-output proof. It must not merely whitelist another evidence
  schema. In particular, capture rederivation can occur inside a live approval
  key consumer, so a historical reader must reuse that active claim or be
  called outside it; nested provider consumption is not an acceptable shortcut.

## Callback-window fix and typed Git output contract

- The source-only callback regression was reproduced against the original
  scoped runner: one test failed in 25.562 seconds after an actual intake
  receipt publication, while the workflow reported authenticated completion.
  This was a product boundary defect, not dismissed as a test-only problem.
- The scoped runner now permits arbitrary progress before the source check
  and after a completed field, but uses only concrete held/current/origin
  verification throughout source hashing (including EOF) and publication.
  The legacy writer and its callback behavior are unchanged; no second source
  hash or batch-per-chunk decoding is added. The fixed independent CLI reporter
  remains available. Native process interruption is not disabled.
- All five final adversarial cases passed in 106.118 seconds on intake source
  `64F7A68B93E00A508A8D541E759CFD50171D20681999DECDA1C55838FD546F80`:
  actual owner loss before publication; no arbitrary publication callback and
  resumed notifications; actual EOF callback protection; pre-entry source drift
  refusal; post-field cancellation with held lock and original no-rewrite resume.
  Independent read review cleared this source. Earlier fixture failures used
  overly broad publication hooks and Windows short/long TEMP lexical equality;
  final hooks select the actual intake artifact and compare physical identity.
  The consolidated unchanged-source regression cohort was started next; its
  final observation is recorded below.
- Separately, the next Git data contract now has a closed v2 producer union
  for intake receipts, prepared capture requests and common completion receipts.
  V1 schema, bytes, hashes, evidence and 128-proof budget remain unchanged.
  V2 is bounded to 8,192 proof rows and 16 MiB, refusing the whole scope on excess;
  a synthetic 1,000-item intake binds all 1,002 output proofs without truncation.
  Intake evidence does not invent a registry generation. Exact whole-new-file,
  HEAD-absent and index-absent-or-identical rules remain required.
- Seven new and five existing pure scope tests passed in 0.501 seconds on the
  final independently reviewed data contract. The three intake path spellings
  have literal independent oracles, not expectations derived from the helper
  under test. This is data/partition validation only: authenticated discovery,
  all original Git proof-consumer sites and actual remote backup remain to be
  connected. Existing writer authority is not broadened by constructing v2 data.

## Bounded historical context hints for the next producer

- A new private, read-only intake-context inventory visits only the fixed
  original-context directory. It distinguishes true absence from empty presence,
  denied access and unsafe topology. Published and pending leaves both bind the
  full name/identity/raw-byte generation, but pending leaves are never promoted
  to context hints. Corrupt JSON remains opaque, unauthenticated input for a
  later proof reader; enumeration itself establishes no provenance or ownership.
- Count all entries before filtering. Refuse the whole snapshot above 128
  entries or 32 MiB aggregate bytes, including pending files, before body reads;
  each stable read is capped to the already budgeted size. Repeated hint access
  performs no additional reads. Before/after observations include the complete
  fixed private ancestor chain, not just its deepest directory. No file,
  directory, pending record, key or receipt is created, removed or repaired.
- Final inventory tests: 14 passed and one native-symlink privilege skip in
  1.709 seconds; actual hardlink refusal and portable leaf/parent/intermediate
  reparse models passed. Root independently reviewed the frozen source and test.
  This still does not connect intake output authentication to scoped Git or
  capture. The remaining consumers must verify original claim/context/MAC and
  exact approved output membership, caching once per original operation.

## Final first-slice regression checkpoint

- The final unchanged-source cohort completed in 395.453 seconds with exit 0:
  78 tests, 77 passed, one host-capability skip. Composition: private workflow
  15; actual public CLI journey one; legacy intake 25, held runner 10 and
  completion verifier nine; new adapter 17; startup parity one. The skip is
  the prebound-receipt-parent directory-symlink test because native creation
  is unavailable on this Windows host, not a disabled product guard.
- Final intake source remains `64F7A68B93E00A508A8D541E759CFD50171D20681999DECDA1C55838FD546F80`;
  workflow `F9E6B3220E51BBF5128DA3BAD74D4FEEEA72A43333EBFEF6A2A00CE91E0FE250`;
  private tests `51C7685AFE7A518CBBEDCF0DB9F8234178D59ACC93EB01CEE28E1C43E81356C7`;
  actual public test `ADFD90CBD7B47F0BF11A4659E48CB210FF73D07E4121339D504AFE6741BA40FB`.
  All were independently reviewed. Actual runtime is Python 3.12; 3.10 grammar
  was checked separately. Legacy authority, writer, verifier, execution,
  reconciliation and completion helper ASTs remain unchanged; the extracted
  pure evidence expression is identical to the original planner expression.
- The staged checkpoint passed all four readiness/privacy checks and the
  169-resource consistency check. No version bump, installed v0.4.20 acceptance,
  cross-platform final CI or client recovery is implied. Intake original
  re-review, authenticated downstream capture/Git, mixed-byte performance and
  remaining writer coverage stay unfinished. The separate Git v2 data-contract
  changes are intentionally excluded from this first intake commit.
- Independent documentation review found no release/MCP/capture/backup claim
  expansion. The ADR now explicitly says checks occur before domain mutations:
  a refusal may still preserve private control evidence for safe original resume.

### Scoped intake Git contract checkpoint and next composition

- The v1/v2 Git scope cohort passed all 18 tests in 70.891 seconds on this
  Windows Python 3.12 source checkout. This includes actual Git preparation and
  original-context reconstruction, old-route rejection of scoped substitutions,
  unchanged historical v1 bytes and the bounded 1,000-item/1,002-output v2 data
  contract. It does not prove authenticated intake discovery or a live backup.
- The independently reviewed v2 codec and its seven new tests are checkpointed
  separately from the downstream integration. Completed public release
  evidence remains attached to v0.4.19; v0.4.20 remains unreleased.
- Next composition retains the original human-decision receipt producer and
  adds a separately authenticated intake-output producer. Its hint inventory is
  discovery data only. Retained original context, succeeded approval MAC,
  exact completed output bytes and original session binding must all agree.
  Active Git approval reuses its existing key context rather than opening a
  nested credential provider. Original Git re-review uses stored producer
  references, never a fresh inventory to replace the original approval.
- A new joined test is being prepared for a completed intake whose common
  receipt is already committed while source-intake receipts and its prepared
  capture request remain changed. Other-session outputs and lookalike files
  must remain excluded. A capture request is not preserved source bytes;
  authenticated metadata backup must not claim completed artifact custody.

### Historical completion reader and Git consumer integration

- The versioned data contract was committed and pushed as `b8e0f3e3`. The
  development branch then incorporated completed v0.4.19 release evidence from
  `origin/main` in `daae3db8`; no product tag moved and all unfinished integration
  files were preserved. Four public readiness checks and 169 resources passed.
- The shared historical completion reader's eight actual synthetic tests passed
  in 228.592 seconds, with no skips. Its first positive run had refused the
  common receipt's canonical trailing newline because a private-context parser
  was used; it now uses the exact runner's strict common JSON parser while
  preserving actual raw file bytes. The original failure is not reported as a
  successful test. All nine existing strict completion tests had passed in
  that earlier run with the same extracted common evidence helper.
- Product source hashes: intake helper
  `BD86B35BCF495DD9B101ABB495A2079446BDEAAB36F93CBFA49CEA7B71733E74`;
  historical reader
  `41683DE708D82B207A7043596C956658C39D03ACAF255EF08B638F91BB3608B0`.
  The tested eight-test file was
  `D42C3758666A2E6E0781DC47984CF695E0D6CBB7D28E8D405EF78A0DAD52B6FB`.
  Targeted test-only supplements and joined Git acceptance remain in progress.
- Existing Git command routing and new pure consumer projection/closed-dispatch
  tests passed 19/19 in 8.366 seconds. These routing/projection checks do not
  authenticate an intake or prove a Git push. Independent consumer source review
  was clear at provenance
  `54B16A505EE3F2E31870BABCFA90F9730DDB2DCE10BBACA0427B1BE0CFD228A7`
  and workflow
  `6445064DF8D137661768B0D357BF954E428691673A0F598F54681BD1F4ED7121`.
- Original intake metadata and current write authority remain separate facts.
  A succeeded original may be audited without its source inputs, but neither
  that audit nor metadata backup grants permission to delete those inputs.
  Baseline common-receipt discovery, real scoped commits/pushes, original resume
  and original re-review are still awaiting their joined test outcomes here.

### Historical reader checkpoint, adapter evidence and pending joined gate

- The final four reader supplements passed in 127.869 seconds on the unchanged
  `BD86B35B...` / `41683DE7...` product sources. Three strengthened existing
  cases plus one new generation-budget case complete passing evidence for all
  nine distinct current reader methods; this is not one full final nine-test
  run. Final test file:
  `661BC21573088B7FBF978F2C39C2E190200D9490FDF5ECF0712E931C52446D95`.
  Supplement execution overlapped the isolated joined Git functional cohort;
  elapsed times are not performance acceptance. Independent shared-reader and
  helper review was clear without another claimed runtime rerun.
- The adapter's final targeted eight checks passed in 68.629 seconds (seven
  data/contract cases and the real A/B intake + stored proof data/key/active-claim
  case). The separate corrupt-output/context preservation case passed in an
  earlier cohort before the sole product change: private snapshot inputs now
  reuse the existing 256 MiB Git writer input ceiling, independently of 16 MiB
  proof and 32 MiB result limits. This prevents a new intake adapter from
  shrinking legacy wide-exclusion input support. These are nine unique passing
  cases, not a single final nine-test run. Adapter source
  `24098B7C7C63FD7C8EED906FFE1B11879E112A0356C3D8A6F8C7FC37C4959414`;
  tests `325F98BA1D3924820E8FE014FB33D3B88A317D8C064DE8E865E774A6EBF42EBE`.
  Earlier adapter failures were test fixtures using the wrong result selector
  and confusing archive-generation revision with session revision. Neither is
  counted as an authenticated integration success.
- The first joined Git cohort failed both tests before their interruption
  sentinels; a first-only diagnostic rerun showed `cli_arguments_invalid`.
  The new test helper supplied an unsupported Git `--no-progress` option.
  It was corrected only in that test, preserving the real observer; all three
  intended Git modes then passed parser validation before expensive setup.
  No product parser/guard was relaxed. Actual joined commit/push and original
  continuation outcomes remain pending, so that consumer integration is not
  checkpointed as accepted here.
- Read-only follow-on analysis found that legacy `objet_capture_batch_exact`
  is not an existing common exact-manifest held transaction: it replans within
  a key consumer and delegates to legacy blob/manifest/index/receipt writes.
  Its result explicitly lacks same-claim resume. Keep its old schema gates;
  widening them alone would not supply session authority or safe continuation.
  A later concrete typed preparation/backend must bind original intake proof,
  current ownership and every actual effect while reusing existing publication
  primitives. No capture code changed during this analysis.

### Joined intake-output Git acceptance and compatibility checkpoint

- The shared historical reader checkpoint was committed/pushed in `b45f1229`.
  The remaining Git integration then passed both corrected actual source-CLI
  journeys on unchanged product sources. The test file is
  `DF71449C31ECF47591AF203FBE853D0465C46763AF5E503E313F2816B7042177`:
  first case 182.310 seconds; original re-review case 204.780 seconds, each
  exit 0 with no skips. They were separate runs, not a single final two-test
  run; concurrent isolated functional work is not performance evidence.
- Both tests use actual public app/session creation and claims, actual scoped
  intakes, actual Git commits and a temporary bare-remote push. Native input,
  archive key bytes and the existing local-transport/read-only legacy handoff
  fixture are explicitly synthetic. No actor, producer proof or domain writer
  is substituted. The installed-project/wheel path is not being claimed here.
- An already-committed common receipt still identifies the three remaining
  exact A outputs. Four B outputs are authenticated as other-session; copied
  source-shaped JSON and ordinary documents stay unknown. Worktree bytes,
  pre-existing staged entries, ignore behavior, source binaries and B actor
  state remain unchanged. Independent local/bare-remote refs and blob IDs agree.
- The first test makes one actual commit, interrupts before its push, and
  resumes from the same retained context without a second commit, new planner,
  hint inventory, selection, native approval or claim. Completed replay does
  not write or resign. The second interrupts before claim publication and
  explicitly re-reviews exactly the original context/pending actor before the
  real commit/push. Both interruption sentinels must actually be called once.
- Existing v1 provenance's full 12-test cohort passed in 239.025 seconds, with
  no skips and no source changes. Its existing public-command continuation
  cohort subsequently passed both tests in 228.027 seconds, with no skips and
  exit 0. All 14 existing regression tests passed on the same frozen sources;
  the first cohort overlapped other isolated functional tests, not a performance
  measurement. Four staged public readiness checks and all 169 package resources
  passed. New projection counts separate capture requests from
  receipts and keep source custody/artifact completion false. No client data,
  runtime, credentials, provider state or feedback status was modified.
- This source integration is ready for its development checkpoint, not for a
  v0.4.20 release judgment. Installed-wheel acceptance, remaining writer and
  effect coverage, domain MCP parity, artifact custody and responsibility
  assignment remain open. No new task command or parallel approval system was
  added by the intake-output Git integration.

## Single metadata-record session integration, in development

- Continued from clean, pushed checkpoint `859d8d83` in the existing unfinished
  v0.4.20 worktree. The release remains v0.4.19; this is not a v0.4.20 release
  or a client recovery result. No private client archive or runtime was changed.
- Selected existing `source-intake-record` next because it already has one
  absent-to-exact receipt manifest. It does not capture source bytes or prepare
  a batch capture request. Routing it through batch intake would add an
  unintended artifact. Legacy capture has a different transaction lifecycle
  and is not reopened merely by accepting a new evidence schema.
- Extracted a pure reconstruction factory while preserving original unscoped
  manifest, approval context, receipt and source-basis bytes. New private
  retained inputs bind original redacted JSON bytes/path, original unbound
  manifest, session claim/origin and predecessor to a new scoped manifest.
  Loading is data validation, never original-approval or current-owner proof.
  The legacy public entry rejects a scoped plan before native approval.
- New single-record held execution reuses the common exact engine, checkpoints,
  authenticated final receipt and existing exclusive staging/no-replace move
  primitives. It leaves interrupted pending files intact, never scans or adopts
  them as authority, and refuses an unknown existing destination. Original
  continuation does not need the external caller JSON. The workflow reuses
  existing concrete current-session and original-establishment checks, the
  common native broker and original-claim discovery, not a second approval
  framework. Missing approval remains a blocker without an automatic prompt.
- Shared command routing now supports single and batch receipt modes while
  retaining batch call grammar. The existing single CLI gains explicit session
  selectors and original resume. A matching MCP tool uses the same held/runtime
  service, bounded closed arguments and MCP allowed-root checks. New MCP work
  enters the existing serial lane and cooperatively waits; only audited reader
  queries bypass that lane. Intake progress is closed stage/count data; an
  idle interval reports liveness with the last observed facts, not invented
  processing progress. No new top-level CLI command was introduced.
- Initial legacy/codec result: 26 tests passed in 9.974 seconds, including 15
  new codec/legacy-entry checks and all 11 existing single-record cases. The
  preceding 25-case run had one overly specific error-code test expectation;
  the malformed context already refused safely. The expectation was corrected,
  not product admission. Existing writer/context/authority AST remains unchanged.
- Single-record completion foundations passed seven tests in 2.945 seconds.
  A fully rehashed but forged-MAC envelope passes structural loading and still
  fails authenticated completion. These foundations do not claim actual owned
  publication. The first actual private workflow case separately passed in
  25.987 seconds: actual publication, injected interruption, original resume
  with deleted caller JSON and read-only completed replay. The broader final
  workflow cohort and cross-CLI/MCP public journey are still under examination.
- All 17 existing batch command-routing tests passed in 8.749 seconds after
  shared dispatch/CLI factoring. They use mocked domain runners and are not
  proof of actual intake execution, installed release acceptance or timing.
  Source hashes and final broader results will be recorded after review.
- Independent review found that reusing the legacy single-record verifier in
  the new scoped path would resolve away an internal link and did not reject
  unexpected hardlinks. Publication itself used strict reads, but later
  postimage/resume authentication needed the same protection. The scoped path
  now receives a lexical, bound-file verifier at preimage, exact writer,
  started-final and completed-proof boundaries. The legacy verifier is not
  weakened or silently redefined. Earlier passing tests do not close this gap;
  the corrected source needs new link-refusal and continuation evidence.
- The initial broader private workflow cohort had seven passing cases and one
  test-fixture failure: saving identical actor fields is intentionally a no-op,
  so that callback did not create the claimed drift. The corrected test makes
  a real actor CAS change and asserts different raw bytes; that case passed
  separately in 6.484 seconds. These are eight distinct covered cases, not one
  passing final eight-case run. The forthcoming scoped-verifier revision also
  requires revalidation of those earlier results.

## Single-record corrected-source verification

- Final scoped verifier uses the lexical approved receipt path, retained full
  directory/file binding and a separate strict single-link, stable control
  read. Review discovered that the held-file primitive itself did not enforce
  single-link status, so it was not treated as sufficient by name alone.
  No common legacy reader was modified for this single-record change.
- The corrected completion-foundation cohort ran nine tests in 3.268 seconds:
  eight passed; the real Windows file-symlink test was explicitly skipped for
  native privilege error 1314. Actual hardlink creation proved the old-reader
  acceptance and the new refusal. The missing native symlink privilege is not
  a passing Windows symlink test; the cross-platform/full release gate remains.
- All eight actual private workflow tests then passed in one final run,
  105.031 seconds, with no skips. This includes real publish-before-checkpoint
  interruption, retained original resume, exact ownership/input/MAC refusal,
  preserved unpublished staging and read-only completed replay. Independent
  review of the bundle, unchanged legacy factory values, workflow and narrowed
  verifier found no further blocking issue in those reviewed changes.
- Both joined public source tests passed in one run, 75.867 seconds, no skips:
  CLI publication interruption to MCP original resume to CLI replay; and the
  reverse direction. Actual public session registration/create/claim, native
  broker, domain writer, receipt/checkpoint, runtime guard and shared service
  execute. Only native answers/key bytes and the precisely placed interruption
  are synthetic. MCP uses real JSON-RPC dispatch in-process; this is not a
  fresh stdio process, installed-wheel journey, native power loss or timing
  acceptance. Source files and original private context stay unchanged; no
  capture request or extra claim is manufactured.
- New command/MCP/serial-lane tests passed 18/18 in 5.293 seconds, no skips.
  Those tests mock domain execution and instead cover closed grammar, root
  policy, real runtime/held routing, cancellation, terminal silence and safe
  observed-stage/count liveness. They complement rather than replace the two
  actual public journeys. Earlier 17-case batch command regression remains
  separately recorded. Broader existing transport/startup/resource regression
  is being run before this development checkpoint is pushed.
- Frozen corrected source SHA-256 (no `sha256:` prefix):
  - Single workflow: `22a1bd3267b34167a997f8edcde6e0a3a0643572b8fa3544e30464a75bb46f5b`.
  - Held execution/verifier: `c807b1898d268b6dfa5365c64ee4d9e04f96c2b8ce75c1f729876a21055ac8dc`.
  - Retained bundle: `89fb3ac61aea787a7444231da03db923182502ffb08edcceac1ad434067467ec`.
  - Legacy pure factory/public-entry guard: `b16a2fe17ab44722194d280622e8f387e4c26321706b35a920f4795a37c1c56c`.
  - Public journey test: `c6224ebe109d2a646a7417d25f29a20beb28ca1c14e0ad5b885faa2ddeea639a`.
  - Private workflow test: `5d2121c0c1e156aa2617001efaf44812af74e8aed8dda94c206814a103937378`.
  - Grammar/transport test: `8022c5b27e1937ee50f9282dc515187bfe2c367ec0e8a9e28570a881496b311d`.
- Windows Python 3.12 executed these tests. Parsing changed Python sources with
  Python 3.10 grammar is additional syntax evidence only. Concurrent isolated
  functional fixtures are not performance acceptance. Version remains 0.4.19
  in this unreleased feature branch. No client or provider state was modified.
- Final existing regression cohort passed 57/57 in 23.152 seconds, no skips:
  batch command routing, MCP session transport, fresh-process CLI startup and
  package resources. The four public readiness checks passed, including public
  privacy hygiene. These are development gates, not full multi-platform CI.
- The present-day surface assertions needed their already approved additions:
  exactly one CLI path (`work-session`) and three MCP tools (session query,
  session management and single-record intake). Current counts are 576 CLI
  spellings and 134 MCP tools. Removing exactly those additions reproduces the
  old 575/131 canonical digests; no existing MCP input schema or CLI path was
  changed by that comparison. Five targeted surface tests passed in 0.513
  seconds. Historical fixture goldens and every privacy/raw/derived/path/BOM/
  subset checking expression remain unchanged; the broad history suite was
  not claimed as rerun. Existing checkout CRLF differences were distinguished
  from the fixture's Git bytes without editing the fixture.
- Remote read-only recheck still reports latest release v0.4.19, no open PR,
  main `84d55bd5871e852eef97da6e4b89dcba252d0d8b` and original task head
  `859d8d83b7dc88b4ed4460f4ac84e2bab7722f4b` before this checkpoint push.
  Open secret alert count is zero; this does not guarantee no historical
  exposure. Only the canonical root and this unfinished feature worktree are
  registered. No completed worktree was recreated and no client file was used.

## Scoped batch output identity follow-up

- Single-record checkpoint `0602abd1602ec337ab1e6b1faa0ce2b832d7f8b7`
  was committed and pushed after the final four readiness gates; remote branch
  ref matched and the feature worktree was clean. This was a development
  checkpoint, not a merge/tag/release.
- Continued the concrete verifier finding across the existing scoped batch
  path instead of declaring the same class of problem closed globally. A tiny
  temporary-file reproduction (1.455 seconds, exit 0) showed that both a source
  receipt and a prepared capture request with two hardlinks still passed the
  old batch postimage reader. Git's independent plain-file observer classified
  those same files as hardlinked. This establishes a reader defect, not a
  demonstrated Git push exploit or evidence of any client modification.
- The shared verifier is used by scoped apply, preimage, started-final resume,
  own succeeded proof and downstream historical completion. The minimal fix
  is a strict single-link/stable read inside the already bound file lease when
  the original manifest has a work-session binding. Preserve the unbound
  legacy branch, approval/context/manifest bytes and all writer code. The
  conditional check adds no approval source, new command or alternate engine.
  Focused linked-output and authenticated-history tests are being prepared;
  previous clean single-record results do not stand in for those new tests.
- The frozen 26-line scoped branch passed the new four-test cohort together
  with 25 legacy intake, ten held-execution and nine own-completion cases:
  47 passed, one existing Windows directory-symlink privilege skip, 56.459
  seconds. All new hardlink cases actually ran. One real completed batch was
  checked through own succeeded proof, historical provider authentication,
  data-only image and a distinct active Git claim, including a hardlink added
  at provider entry. No caller request/source read, writer, signing, key
  creation or repair was permitted by the historical fixture.
- Independent review found no further issue in the scoped branch. The
  existing nine historical-reader tests passed in 261.027 seconds, no skips.
  These concurrent isolated Windows Python 3.12 fixtures are functional
  regression evidence, not a performance acceptance claim. Python 3.10
  grammar and diff checks passed; removing the new conditional branch makes
  the source AST equal the previous committed version.
- Frozen source SHA-256 is
  `5d44da7dee3bc3b9124926cc1e51855128a029660fbe5d44ece39ae1bea3f3f2`;
  new output-identity test SHA-256 is
  `23acb20db78be585b88a51318caa527ed51009d9ae91825f904a493cdfef8548`.
  The actual batch workflow regression and public readiness checks remain
  pending at this record point. A prior root test output was interrupted;
  absence of its process is not counted as a pass or completion receipt.
- The actual batch workflow cohort subsequently passed all 15 tests in
  327.295 seconds, exit 0, no skips. The four public readiness checks also
  passed. Together with the recorded owner/reviewer results, this closes this
  scoped reader correction at development-test level only; no release or
  client repair is claimed. The next bounded slice is single-record historical
  proof into the existing selective Git pipeline, not a new backup engine.

## Single-record historical proof and selective backup integration

- The scoped batch identity correction was committed and pushed as
  `aff179181916ed9ee39206f81819b55f9f9b4d00`; the remote task branch matched.
  The unfinished feature worktree is retained, not mistaken for cleanup debt.
- Continue the existing user workflow: one completed metadata record must be
  attributable to its original session when a later Git backup runs. A prior
  completion is historical evidence, not the later writer's current authority.
  Do not call original resume merely to obtain proof: the actor may correctly
  have moved on. Do not reuse a batch proof label for a single record.
- Reuse the shared original-context, establishment, claim-generation, terminal
  MAC and repeated file-image reader. Closed batch/record dispatch selects the
  existing domain codec, exact context, strict output verifier and own
  succeeded-claim gate. Record results have distinct exact data-only and
  authenticated types. Their output set is one source receipt and its common
  final receipt; it includes no capture request, source bytes or input JSON.
- Reuse the complete bounded context inventory with separate fixed batch and
  record directories. Neither filename nor opaque context hint establishes
  authorship. Existing limits remain 128 entries and 32 MiB per directory;
  both directories together are explicitly bounded, not unlimited history.
  Pending leaves count toward budgets and generation but are never hints.
  Wrong-family snapshots, links, denied reads and generation changes are
  rejected rather than interpreted as absence.
- The Git v2 codec admits only the explicit new single-record producer and
  its two output kinds. Fresh selection authenticates each original once;
  original Git resume and re-review follow retained producer references only.
  Preserve unknown and other-session changes, existing v1/batch v2 bytes,
  non-force writer, current owner guards and original human approvals.
- Inventory regression initially had one test-helper error: the old fixture
  attempted to read the actively locked Windows writer-lock file. Corrected
  only the new assertion snapshot to exclude that exact held lock, then the
  combined existing 15/new four tests passed: 18 passed, one existing native
  file-symlink privilege skip, 2.520 seconds. Real record hardlinks were tested.
  This is opaque inventory coverage, not completion or backup acceptance.
- The shared reader and actual joined selective-backup journeys remain under
  implementation and independent review at this record point. No version,
  release, client archive, provider, credential or feedback status changed.
- The single-record historical reader then passed all eight new cases in
  176.164 seconds, exit 0, no skips. Actual original record and establishment
  approvals, claims, checkpoint/final files and output bytes were used; only
  native answers and key bytes are synthetic. Tests distinguish structural
  data images from terminal-MAC authentication, preserve the strict original
  succeeded-claim gate, and audit with a different active same-archive claim
  without a nested key provider. Input/source removal, wrong family, missing/
  corrupt/started claims, foreign/released locks, hardlinks and provider-entry/
  exit evidence changes were exercised without repair or new authority.
- Independent source/test review is clear at shared-reader SHA-256
  `033ff31f87b371d3b378eed3ccdc5605cfa5c20360c3f063b2f50d5f35b32fa0`
  and new reader-test SHA-256
  `7bf6521df1bb226408b20ee0f4ec5b835b435cc8270f64d10ec1a6fa8f3cb51e`.
  The existing batch historical cohort and actual selective-Git journeys are
  still pending; this reader result does not substitute for their execution.
- The existing batch historical reader also passed all nine cases on the
  new shared-family implementation: 275.442 seconds, exit 0, no skips. This is
  separate from its earlier 261.027-second run before the family extension.
- Pure Git contracts passed 27/27 in 1.631 seconds: eight new record contracts,
  seven existing intake-scope, five consumer-projection and seven provenance
  data cases. The initial run had one incorrect manual test expectation that
  omitted the existing `private_values_echoed: false` evidence field. Corrected
  only that expected field; original scope bytes already matched. These
  synthetic data contracts are not MAC, ownership or Git execution proof.
- The first actual joined record/Git run failed both cases before the record
  writer or Git producer was reached (46.117 seconds). The new fixture passed
  an archive-relative string to the existing process-relative `local_path`
  argument. A minimal real planner comparison confirmed the relative argument
  returned `local_path does not exist.` while the same absolute fixture path
  succeeded. Corrected only the test input, without changing path semantics,
  initializing guessed policy, weakening checks or stubbing the planner.
  Corrected public journey test SHA-256 is
  `24838885ad87c1fde9e0aac6a0f2ffef415f91bb3a9af314410aa2c177c32429`;
  its actual two-case rerun is pending at this point.
- The corrected actual public single-record-to-Git pair passed both cases in
  361.534 seconds, exit 0, no skips, without product-source changes. Real
  public app/work creation and claim, exact record and establishment evidence,
  current ownership, selective commit, local-bare-remote push and remote blob/
  ref checks execute. Only native answers/key, pre-existing nonmutating
  handoff prerequisite and isolated local transport are synthetic. The tests
  inject exceptions at named boundaries; they are not installed-wheel, native
  power-loss, provider or performance acceptance.
- One case starts with the common final already committed, discovers only the
  remaining owned source receipt, interrupts after commit/before push, resumes
  with app/task only and verifies read-only completed replay after fixture
  source removal. The other interrupts before claim creation and re-displays
  the exact original context, then commits both owned metadata outputs. Both
  forbid new inventory/planning/context replacement during original
  continuation and preserve the other session, staged/unstaged unknown files,
  copied-but-unowned receipt and custom ignored data. They do not newly inject
  owner loss, attest source custody or authorize source deletion.
- Independent source/contract/public-journey read review is clear. Frozen
  Git adapter SHA-256 is
  `d3398554f30d86029c889acaf0fbc5b7dbe0a8053b3034a159b21bb26845856f`;
  scope codec `279d3c8a5a0672947f0324698c66cb5e9ae55f5f42be8af54e6f3a760b7f99c3`;
  Git projection `ecb7845a7bd8e87283b6a4764b9ea30cf14f79f399bb2f0216693713018d8be6`;
  Git workflow `2b3e42327b1942b89b68c594577cac488d300ff1d0ce3442ab91abe0b6279995`.
  The new pure contract test is
  `096a85e0b4ae01b919f781c911a5d98bdcf9a605e28f44e15fed6fe18b631da6`.
  Existing actual batch adapter/public journeys and final public hygiene
  checks are still pending at this record point.
- Final existing real batch regressions passed all four cases in 510.520
  seconds, exit 0, no skips: two actual provenance cases and both public batch
  intake-to-Git original-resume/re-review journeys. The four public readiness
  gates passed. Root and independent reviewers checked the frozen source;
  actual tests ran on Windows Python 3.12, with Python 3.10 grammar as syntax
  evidence only. Concurrent isolated functional runs are not timing acceptance.
- Remote recheck still shows public v0.4.19, no open PR and zero open secret
  alerts (not a no-exposure guarantee). Canonical main and origin/main remain
  `84d55bd5871e852eef97da6e4b89dcba252d0d8b`; the only worktrees are the
  canonical checkout and this unfinished feature checkout. This source slice
  is ready for its development commit, not a v0.4.20 release or client result.

## Git MCP parity after the single-record producer checkpoint

- The linked-output correction and single-record authenticated Git producer
  were committed and pushed as `aff17918` and `3d94f40c`. The feature checkout
  was clean after push; neither is a release or a client-data execution.
- Continue the approved train by exposing the already tested session Git
  service through MCP. The next slice adds only `git_backup_reconcile_plan`,
  four explicit modes, strict presence-sensitive original-input rejection,
  allowed-root checks and a closed MCP-only result projection. The CLI result,
  exact writer, original approvals and current-owner guards remain unchanged.
- Divide implementation by non-overlapping ownership: handler/projection and
  grammar tests; shared transport and progress/cancellation tests; actual
  CLI/MCP selective Git journeys and independent review; root documentation,
  integration review and final hygiene. Limit functional cohorts to two
  isolated processes. Their elapsed times are not performance acceptance.
- Review corrected an exact-type boundary in the draft projection: inspect
  `effects_state` as an exact string before comparing its value. A hostile
  object's equality method must not be invoked while forming public output.
  This is a presentation fix, not new authentication or altered Git authority.
- Existing MCP progress/cancellation specifications were rechecked. Reuse the
  fixed progress-token sequence, one serial lane and cooperative wait cancel;
  do not invent item completion, kill entered Git work or drop a verified
  original result on a late cancellation. References and consequences are in
  the session-resume decision log.
- Functional results and frozen source identities are pending. No version
  bump, pull request, release, provider use or client-data mutation is implied
  by this implementation checkpoint.
- The final handler/projection and current-surface cohort passed 18/18 in
  0.714 seconds, exit 0, no skips: 13 new command cases and five current-surface
  checks. An initial grammar-test error passed `mode` twice to a test helper;
  only that fixture call was corrected. Closed projection also refuses
  non-exact string keys before known-field lookup, including nested anchor
  keys. This defends against malformed internal objects, not a new JSON
  authority path. The CLI result object is not rewritten.
- MCP has 135 tools at this checkpoint. Removing only the new Git tool
  reproduces the preceding 134-tool digest; existing definitions are unchanged.
  CLI remains 576 spellings. Only current expected count/digest and the
  explicit additive name changed in the two surface gates; historical fixtures,
  raw/derived privacy checks and subset boundaries were not weakened.
- Final transport tests passed 49/49 in 7.530 seconds: 14 new Git cases and
  35 existing cases. The first draft malformed-ID test wrongly used a handler
  stub that accepted an invalid request. It now uses the real JSON-RPC basic
  validation. A separate exact-key precheck protects only Git event projection;
  the shared CLI projector and intake behavior remain unchanged.
- The subsequent six-case cohort passed in 11.661 seconds, exit 0, no skips:
  one new actual-process Git wait/cancel test, two existing actual-process
  management tests and three existing MCP startup/error-envelope tests. A
  foreign OS lock remains held through a serial response barrier; Git waiting
  and queued cancellation produce no domain writes, ping/query remain live,
  and protocol stdout/stderr remain clean. This is admission/order evidence,
  not instrumentation of every native/key call or actual Git backup proof.
- The first actual two-journey run failed both final completed-replay checks
  after 331.312 seconds. Before those checks, actual selective commit/push,
  cross-surface continuation/re-review and independent blob/ref/exclusion
  checks had completed. The new test over-forbade the shared terminal-MAC
  function: original session establishment uses that same pure calculation
  to compare its existing MAC. Root independently confirmed this read-only
  path. Removed only the blanket MAC-method sentinel; concrete terminal
  publication, writer, new claim, native approval, context replacement,
  discovery and actor writes remain forbidden on completed replay, with
  full files/index/HEAD/remote equality checks. Product authority is unchanged.
- The corrected two actual journeys are running against the final command
  and transport snapshots. Earlier execution loaded the previous projection
  before exact-key hardening and is not final-candidate acceptance. No success
  or source-byte-custody claim is inferred from a running process.
- Final corrected actual CLI/MCP Git journeys passed both cases in 341.968
  seconds, exit 0, no skips. The final source snapshots were unchanged for
  this run. One crosses CLI pre-push interruption to MCP original resume and
  CLI completed replay; the other crosses MCP pre-claim interruption to CLI
  original re-review and MCP completed replay. Both independently check real
  local-bare remote refs/blobs, excluded staged/worktree bytes, original
  context/claim, current owner and unchanged completed-replay state. Recomputing
  an existing establishment MAC is permitted; creating/publishing new evidence
  is not. These source journeys use the documented synthetic native/key/local
  transport and read-only handoff fixture, not client credentials or providers.
- Frozen source SHA-256 values: MCP handler
  `2557bdffa97e053b404c0256be5165ebe2e2fb04f69c3dfc5c85ed246efb14f6`;
  Git command/projection
  `c9ec42576840bf8f1356fe5d61e26da78b447a0e0eeb518963ef8e9c0f182fa3`;
  transport
  `5fc12ae2e4e4e4b20f79bbe9b30f099c533ca1e95cc4550132a01e6b2c891f38`.
  Actual journey test is
  `0f3beda61758263f0061ee1808d6e952874fdc15392df23f407a1e1e7695f21f`;
  command test `aed6f19fa4cc83e361a2d292f71cf3789a20d3fd92babab76369e73fad020aab`;
  transport test `43b887b0425618b55d1167a95e86e7a250694e3dc674c3615a7cd66ccc3a062a`;
  stdio test `f7416906643b9af77a0e62ce00babe5b8a58f56cd566a47da4e8ab59f420e5e9`.
- Root and independent reviews are clear. The four public readiness gates
  passed; Windows Python 3.12 functional results and Python 3.10 grammar
  evidence are distinct from full cross-platform CI and installed acceptance.
  Remote recheck still shows public v0.4.19, no open PR, zero open secret alerts
  (not a no-exposure guarantee), clean canonical main at `84d55bd5` and only
  the canonical plus unfinished feature worktrees. No client or global runtime
  was modified. This slice is ready for a development commit, not a release.

## Batch intake MCP parity after the Git checkpoint

- The Git MCP slice was committed and pushed as
  `c3828e8f471357c7f287cb784fa270d85e3de190`; local HEAD, tracking ref and
  the independently queried remote ref matched, and the feature tree was
  clean. Continue the train with the existing batch intake, not a new writer.
- Add `source_intake_batch` with preview/apply/resume and its existing manifest
  input. Reuse the common intake command result, exact actor/approval/checkpoint
  engine and serial MCP lane. A fixed private record/batch helper may share
  input handling, but must preserve the existing single-record tool definition,
  response text, relative-path policy and missing-field failure behavior.
  Stricter fresh-field admission belongs only to the new batch tool.
- Original continuation uses app/task and an optional same-session assertion;
  reject replacement manifests/reviewers by presence. It does not expose
  original re-review: missing original approval remains an explicit blocker.
  A prepared capture request is metadata, not evidence of preserved source
  bytes. Do not bridge legacy capture by accepting another schema.
- Seed the shared intake transport with an internal fixed `starting` tuple,
  then replace it only with real observations. Reuse the existing five-second
  heartbeat and token/cancellation rules without widening the domain event
  projector. Inspection confirmed wait/acquired observations already occur
  before runtime verification; this closes the earlier transport-entry gap,
  not a previously missing runtime heartbeat. Preserve Git/legacy behavior.
- Work ownership remains separated: MCP helper/schema and command tests;
  transport plus intentional record-starting expectation changes; actual
  batch cross-surface journeys and existing record regressions; root durable
  records, independent review and hygiene. Run at most two isolated functional
  cohorts. All results below this point are pending until their terminal output.
- The new handler and compatibility cohort passed all 15 cases in 0.668
  seconds, exit 0, no skips: ten new command tests and five current-surface
  checks. Exact old record definition, response text, empty/missing-field
  structured failures and relative/empty input-path behavior are retained.
  New batch strict grammar rejects cross-family inputs, replacement original
  parameters, extra authority and oversized payloads before the domain route.
  No common command/writer or CLI implementation was changed.
- The transport/regression cohort passed 76/76 in 15.421 seconds, exit 0,
  no skips: ten new transport cases, 17 existing batch command, 18 existing
  record command/transport, 17 shared transport and 14 Git transport cases.
  Four record expectations intentionally include the new initial notification;
  their domain-count, privacy, cancellation and terminal assertions remain.
  Independent final transport review is clear, with no further source delta.
- Current MCP is 136 tools; removing only `source_intake_batch` reproduces
  the previous 135-tool digest exactly. Existing tool definitions, historical
  fixtures and all other privacy/predecessor gate ASTs are unchanged. Syntax
  checks use Python 3.10 grammar; functional tests run on Windows Python 3.12.
- Four actual source journeys are running serially on the frozen helper and
  transport: two new batch CLI/MCP cases and both existing single-record public
  cases. They are separate from grammar/scheduling proof and must complete
  before this source checkpoint is considered verified. No installed-wheel,
  full CI, release, capture-custody or client-recovery claim is made here.
- All four actual journeys passed in 145.224 seconds, exit 0, no skips, on
  unchanged candidate source. The new batch pair interrupts after a real first
  receipt publication and before its checkpoint, resumes through the other
  surface without caller JSON, verifies the same original claim/context and
  independently checks common MAC/checkpoint plus exact receipt/capture-request
  bytes. The already-published receipt keeps its bytes and file identity rather
  than being written again. Completed replay after fixture source removal
  forbids concrete publication/writer/planning/actor/new-approval paths and
  preserves the full remaining file snapshot. Both existing record journeys
  also pass; no fixture correction was needed in this cohort.
- Frozen MCP helper is
  `098615dd995f2a99ea1f784f2d662836c91a21b6315eb3f43449541fca295a94`;
  transport `214050248a5e85773e89e0e876fc51acda5321f1984b5ea4ccd5446acc2613b0`;
  new command test `ce8204db8a5d5a2b6e04a163543a66093dcabc562add23aab4a1a610d55f79e2`;
  new transport test `a35cc3d2bd6472486075c76d55ccdcb977322de66be0bcd1b4280a906c625f94`;
  new actual journey test `1c2529cb99a2b6d0edd95007322d0f0242a725ba9cfe837ac3d85bedac5893ee`.
  The existing record public test remains
  `c6224ebe109d2a646a7417d25f29a20beb28ca1c14e0ad5b885faa2ddeea639a`.
- The four public readiness gates passed and independent handler/transport/
  journey review is clear. Source verification is complete for this bounded
  MCP mapping, not for the whole release or all writers. The only approved
  schema addition is the new batch tool; no client, provider, global executable,
  legacy approval or source-byte preservation state was changed.

## Explicit original review for the reachable pre-claim cut

- The batch MCP slice was committed and pushed as
  `4e0472091d863b5df29eed27db95f2ae6a7f184b`; local HEAD, tracking ref and
  remote ref matched, and the feature tree was clean. Continue with the
  remaining reachable interruption before durable approval-claim creation.
- Inspection confirms that both intake families save their unchanged context
  and pending actor immediately before the claim constructor. A failure there
  can leave a retained original but no claim. Automatic resume must continue
  to refuse; add an explicit original re-review instead of manufacturing
  approval from absence or leaving that operation without a continuation path.
- Reuse the existing original-review broker with its noncreating key consumer
  and final authenticated same-key presence scan. One private closed-family
  intake module and two fixed wrappers compose existing loaders, typed views,
  current-owner guards, concrete writers and completion verifiers. Do not alter
  original manifest/context bytes, fresh/automatic-resume implementations or
  the broker. The registry-transition-specific re-review helper is not an
  intake writer and will not be adapted by pretending its preimage is compatible.
- A present original claim follows unchanged automatic resume without another
  native decision. A malformed, failed, ambiguous or unverifiable claim is
  not absence. New native review requires genuinely absent original approval,
  a pending original selector, authenticated unchanged establishment evidence,
  unchanged current ownership and every original output still absent.
- Batch revalidates retained source locations, physical identity and bytes;
  record revalidates its retained metadata and strict receipt preimage without
  newly requiring external source bytes or the caller JSON. A copied output,
  even if byte-identical, blocks a new review. Guard source/target/actor/origin
  evidence before and after native/provider callbacks; never nest key consumers
  or save a new context/pending actor over the original.
- Extend only the two existing CLI/MCP routes. CLI requires explicit
  `--approve --review-original`; MCP uses `review_original`. Both accept the
  saved app/task route and optional same-session assertion, not a replacement
  input, reviewer, digest or approval ID. Preserve existing unscoped batch
  resume, old mode behavior and the same transport family/lock. No new command
  or tool name is added. Native acceptance alone is not completion evidence.
- Assign the private engine/fault matrix, public surface/compatibility and
  actual public journeys to separate owners. Root records decisions and
  independently reviews integration. All new implementation and validation
  results remain pending; client and provider boundaries are unchanged.
- Root also identified a separate pre-release concurrency question in current
  code: scoped intake and Git `_current` guards compare the whole registry
  digest as well as the exact current claimed binding. A different app's
  registration after an interruption could therefore block original
  continuation even if the selected session is unchanged. The whole-digest
  comparison is confirmed in code; the cross-app interrupted journey still
  needs an actual synthetic reproduction. Do not silently relax this guard
  during original-review implementation or claim two-app recovery acceptance
  before resolving and documenting its intended scope.

## Original-review verification checkpoint (not release acceptance)

- The public routing and transport cohort passed 101 tests in 26.268 seconds,
  no skips. It includes ten new original-review grammar/held-routing tests,
  unchanged-mode compatibility, legacy unscoped batch resume, private error
  envelopes and the existing completion-authentication requirements. This is
  routing evidence, not proof that a mocked domain performed a write.
- Root's four public-readiness checks passed: public links, Korean product
  language, public privacy and the runtime skill package. This is not a
  guarantee that historical public material never exposed information.
- The first private positive run failed because its test observer used the
  wrong positional argument for the native request. Exact source inspection
  confirmed the contract is `(context, *, intent, native, ...)`; the public
  journey's observer was already correct. The private test was corrected,
  including its direct synthetic-decision call, without product changes.
- Review also removed a blanket test prohibition on terminal MAC calculation:
  existing historical establishment verification legitimately recomputes that
  MAC without writing. Concrete claim construction, receipt finalization,
  domain writer and actor mutation remain prohibited during completed replay.
  A corrected both-family positive test passed in 76.120 seconds. The expanded
  fault cohort and independent public journeys are still pending at this point.
- Source is frozen for those runs: shared review engine
  `3704ce520b35cf5e660984c43838ed9ef508b35af10800445068d8c5a0a42e9b`,
  batch wrapper module
  `5420498edb159820ecb636c8c52289f30e47f4fedb660dee12177e5f01203895`,
  record wrapper module
  `1dc5cc64a1c9cedd7269317351e635aa5b6a2eb48c41966e6180137cda77abc6`.
  Existing fresh/resume definitions and broker source are unchanged.
- The separate cross-app whole-registry diagnostic is prepared to use real
  public app registration after the original pre-claim cut. It must report the
  actual refusal without treating that refusal as desirable concurrency UX or
  silently changing approved scope. No client archive or provider is involved.

## User-requested new-session handoff, 2026-09-08

The user requested a planning-only handoff to a fresh session, with execution
after plan approval using their selected Astra/high setting. Stop further
implementation and tests; preserve the dirty worktree. The handoff records
verified results separately from the interrupted fault/public-journey cohorts,
whose final outcomes were not recovered. The unrelated-app registration
diagnostic reproduced a whole-registry prerequisite refusal without any
selected-session drift; this is still an unfixed behavior, not acceptance.

The local starting instructions, `2026-09-08-new-session-plan-handoff.md`,
contain the current local/remote SHAs, release state, remaining work, minimal
reading order and the developer/client boundary. No new commit, push, release,
client mutation or cleanup was performed for this handoff. Earlier agent work
was interrupted; a targeted process-name/argument check found none of the
recent original-review/concurrency test processes still running.

## Approved continuation-scope completion, 2026-09-08

The user approved the planning-only reassessment and requested implementation
of one bounded unit: complete the pending intake original-review extension and
allow original intake/Git continuation after unrelated app registration. Keep
the existing six-release train and unfinished branch at `4e047209`; preserve
the 16 modified and five new files already present. Execution uses the user's
selected GPT-6 Astra / High setting without raising it.

Remove only the whole-registry equality prerequisite in intake `_current` and
Git `_current_scope`. Retain current claimed binding, actor/pending/original
evidence, held lock and all domain preimage checks. Stored original registry
digests and approval bytes remain immutable; registry transition CAS is not
changed. The record workflow already uses the intake guard. No new production
command, format, authentication layer or client operation is introduced.

Acceptance is the existing pending eight-case private review cohort, two
public review journeys, actual unrelated-app original resume/review in batch,
record and Git, current-owner/CAS and affected Git interruption regressions,
followed by bounded independent review and updated acceptance records. Reuse
the unchanged public routing/transport result (101 passed) and avoid full
suite, installed-wheel and scale repetitions for this development slice.
All new test outcomes are pending until their terminal exit is recorded.

No client archive, runtime, credential, provider, feedback ledger or shared
PATH executable is changed. Completion of this unit is not v0.4.20 release
acceptance. Previously failed diagnostic evidence remains historical evidence.

- The previously unfinished private original-review cohort completed all eight
  tests in 387.956 seconds, exit 0, no skips, on the corrected current-owner
  guards. Both intake families exercise approval absence/presence, cancellation,
  repeated preclaim cuts, existing started claims, source and copied-output
  preimages, corrupt/ambiguous/failed claims, missing keys, provider-entry claim
  insertion and origin/evidence drift. No private-test correction was needed.
- Independent read-only review found no actionable defect in the two guards,
  pending original-review implementation, public routing and changed journey
  tests. This is static review, separate from the public functional run now
  pending. Python 3.10 grammar checks passed for the three relevant production
  modules; functional execution is Windows Python 3.12, not cross-platform CI.
- All nine actual public/registry journeys passed in 778.690 seconds, exit 0,
  no skips, without further product or test corrections. The two previously
  unverified original-review journeys now include real unrelated-app public
  registration after the retained preclaim cut. Existing batch and record
  CLI/MCP pairs likewise register an unrelated app after receipt publication
  and before original resume. A's binding, actor, claims and original bytes
  are unchanged by registration. Completed replay remains read-only.
- The Git MCP pair registers an additional unrelated app after A's original
  pre-push or preclaim interruption. Both retain the exact Git bundle/context,
  verify real local-bare remote refs/blobs and exclusions, and forbid replanning,
  replacement context/claim and duplicate commit or completed-replay effects.
  The converted registry diagnostic also proves the corrected guard admits
  unrelated registration but actual pause still prevents native review and
  domain writes. Historical refusal evidence was not relabelled as success.
- The remaining current-scope, Git review/interruption and registry-CAS cohort
  is running serially. Full release/platform/installed/scale checks and client
  execution are not included in these source-functional outcomes.

Reproduction uses Python 3.12.10 from `wom-kit`, with source/test import roots
`src;tests` and UTF-8 enabled. Each cohort runs through `python -m unittest -v`
(public and regression cohorts additionally use fail-fast):

| Cohort | Exact modules or selectors |
| --- | --- |
| Private review | `test_v0420_source_intake_original_review` |
| Public and registry | `test_v0420_source_intake_original_review_public_workflow`, `test_v0420_source_intake_registry_concurrency_diagnostic`, `test_v0420_source_intake_batch_mcp_public_workflow`, `test_v0420_source_intake_record_public_workflow`, `test_v0420_git_backup_mcp_public_workflow` |
| Current scope | `test_v0420_work_session_scope.CurrentSessionScopeTests` |
| Git review | `test_v0420_session_git_original_review.OriginalGitReviewTests` |
| Git interruption | `test_v0420_work_session_git_workflow.SessionGitWorkflowTests`: `test_started_before_first_checkpoint_resumes_exact_original_without_planner`, `test_partial_commit_cut_resumes_without_second_commit_or_new_review`, `test_underlying_writer_refuses_changed_pending_selector_before_git_effect`, `test_proven_git_completion_survives_later_ownership_loss_without_actor_cas` |
| Registry CAS | `test_v0420_work_session_registry.SessionRegistryTests.test_duplicate_claim_cas_does_not_replace_first_owner` |

Frozen production SHA-256 for these runs:

| Module | SHA-256 |
| --- | --- |
| `work_session_source_intake_workflow.py` | `b14b395016fc57a210df1a60c98863f587e65e8b0e8592aa20351f61ddd00dc2` |
| `work_session_git_workflow.py` | `9eb216328f176bc99884d058d9da9f85b90a91af8035ad66b91b69a4a8adb1d9` |
| `work_session_source_intake_rereview.py` | `3704ce520b35cf5e660984c43838ed9ef508b35af10800445068d8c5a0a42e9b` |

The shared review engine hash is identical to the handoff. The previously
passing 101 routing/transport tests and their unchanged public source are
reused as supporting evidence, not added to this run's executed test count.

- The final current-scope/Git/CAS cohort passed all 28 tests in 863.320
  seconds, exit 0, no skips. This includes 17 current-owner tests, the five
  existing Git original-review cases plus a new real unrelated-registration/
  pause refusal, four existing Git interruption/pending/completion cases and
  the duplicate-claim CAS case. There were no failed runs or runtime fixture
  corrections in any of this unit's three cohorts.
- Total newly executed functional coverage is 45 tests, all passed. Registry
  CAS, the common approval broker and the three original bundle codecs were
  independently compared with HEAD and are unchanged. The review engine still
  has the handoff hash; only the two excessive live-registry comparisons were
  removed from product behavior in this turn. Existing uncommitted routes and
  wrappers were preserved and verified rather than recreated.
- The acceptance register now reflects v0.4.19's completed release/evidence
  merge and the actual v0.4.20 partial milestones. It does not present the
  historical `planned` rows as missing implementations. The bounded original
  continuation unit is development verified; all-writer/effect coverage,
  source capture/general document backup and final v0.4.20 release conditions
  remain unfinished. No version bump, commit, push, PR, release, client mutation
  or unfinished-worktree cleanup is part of this closeout.
- Final hygiene initially found two Markdown links to the local handoff, which
  is excluded by the existing `/meeting-minutes/` ignore rule. The handoff was
  preserved locally; only those public-link presentations were changed to
  plain code references. No ignore rule or checker was weakened, and no private
  handoff was force-added. Korean language, public privacy (zero findings) and
  runtime skill checks passed. Only the failed link check needs a rerun.
- The targeted link-check rerun passed, exit 0. All four final hygiene checks
  now pass; functional tests were not repeated for this link-only correction.
  The reviewed development unit and its acceptance records are complete.
  Changes remain uncommitted in the preserved feature worktree for the next
  approved development checkpoint, with v0.4.20 release gates still pending.

## User correction: continue the complete approved train

The user clarified that the completed continuation unit must not be confused
with completion of v0.4.20 or the accumulated recovery work. They explicitly
authorized continuing the existing v0.4.19-v0.4.24 plan without stopping to ask
again at each development unit or release: "아니야 그냥 쭉 해도괜찮아".
The preceding unit-only stop is superseded by this instruction.

Continue implementation, focused verification, independent review and each
release's full required acceptance/merge/tag/public artifact/evidence closeout
in the accepted dependency order. Keep short milestone records rather than
replanning or asking for routine permission. Preserve all unfinished work and
reuse verified source evidence. The selected Astra/high setting and developer/
client boundary remain: no client archive, runtime, credential, provider or
feedback-ledger writes and no shared PATH replacement. Actual client execution
and independent client outcomes still follow the public product release.

First preserve the verified original-review/continuation slice in a development
commit on the existing branch, then continue the unfinished v0.4.20 writer,
effect, source-capture and backup ownership integration. A source checkpoint
does not imply all-writer coverage or release completion.

## Local recovery binding preservation checkpoint, 2026-09-08

The verified continuation unit was committed and pushed as
`35fb4e58dbb78436e72cd7606c97e2c7e4b6faaa`; the feature branch's remote ref
matched that commit. Work continues under the user's complete-train approval.

Before composing existing local title/locator/objet recovery with current
session ownership, inspection found three existing manifest transformations
that omitted the optional `WorkSessionBinding`: composite, revert, and
observed-post subset compensation. Six product lines now preserve that exact
binding, refuse mixed sessions/revisions and bound/unbound composite members,
and require a subset's historical binding to match its retained parent. This
does not retrofit a binding into any old approval or assign legacy documents
to the caller. No new command, schema or approval mechanism was introduced.

`test_v0420_local_recovery_binding` (six new cases) and
`test_local_recovery_execution` (12 existing cases) passed together: 18 tests,
11.320 seconds, exit 0. Tests include actual private-control round trips,
one-field observed-post selection, mixed identity refusal, exact parent
membership, and the existing interruption, native approval/resume, subset
supersession and field-local revert preserving later unrelated body changes.
Six unbound manifest/control/approval-context golden digests were obtained by
executing the actual `35fb4e58` module against the synthetic fixtures, then
matched against the final code. Independent read-only review found no
actionable defect; it did not repeat tests.

This is preservation of an existing data contract, not a completed session
writer family. Local recovery still needs a caller-held session execution
route, original context/actor integration, and authenticated whole-document
backup evidence. Neither the human-artifact registry's caller-supplied hash
nor a field receipt alone proves ownership of an entire changed document.
The remaining v0.4.20 coverage and later release batches remain open.

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
