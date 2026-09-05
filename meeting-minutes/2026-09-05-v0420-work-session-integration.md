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
