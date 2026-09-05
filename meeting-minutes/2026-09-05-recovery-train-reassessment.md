# Recovery train reassessment and implementation restart

Date: 2026-09-05
Status: accepted; v0.4.19 implementation resumed, not released

## Conversation and correction

The user requested a fresh evidence-based assessment before continuing the
existing six-release recovery and operations plan. The user explicitly said
that beta testers can wait: dependency correctness and avoiding repeated work
matter more than moving an apparently urgent feature ahead of its foundations.
The resulting plan was explicitly approved for implementation.

The audit covered all 162 Markdown feedback documents and three JSON evidence
documents in the supplied feedback collection. Original private documents,
labels, credentials, filesystem paths, provider identifiers, and raw client
content are not reproduced here. Later corrections, withdrawn claims, actual
client successes, public releases, and unperformed client actions were treated
as different kinds of evidence.

The conclusion was neither that nothing worked nor that shipping commands
resolved the workload. Several single-item creation, publication, capture,
linking, and deduplication tasks have real successful client reports. Other
previously usable operations were closed during the exact-approval migration.
Tests of individual commands repeatedly failed to prove the complete user
journey through preparation, approval, execution, restart, and verification.

The previous near-ready assessment of v0.4.19 was corrected. A synthetic replay
still rejected both runtime and source directories when only directory
`st_size` changed from zero to an allocated size. The installed bytes stayed
identical. Also, the same-version no-op built a complete candidate before
recognizing the existing runtime. Doctor's count-scale object files were only
30 bytes each, so that benchmark cannot prove large-byte client performance.

## Starting checkpoint

- Public main and the observed remote main were `95e3a8b3`; latest release was
  v0.4.18. There was no open PR or open secret-scanning alert.
- The preserved integration branch was 15 commits ahead of main at
  `17f6c77c`, with 52 existing modified or untracked paths.
- v0.4.19 had not been released. Later releases in this train had not begun
  integrated implementation; reusable older domain components already exist.
- No client archive, runtime, credential, provider, feedback ledger, or shared
  PATH installation was modified during assessment or this restart.

An absence of open secret alerts is not proof that a repository contains no
private material. Every public candidate still needs the privacy gates.

## Revised sequence and omitted outcomes restored

1. v0.4.19: runtime/source directory identity, a verified pre-download no-op,
   bounded predecessor recovery, four-state observations, capability truth,
   current-index behavior, meaningful Doctor performance, and hidden background
   process launches.
2. v0.4.20: work-session identity and compatible legacy resume, common local
   target preview, complete pagination, and **working session-scoped Git
   commit/push with remote verification before any subsequent client repair**.
3. v0.4.21: discard/restore, semantic revision/restore, publish/retire/edge
   batches, source-property recovery, title and receipt audit, locator/occurrence
   repair, already-captured object outcomes, and each operation's actual revert.
4. v0.4.22: reuse existing secure credential components and complete the Notion
   recovery chain, including the distinct historical locator recovery cohort.
5. v0.4.23: reuse existing object-store transport, verify complete remote bytes,
   safely offload approved local bytes, and automatically rehydrate on demand.
6. v0.4.24: relation acceptance, artifacts and external registered work roots,
   historical approval/source evidence review, exact legacy retirement, final
   session backup, and evidence-backed feedback accounting.

Common preview moves to v0.4.20 so later writers do not each invent it. Old
approved manifests and checkpoints remain immutable: session introduction may
record responsibility but cannot silently change the operation already
approved. A real source/pin/field conflict is not repaired by inventing evidence.

Withdrawn search-absence reports and already-confirmed capture, paired intake,
context, and duplicate-row fixes are preservation/regression requirements, not
new implementations. IMAP, Tiro, and unrelated provider extensions remain
explicit separate backlog items. They are not counted as resolved by this train.

## Implementation split and feedback loop

- Runtime work owns the shared runtime module and dedicated new synthetic
  identity/no-op tests.
- Doctor work owns the scale fixture and associated performance tests.
- Integration owns service routing, cross-domain installed-wheel tests,
  documentation, independent review, supported-platform CI, publication, and
  cleanup. A separate read-only review checks capability and observation gaps.
- Existing dirty work is preserved. No branch, worktree, or temporary artifact
  is removed merely because it is unfinished.

Each completed implementation/test step is appended here or linked from the
acceptance register. Public completion and real client verification remain
separate. The client-side AI performs project updates, native approvals,
recovery, independent verification, and backup using supported WOM paths;
development does not perform those private writes.

## Durable specifications

- [Acceptance register](../wom-kit/docs/recovery-operations-acceptance.md)
- [Decision amendment](../wom-kit/docs/archive-infra-decision-log-2026-09-05-recovery-train-amendment.md)
- [Earlier chronological implementation record](2026-09-04-v0419-v0424-recovery-operations.md)

## Implementation and independent-review observations

- Runtime directory snapshots now ignore allocation size for directories only;
  membership, identity, file bytes, and reparse checks remain. Independent
  synthetic source-mirror tests also preserve identical bytes under a
  directory-size-only change and reject actual file changes.
- A retained-runtime verifier checks exact retained wheel/dependency bytes and
  trusted startup files before executing fresh-process probes. The updater
  uses this before candidate download/build and repeats the existing fourteen
  revalidation dimensions. Probe timeout or launch uncertainty is unavailable,
  not permission to repair. Independent review found and corrected that
  distinction before release.
- Public create-draft preflight now separates valid input from current-index
  write readiness. Missing/stale indexes have a supported action; unreadable
  state does not authorize index rebuilding. AI provenance dispatch uses the
  same predicate as the service, including mixed declared provenance.
- Public command-tag evidence distinguishes nine formerly exposed approval
  paths from unaudited history. Exposure is not proof of successful use and
  does not recommend an older-version approval workaround.
- The real synthetic CLI/broker/runtime journey exposed a further integration
  error: a successful no-op left terminal pre-intent control history that
  blocked the next ordinary preview. The correction uses only that invocation's
  exact abort receipt to compact its own history into the established inert
  proof. Partial cleanup must not return a completed no-op. End-to-end replay
  and fault validation are still pending at this checkpoint.
- The historical count-scale Doctor run passed operational 76.730083 seconds
  and deep 85.847179 seconds. Its 22,441 objects totaled only 673,230 bytes and
  its mint evidence reused two source/snapshot pairs. Those numbers are not
  large-object or client-performance claims.
- A separate varied-size/independent-source fixture exposed a materially
  slower run. No success has been assigned to that expanded gate. Diagnosis
  will reuse the exact synthetic fixture instead of regenerating it repeatedly.
- Reusing that fixture isolated the repeated-work defect: one ordinary inbox
  draft invoked the retirement write planner, which spent about 15.5 seconds
  revalidating the whole index. Doctor called that path for every draft. The
  read-only diagnostic is being moved onto Doctor's existing bound input
  observations; actual retirement plan/write guards remain independent.
- Four real Windows own-reservation closeout tests passed, including a
  competing writer. Review caught a generic result that reported no lock
  despite that successor lock; a fresh tri-state presence observation corrected
  the report without touching the successor's bytes.
- The actual installed-wheel journey is now part of the checker and runs from
  isolated installed modules, not imports from the checkout. Its first full
  local run is diagnostic while source corrections are still being finalized;
  only final reviewed candidate evidence can satisfy release acceptance.
- The required CI now includes both Doctor profiles and the existing real
  installed-wheel workflow checker. Fixture preparation/job timeout and the
  unchanged 180-second operational measurement are explicitly separate.

All listed changes remain development-candidate work. Full candidate CI,
publication, anonymous asset verification, cleanup, and client execution are
not complete at this checkpoint.

## Installed-flow and scale-fixture review checkpoint

- The real candidate-wheel updater/no-op/follow-on-preview/launcher journey
  returned validated success before a later legacy runtime-skill assertion
  failed. The full checker therefore still failed; the partial journey result
  is diagnostic, not final candidate or public-release proof.
- Broader release-document regression testing found five stale expectations:
  four current citation dates and one conditional-approval count. The current
  date expectations now agree with this candidate and the count includes the
  actual create-draft provenance predicate. Historical release dates and
  successful-use claims were not rewritten.
- The Doctor optimization initially missed genuine minted twins when their
  retired-receipt parent directory did not yet exist. Existing public
  mint/validate/retire regression testing found it; a narrow parent-absence
  observation corrected it without weakening the safe resolver. Four durable
  tests now cover that case plus completed-inventory source/receipt drift.
- Review of the expanded synthetic fixture found mismatched source and target
  IDs, which exercised unmatched drafts rather than genuine minted twins. Its
  earlier performance failure remains useful diagnosis, not genuine-twin
  coverage. The corrected fixture binds matching source/target IDs and is being
  generated once for the final mixed-profile measurement.
- In-process Doctor timing begins after imports. Fresh public-process startup
  is a separate acceptance measurement; a quick handler status must not hide
  interpreter/module startup delay. Installed-process evidence is being checked
  before claiming the two-second first-status target.
- A bounded compile-only reproduction measured about 6.24 seconds for the CLI
  module and 12.03 seconds for the service module. Project runtimes intentionally
  disable generated bytecode, so an early print inside the same large module or
  a Python thread cannot establish the complete startup/heartbeat contract.
  The chosen correction is a small public CLI entrypoint with a content-free,
  lifetime-bound preparation heartbeat and handoff to the existing reporter.
  Earlier target releases retain their original launcher module. MCP and old
  direct module invocation remain compatible; improved startup is measured on
  the new supported console and project-launcher paths.
- The corrected full mixed fixture completed deep verification in 132.827
  seconds with one complete hash per object. Its operational run stayed within
  180 seconds but returned a failing diagnostic, so the combined gate remains
  failed. The same fixture is retained to expose content-free error counts and
  isolate that discrepancy instead of rebuilding it or weakening the gate.
- A same-fixture operational retry completed all diagnostic and traversal
  checks in 120.296 seconds. That retry does not explain or erase the first
  failure. The candidate retains the discrepancy and requires fresh isolated
  CI with preserved error counts before any release decision.
- The small CLI entrypoint's initial eleven tests passed, including real
  compilation, first status, independent heartbeat, parent termination, and
  unchanged JSON stdout. The progress-name/default table is checked against
  the actual parser. The installed-wheel driver additionally measures the
  complete public-launcher Doctor process; that candidate run is still pending.
- The real partial-no-op cleanup test now continues through public CLI
  `--resume` without transaction, approval, or checkpoint identifiers. It
  reuses existing authority, opens no new approval, compacts the interrupted
  history, preserves domain bytes, and permits the next ordinary preview. The
  existing external-writer quiescence assertion remains required in this
  pre-session release. This extended case passed.
- A separate deterministic Doctor test reproduced a directory-allocation-only
  false boundary change after inventory completion. Root and inventory identity
  now exclude directory size only; file size, inode/device/type/reparse state,
  timestamps, and membership remain guarded. Combined real file/member changes
  still fail even when directory timestamps are restored. This independent
  reproduction does not establish the cause of the discarded first-run issue.
- Final bounded review found one service-level truth mismatch: approval replay
  correctly observed an unavailable index but still reported a rebuild blocker.
  Its blocker now uses the same fixed preflight reason. Four focused draft
  tests and independent replay passed; neither index rebuilding nor approval
  was enabled by unavailable evidence.
- Independent review of the startup implementation and its launcher/version
  boundary found no further actionable findings. Startup plus launcher tests
  passed with fifteen tests and thirty-one subtests. The source is being frozen
  for supported-platform CI and complete installed-wheel verification; none of
  these local results claims a published release or private client completion.

## First supported-platform candidate

- Candidate `90104abe03ce95235f1e390902bf9ebece175a6e` was pushed in draft
  PR #97. Its Windows installed-wheel job completed the real update, retained
  runtime no-op, follow-on preview, new-process runtime verification, public
  launcher progress, and existing installed workflow checks successfully.
  That wheel is candidate-specific evidence, not the final release asset.
- Both Ubuntu scale jobs then exposed the same immediate `IndexError` in the
  symlink-boundary inventory. A POSIX observation has nine tuple members, but
  its consumer read a Windows-only tenth member. A reduced real inventory
  reproduced the exact failing frame; the correction keeps the common
  hardlink test and reads the native Windows flag only on Windows.
- Regression coverage exercises the actual POSIX observation branch even on
  the Windows development host. Benchmark failures now retain only fixed
  exception classes and allowlisted repository source coordinates, excluding
  exception messages, local values, and absolute paths. Independent review and
  a fresh full candidate CI remain required; the failed run is not waived.
- The final local operational mixed-profile run before this POSIX correction
  passed in 90.811767 seconds, with first status at 0.254 seconds and maximum
  observed progress gap 5.014736 seconds. Source hashes were stable through
  that measurement. This result does not erase the earlier unexplained mixed
  failure and does not prove the separate public-process startup or client
  byte-scale performance contracts.

## Full-CI reconciliation before release

- The next candidate passed both Ubuntu Doctor scale profiles and the Windows
  installed public-entrypoint workflow. Its full test shards still failed;
  these green gates are not permission to merge or publish the candidate.
- The shared availability gate accidentally changed established JSON
  `lifecycle_action` names to handler names and ignored command-specific JSON
  defaults. Restore the public identifiers and parsed format defaults without
  invoking handlers or inspecting private prerequisites. The original blocked,
  no-write and privacy assertions remain. The first affected CLI cohort passed
  57 tests and 59 subtests with no expectation changes. Independent comparison
  against published handlers and current inventory also found the canonical
  `parcel` alias and the discard-draft action; both are corrected. An available
  session-evidence writer remains outside the fixed-closed compatibility map.
- Remaining test corrections distinguish intentional contracts from bugs:
  unavailable observation is not mismatch, skipped checks are not failures,
  diagnostics must not recommend a fixed-closed writer, and mutually exclusive
  execution modes fail before dispatch. A parser-known unavailable writer does
  not inspect a damaged runtime merely to produce another blocker.
- Native retained-handle legacy moves and exact deletions were already
  Windows-only. Their unsupported-platform result is now explicit. Portable
  schema, identity and refusal tests remain portable; only actual Windows
  effect/lease integration cases are Windows-scoped. No POSIX mutation safety
  claim is fabricated by weakening those primitives.
- A Windows two-process reservation test exposed an eight-second wait timeout
  mislabeled as state drift. Use a bounded thirty-second wait with distinct
  busy/unavailable results, keep the existing OS lock, and keep the independent
  progress reporter live. A deterministic hold exceeding eight seconds,
  timeout heartbeats, failed-wait classification and post-lock directory drift
  checks passed locally. Public propagation also passed fixed-code/privacy
  tests and the real synthetic Git-preparation path: a failed reservation did
  not invoke foreign-lock cleanup or native approval, and kept the pin and
  source HEAD. The remaining full shards are still being verified; no automatic
  repair or new approval follows contention.
- Subsequent local groups passed 30 CLI regressions plus the separately
  corrected conflicting-mode case, and 56 capability/quarantine/bytecode
  tests with 1,896 subtests. These are bounded local evidence, not a claim that
  the whole CI or the private client recovery has completed.
- Python 3.10 had one additional test import failure because a checkout-shim
  test imported Python 3.11's `tomllib`. It now checks the repository-owned
  literal project version without requiring that unsupported standard module
  or changing runtime dependencies. The real new-process shim test passed
  locally; the lowest supported interpreter still requires fresh CI.
- The full local version cohort's two remaining failures were corrected and
  replayed separately. Native junction-path admission and non-Git pre-admission
  now assert their actual early failure with downstream checks `not_reached`.
  The independent origin-unavailable case remains distinct from exit-code-one
  missing configuration and reads no remote URL value. A single fresh full
  candidate run, not an aggregate claim based on partial reruns, is required.
- v0.4.20 preparation remains isolated in its own unfinished worktree. The
  binding, preview, Git selection and registry slices are not yet one public
  workflow. Independent review corrected preview navigation reentrancy and
  retained the registry parent during private pending-image creation. Their
  passing component tests do not represent integration or release completion.
- All shards of candidate `c4333f947d1161a938187371dfcfd30d55f8d368` have now
  finished. The final Windows shard passed, but the aggregate run failed.
  Windows updater callback-contract failures and two interruption/replay cases
  require explicit reconciliation before a new complete candidate run.
- Independent review found that a busy/unavailable reservation does not prove
  an existing transaction exists: it can precede transaction creation. The
  diagnostic now leaves existence and required resume unconfirmed, advises
  inspection first, and offers resume only when matching evidence is found.
  It still grants no retry, new approval, repair, cleanup or lock-steal authority.
- Windows-specific failure reconciliation identified actual routing and replay
  bugs in addition to stale synthetic callback signatures. A completed v0.4.15
  cleanup tombstone was intercepted by the prewrite adapter; exact authenticated
  terminal cleanup must retain its original route. Bootstrap replay also compared
  a deliberately never-fetched sealed URL placeholder with the live wheel URL.
  Exact version/tag/filename/hash and live public-origin checks, not placeholder
  equality, define the retained supply identity. Focused interruption tests and
  other actually reachable predecessor boundaries are being rerun.
- Independent synthetic Git review reproduced selected-observation drift in both
  the v0.4.20 preparation and legacy v1 writer. A mutable convenience dictionary
  could disagree with approved source bytes. Reuse the strict private-bundle
  decoder to reconstruct and detach execution state before claims and writes;
  compare the exact approval context again at writer entry. New refusal tests
  passed for changed views and matching changed disk bytes, with no commit/push
  or private claim creation. A same-fixture comparison against actual predecessor
  source preserved canonical legacy bundle, manifest, source, commit-message,
  public-plan and approval-context bytes. Full Git cohorts remain required.
- The corrected legacy Git writer plus new security regressions then passed
  thirteen tests and two subtests. The isolated v0.4.20 Git cohort passed 23
  tests and 25 subtests; neither synthetic remote is a client remote.
- The original failing Windows updater group plus new pure boundaries passed
  nine tests and sixteen subtests. A final predecessor group passed nine tests
  and fourteen subtests, including actual v0.4.15 completed-original and
  completed-tombstone process exits and public resume with no replacement writer
  or new approval. Missing/tampered claim, checkpoint and context cases stayed
  refused. A cleanup-authority read-error injection also confirmed owned guard
  and runner release without private exception output.
- Supported automatic legacy scope is now explicitly bounded: exact prewrite
  recovery and authenticated completed-original/tombstone cleanup. Other
  ambiguous or changed legacy journals remain preserved and blocked, not
  silently counted as recovered. This source is frozen for a fresh complete CI
  candidate; no partial local test sum is substituted for that release gate.
- Candidate `dd6c1669d5d56130c2de3ee232c7e8f41ab9debb` was committed and
  pushed to the existing draft PR. Its installed-entrypoint, both Doctor scale,
  link-index and readiness gates passed, but the complete CI has not passed.
- An acceptance audit found that the installed-wheel gate proved installation
  and healthy same-version no-op but not real-wheel repair, process-loss resume
  or source/ref drift. The driver now observes real implementation returns to
  inject source/ref changes and exits a child after the actual durable runtime
  intent append. Fresh-process resume must reuse the old claim and prepared
  runtime without another download, preparation or native approval. Production
  verifier/writer results are not mocked. The existing time budget is unchanged;
  the extended complete local installed run is still being measured.
- Both Linux shard-one jobs exposed the same five dispatch fixtures that
  instantiated the production Windows key provider before their synthetic
  service seam. They now explicitly use the already-existing memory-only
  provider. The single-file derived-text assertion now matches the actual
  handler, including the public predecessor. Six focused tests and eleven
  subtests passed in 22.70 seconds; independent source review agreed. Linux
  execution still needs the next complete candidate CI.
- Windows shard three exposed two additional failures in the actual staged
  multi-group Git backup and runtime-repair interruption tests. They are being
  independently diagnosed without weakening source binding, claim authority or
  directory/file verification. A local repeat alone is not grounds to dismiss
  a CI failure or mark the release ready.
- The extended installed journey's first complete local run exceeded its
  unchanged 1,200-second budget. Its global profile observer imposed about
  10.5 times the cost in a bounded call comparison. Named, original-forwarding
  wrappers removed that global overhead (1.01 times in the same comparison).
  Actual implementation returns, durable append-before-cut and assertion
  semantics remain intact; independent review found no additional blocker.
  Twelve focused hook/diagnostic tests and eighteen subtests passed. A new
  complete installed run is in progress; the timeout is not repair evidence.
- Two local actual Git reproductions passed, and the real two-venv runtime
  repair test passed in 229.235 seconds. Neither reproduced the CI-only
  failure. Test-only diagnostics now retain fixed Git stages/error codes and
  unexpected runtime exception frames without adding retries or changing
  production guards. Their causes remain unconfirmed pending new evidence.
- Run `33949084334` then completed with a failing aggregate, preserving every
  job instead of cancelling the final Windows shards. Windows shard one had
  only the already-corrected derived-text assertion. Windows shard two exposed
  one additional real-update/no-op journey failure before the first update's
  privacy-safe result. That masked preflight failure is being traced; it has
  not been relabelled as a successful update or dismissed as test flakiness.
- A separate actual-dispatch audit corrected `operation-control`: its cancel
  writer never existed, despite an approval-available inventory entry. The
  shared inventory, suggestions, help and dispatch now report writer unavailable
  with the precise cancellation-unsupported reason, not a compound-approval
  migration diagnosis. Existing status/wait/recovery-plan read results stay
  unchanged. Fifty-two focused tests and 175 subtests passed; independent root
  review found no additional blocker. Packaged schema synchronization and the
  next complete candidate CI are still required.
- The wrapper-observed full installed run also exceeded 1,200 seconds and
  returned no final per-stage timings. This second failure means observer
  microbenchmark improvement did not establish whole-journey performance or
  repair completion. Another blind full retry was not started. The harness is
  being extended with bounded, content-free per-stage evidence so a timeout
  preserves its validated prefix and explicitly unknown unfinished work.
- The new first-update failure observer preserves actual call/result/exception
  behavior, bounded fixed error classifications and allowlisted production code
  locations without raw output, arguments, exception text or frame locals.
  Seven observer tests and three subtests passed. The exact Windows two-shard
  failing journey then passed once locally in 355.02 seconds, including actual
  first update, native/claim success, no-op, unavailable/timeout handling and
  post-proof drift refusal. Its CI cause remains unconfirmed; no retry policy
  or production verification was changed to obtain that local pass.
- Root separately ran the installed-checker contracts, runtime fault diagnostic
  and unsupported-control cases: 71 tests and 110 subtests passed in 29.71
  seconds. All four readiness gates and synchronized package resources passed.
  These results are not substitutes for the pending complete installed journey
  or the next complete supported-platform candidate CI.
- The public privacy gate caught a synthetic user-folder-shaped string in the
  new observer test. The fixture now uses a generic synthetic drive/path while
  retaining its private-marker redaction assertion; the scanner was not
  weakened. The privacy gate and seven observer tests (three subtests) passed.
- The installed harness now reports eighteen fixed stages through a separate,
  bounded stderr protocol. The parent validates sequence, exact keys, integer
  monotonic times and byte limits as data arrives, and retains only the valid
  prefix on timeout or malformed tail. An unfinished stage has unknown product
  completion and no invented duration. Partial observations cannot satisfy the
  final runtime proof. The 1,200-second limit, process-tree containment, actual
  writer calls, stdout result contract and temporary-fixture policy are unchanged.
- Independent review found two path-bearing error surfaces in the observed
  process launch and wheel-evidence read. Both now use fixed failure messages
  in this narrow path. Review also caught a Windows-only constant missing from
  a Linux-mimicking launch-failure fixture; only that fixture was corrected.
  No additional blocker was found in the final source review. Linux execution
  and full installed repair/resume success are still separate pending evidence.
- Root ran the consolidated installed-checker, phase protocol, unsupported
  control, runtime-fault and first-update-observer tests: 90 tests and 132
  subtests passed in 34.62 seconds. The next full CI candidate will exercise
  the extended installed journey with these observations. A third identical
  local full retry was not run, and neither earlier timeout was waived.
- All four release-readiness gates, synchronization of 169 packaged resources
  and the final whitespace check passed before this consolidated candidate
  checkpoint. The draft PR remains unmerged until the full matrix and extended
  installed journey are independently green at the same candidate head.
