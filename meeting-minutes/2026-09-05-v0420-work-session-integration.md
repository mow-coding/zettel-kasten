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

Pending integration remains explicit: public work-session CLI and MCP routing,
native production orchestration, durable private plan discovery and automatic
resume, cancellation-aware lock waiting, all-writer ownership enforcement,
consistent read generation, full artifact/fate aggregation, responsibility
assignment and session-scoped Git selection assembly. No public v0.4.20 version
bump, PR, tag, wheel or client application has occurred.

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
