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
- Candidate `2e42aa99eee5e0a8d1d1978d9c4134f5e5637dfb` was committed and
  pushed cleanly. Full CI run `33953444526` retained the earlier failed run;
  it is not a retry that erases that evidence.
- Its Windows installed gate `101272360210` passed the extended actual-wheel
  journey, including real corruption repair, the durable-intent process exit,
  fresh-process identifier-free resume with the same approval, independent
  post-repair no-op and real source/ref drift refusals. Candidate wheel SHA-256
  was `4f9e5f45523b3407278bd99084a36cf6e9a19267e90715691af6b978264b0e38`.
  This is installed candidate evidence, not a public release or client result.
- Measured seconds in that gate were update 189.469, healthy no-op 71.875,
  source drift 71.844, ref drift 70.984, repair until interruption 124.890,
  fresh resume 193.875, and independent repaired no-op 70.609. Doctor's first
  status was approximately 0.047 seconds with a maximum progress gap of 5.093
  seconds. The complete checker passed with its original limits and removed
  its temporary environment; neither failed local run was retroactively passed.
- This candidate still failed current-inventory count assertions in two
  historical test modules. Their current-parser sections and three current
  capability documents now describe 46 available, 68 fixed-closed and 201
  approval-unexposed paths, including ten conditional scopes. Tests additionally
  prove the separately unsupported cancel reason and preserved read-only
  control routes. Historical release counts are unchanged. Sixty-three focused
  tests and 307 subtests passed, followed by the additional Notion inventory
  assertion. Resource synchronization passed with no additional packaged diff.
- Windows shard four also reported two live-runtime observations as unavailable
  where its synthetic no-op tests expected passed/failed. Those observations
  did not authorize reuse or repair. Their cause is being investigated separately
  from the successful full installed journey; passing that gate does not waive
  the failures. Remaining jobs are preserved through completion before another
  consolidated candidate is pushed.

- The final no-op test observer preserves original calls/results/exceptions
  while recording only fixed verifier boundaries and bounded OS error numbers.
  Named `lstat`, `open` and `fstat` exception observations are limited to the
  verifier's owner thread; no additional reads, retry, global trace/profile or
  raw path/exception text is introduced. Unknown identity or stream-read causes
  remain unknown. The final actual eight-case Windows fixture passed once in
  123.35 seconds (eleven subtests); its earlier CI cause is still unconfirmed.
  Root's combined observer/current-inventory/control cohort passed 74 tests
  in 13.911 seconds. Neither result replaces the required next full CI.
- Python's [Windows stat changes](https://github.com/python/cpython/blob/main/Doc/whatsnew/3.12.rst)
  and historical [filesystem observation issue](https://github.com/python/cpython/issues/111856)
  were checked as diagnostic context. They do not establish the cause of this
  candidate's failures, and no identity guard was removed on that assumption.
- Windows shard one finished its 1,469 unittest cases and 113 native/authority
  pytest cases successfully, but its next cross-platform lane exposed an actual
  delegated-grammar regression (98 passed, one failed). Root reproduced that
  failure unchanged: the shared availability gate replaced the established
  private finder's usage error with a generic mode-denial response.
- The narrow correction preserves unavailable syntax in the shared capability
  record while allowing only the two existing trusted raw delegates to render
  their own content-free usage error before any archive execution. Other denial
  reasons, approval checks and the runtime guard are unchanged. The original
  failing historical test is unchanged; two new tests that had accidentally
  specified the incompatible behavior were corrected. Independent root review
  found no additional blocker. Eighty focused tests and 82 subtests passed in
  68.90 seconds, including actual synthetic finder and source-coverage behavior.
- The exact five-module cross-platform pytest lane that exposed the regression
  then passed all 99 tests in 34.90 seconds. Independent final review of the
  bounded OS observer found no additional blocker. All four release-readiness
  gates and the 169-resource synchronization check passed. This candidate is
  recorded locally while the preceding run's final Windows shard completes;
  pushing early would cancel evidence that is still being collected.

## Installed-only failure: diagnose once, retain the original evidence

- The user asked to continue after an apparent interruption. Development
  continued in the existing worktrees; the client archive and runtime remained
  read-only. Candidate `10e5eb1e` completed all Ubuntu/Windows test matrix jobs
  successfully, but its installed-entrypoint job failed. It is not releasable
  on the strength of the other passing jobs.
- The parent checker previously discarded bounded child stdout after a nonzero
  exit. A shared, strict diagnostic contract now retains fixed error classes,
  allowlisted reason codes and registered repository source coordinates while
  still failing the job. It excludes exception messages, local values and
  arbitrary paths. An initial-update-only diagnostic has a distinct schema and
  cannot satisfy the complete installed journey. A bounded, exact-new failure
  artifact preserves this observation when the process output is lost.
- Two temporary diagnostic-launcher mistakes were separately reproduced and
  corrected: a function used in place of the `Popen` class broke a later standard
  library subclass import; combined console flags could briefly leave a console
  host in the checker's process job. These are harness faults, not the product
  failure. No product containment rule or job limit was weakened to hide them.
- Reusing the preserved installed candidate avoided repeated builds and full
  updates. Its failure was before the approval broker: the real candidate
  `archive_cli --version` could not import the pinned native Unicode dependency.
  Seven product source files matched the candidate wheel. Candidate and bootstrap
  native binaries also had identical hashes, sizes and AMD64 machine types.
- The actual native binary path was 265 characters. Loading that same file with
  CPython's DLL flags failed with Windows error 206 using its ordinary absolute
  path, but succeeded using the extended-length spelling. A memory-only path
  diagnostic then ran the real CLI successfully in 23.360 seconds, with the
  exact expected version and no stderr. This proves the observed loader cause;
  it is not a product launcher fix, a completed update or client recovery.
- The selected correction is limited to the pinned native Unicode dependency's
  import boundary. It must retain the import system's selected file and engine,
  without changing global search paths, Windows registry settings, project
  location, runtime identity checks or approval. Both metadata and credential
  normalization must use the same pinned engine; dependency failure must not
  silently select the standard library's different Unicode database. Genuine
  long-path native loading and a newly built complete installed-wheel journey
  remain required after implementation and independent review.
- This boundary follows the documented [Windows extended-length path form](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation)
  and Python's existing [extension loader and module specification APIs](https://docs.python.org/3/library/importlib.html).
  Neither source is treated as evidence that all possible Windows filesystem
  operations or native dependencies already support long paths.
- Independent review reproduced an initial compatibility regression in the
  adapter: a short dotted native path loaded normally but the new boundary
  rejected it. Applicability is now decided before strict long-path checks;
  short paths delegate unchanged. The same native-file comparison then passed.
  This was corrected rather than redefining a formerly valid import as invalid.
- The final adapter/metadata/Unicode/credential cohort passed 65 tests and 23
  subtests in 15.34 seconds, including actual long-path native loading and a
  damaged binary in separate processes. Ordinary concurrent import sees only
  the fully initialized shared module; import failures leave no cached partial
  module or reflected private exception context. The independent source review
  found no additional blocker. Root also independently passed the fifteen
  installed-failure observation tests in 18.294 seconds. Final installed-wheel
  and supported-platform evidence is still required for this new candidate.

## Candidate import correction exposed a coupled index contract

- Candidate `17ee34d5` fixed the observed long-path native import, but its full
  CI exposed a separate integration regression: changing the metadata helper's
  import lines changed its exact source hash. The index authority pins that
  helper and the generated singleton metadata SQL also embeds its hash. The
  focused normalization cohort did not cover that downstream contract. It was
  insufficient acceptance evidence, and this candidate must not be released.
- Merely refreshing the hash and generated schema is not automatically safe:
  an existing index retains the old exact SQL CHECK, and the current rebuild
  validates that DDL before replacing rows. An import-path correction should
  not silently introduce a new legacy database migration. No pin, schema or
  migration edit was made while the smaller compatibility option was reviewed.
- The new complete local installed checker failed its unchanged 1,200-second
  runtime-child limit during repair continuation. The original update, healthy
  same-version no-op, source/ref drift refusals, repair preparation and cut
  validation had passed. The first update took 434.453 seconds and repair
  preparation took 281.593 seconds; these are observations, not performance
  acceptance. The final diagnostic says incomplete/failed and cannot be counted
  as a successful installed journey. Earlier preserved failure fixtures remain
  separate evidence; the full checker's internal temporary fixture was cleaned
  by its existing failure cleanup.
- The corresponding CI installed journey failed during repair continuation,
  and a Windows source journey independently reported an invalid transaction
  transition during its first actual update. Neither has yet been attributed
  to the metadata pin regression. The observer is being extended only with
  fixed registered transaction-function coordinates to identify the actual
  refusal; it does not collect state values or raw exception text.
- Work continues in the existing development worktrees. The integration PR
  remains a draft, no release/tag or client completion is claimed, and the
  client runtime, archive, credentials and provider state remain untouched.
- Independent design review selected a lazy, one-dependency standard finder
  instead of any legacy-index migration. The normalization helper's exact
  original bytes and existing generated schema remain unchanged. This revises
  the earlier import-hook restriction explicitly: only process-local finder
  registration changes, not the computer PATH or package search locations.
  Standard Python import owns module locking, initialization and cache cleanup.
- Review then reproduced a one-shot path-entry finder succeeding with one
  normal selection but failing when the initial hook caused a second lookup.
  The hook must return an already selected short/custom specification unchanged;
  only the exact long Windows native specification may be transformed. This is
  a compatibility correction, not permission to override custom precedence.
- The bounded existing actual update/no-op/revalidation source journey passed
  once in 627.67 seconds. Its seven CLI cases shared one fixture; this duration
  is not a measurement of first update alone. The CI transition failure was
  not reproduced, so it remains unconfirmed, not fixed by this local result.
- Reading the failed installed CI log also showed that repair-worker failure
  evidence was lost before reaching the parent. The same strict content-free
  observer is therefore being connected to that one original resume invocation.
  Only two fixed diagnostic stages are accepted. Unknown or malformed child
  output remains a generic failure; no retry, deadline extension or success
  schema change is introduced.
- The final lazy-hook/metadata cohort passed 51 tests and 33 subtests in
  21.73 seconds. The separate existing Unicode, credential, index/rebuild and
  startup cohort passed 179 tests and 125 subtests with two host-dependent
  skips in 76.05 seconds. A thirteen-case POSIX spec-factory simulation passed;
  it is not real Linux execution. Windows-literal spec fixtures were corrected
  because POSIX `spec_from_file_location` otherwise converts that spelling to a
  POSIX path. Actual Windows native-extension tests remain unmocked.
- Independent native-import review directly compared the helper with its prior
  source bytes and confirmed unchanged schema/pins. It found no further
  release-blocking issue in this bounded correction. The documented limitation
  is an extra lookup after a missing path specification; later meta-finder
  fallback is retained rather than replacing the interpreter's path finder.
- The new repair observation initially reached an old first-update-only reason
  check and failed two small tests. It now accepts exactly the two registered
  stage/reason pairs and refuses cross-stage impersonation. The final twenty-two
  diagnostic tests and 25 subtests passed in 30.22 seconds, including real
  nonzero-child output forwarding through the strict outer parser. Failure of
  a harness postcondition after successful CLI return remains a generic failure,
  not a claim that every possible cause is now captured.
- Root independently ran the final combined native-import and failure-observer
  files unchanged: 39 tests and 58 subtests passed in 34.02 seconds. Its separate
  three actual native/index/cold-version cases had also passed in 20.33 seconds.
  These overlapping cohorts are not summed as unique test coverage. All four
  release-readiness gates and the 169-resource synchronization check passed.
- The canonical checkout remained clean and matched local main, origin/main
  and the actual remote ref. The only open PR remained the draft integration
  PR; open secret alerts were zero at this check. That alert count is not a
  no-leak guarantee. Final full CI and installed public workflow must still
  pass on the consolidated candidate; no prior success substitutes for them.
- Independent review of the final repair observer found no additional blocker.
  It verified original-call forwarding, bounded stage/reason pairing, no raw
  private values and unchanged writer, cut, timeouts and postconditions. The
  reviewer did not claim an additional test run or a product recovery success.
- Execution order was revised for efficiency after this candidate froze: the
  previous failed run had twelve completed jobs and one Windows shard still
  running. Its completed evidence is retained, but the remaining old-candidate
  job is superseded by the consolidated candidate's complete new matrix. That
  unfinished old lane is not counted as passed or fully audited. No new
  candidate check is skipped and no prior candidate result waives a release gate.

## Installed acceptance passed; remaining Windows fixture failures

- Candidate `3423028f` passed the complete installed public Windows workflow
  in CI run `33963274478`, including the formerly failing repair continuation.
  The candidate wheel SHA-256 was
  `9eed1df1c08cab723ec43f9cfd077a9a4040c536edb87013d0d1b7f3a4d34c3e`.
  This is development installation acceptance, not a published release or
  client recovery. The readiness gate, all three scale gates and all four
  Ubuntu test shards passed. Remaining Windows failures still block release.
- Windows shard 3 reported one partial-write interruption marker timeout.
  The existing twenty-second deadline includes cold imports, hook setup and
  reaching the actual writer checkpoint. A single local execution passed but
  measured import completion at 17.375 seconds, writer start at the same point,
  and the checkpoint at 18.016 seconds. The actual writer segment was 0.641
  seconds. This demonstrates a tight setup-inclusive fixture budget; the old
  CI log has no stage evidence and does not establish which phase timed out.
- Windows shard 4 failed before its noop test body: the initial runtime payload
  hash compared different directory identities before and after enumeration.
  Directory size is already normalized to zero; this is not the earlier size-
  only regression. The old log does not identify the changing device, inode,
  type, modification timestamp or attributes. One real local setup and healthy
  noop execution passed without reproducing that difference. The cause remains
  unconfirmed, and no production tree comparison is relaxed.
- Narrow test-only observation records changed identity field names at the
  exact original nested comparison, and fixed import/writer/checkpoint stages.
  It forwards original calls and errors, does not rescan the filesystem, and
  stores no raw path, stat values, private data or exception text. Independent
  review found no further blocker in this diagnostic slice. The first small
  cohort passed seventeen tests and 23 subtests; the actual one-shot fixture
  cohort passed three tests in 122.343 seconds. These are not proof that an
  intermittent CI failure has been fixed.
- Based on the measured startup cost, independent review accepted separating
  the test process's bounded startup budget from its unchanged twenty-second
  writer-checkpoint budget. This is a fixture correction, not permission to
  increase product deadlines, retry failed writes or waive an acceptance check.
  The implemented fixture uses one launch clock, a sixty-second startup
  deadline, the original twenty-second checkpoint deadline from the first
  valid ready observation, and an eighty-second absolute cap. A completed
  fixed-byte sibling outside the archive is published without replacement;
  stale, partial, wrong, late or changed readiness cannot extend the budget.
  Existing child-kill, live-at-checkpoint and fresh-process validation remain.
  The final helper cohort passed 24 tests and 37 subtests in 20.08 seconds;
  root independently reran it unchanged with the same counts in 19.68 seconds.
  One actual interrupted partial-write, fresh-process diagnostic and rollback
  passed in 38.765 seconds. Its import completed at 17.905 seconds, writer
  started at 17.921, and checkpoint arrived at 18.562. Product timeouts and
  production writers were not changed.
- Windows shard 1 subsequently reported one real candidate/finalizer test
  failure. Candidate install, static inventory, dependency/version/resource
  checks and new-process inspection passed before a privacy-safe generic
  refusal. Its log does not establish the underlying exception. That source
  fixture is being examined separately rather than attributed to either of the
  other Windows failures. The remaining Windows shard was allowed to finish
  and passed. This candidate's complete run therefore ended with all four
  Ubuntu shards, Windows shard 2, installed acceptance, readiness and all three
  scales passed, but three other Windows shards and the aggregate required-CI
  check failed. No candidate is merged or released on that result.
- The source candidate fixture now reuses `FirstUpdateObservation` around its
  original preparation, broker and safe-failure projector. Its one CLI call,
  synthetic approval helper, real writer and all success postconditions remain
  unchanged. Failed assertions show only the bounded existing diagnostic
  schema; synthetic broker entry is not reported as native UI observation.
  Independent source review found no further blocker in that two-file change.
  Root's frozen observer/forwarding cohort passed 25 tests and 25 subtests in
  37.56 seconds. The separately executed real source candidate test passed
  once, including its seven subtests, in 367.21 seconds. Its receipt, claim
  finalizer, cleanup and malicious Git-hook/filter defenses all passed. The
  old CI failure did not reproduce locally and remains unattributed; a local
  success is not evidence that an underlying product defect was fixed.
- All four release-readiness checks and package synchronization passed on
  this test-only correction. The next candidate retains production code from
  `3423028f` and runs the full matrix again with the startup/checkpoint clocks
  separated and the formerly silent source boundaries observable. It does not
  rerun an unchanged failed job until it turns green or waive any release gate.
- The parallel v0.4.20 public management checkpoint was independently verified
  and backed up on its own unfinished branch. Its source handler tests are not
  substituted for v0.4.19 acceptance. The canonical main checkout remains
  unchanged; the latest public release is still v0.4.18, with only the draft
  integration PR open. Open secret alerts were zero on recheck, not a guarantee
  that every possible disclosure has been excluded.

## New candidate: installed repair continuation remains blocked

- Candidate `d6d978d2` started full CI run `33966565133`. The installed Windows
  workflow failed in job `101307620994` at `repair_fresh_resume`, after 95.110
  seconds in that stage. This is a new failed acceptance result; the earlier
  candidate's installed success does not waive it. No release is authorized.
- The new bounded observer identified the actual nested refusal:
  `exact_human_approval_state_unknown`, from the original approval workflow,
  caused by `project_update_transaction_state_transition_invalid` at
  `project_update_transaction.py:8156`. The broker was entered, but runtime
  preparation was not entered in the resume process.
- The exact source branch rejects `classification.overall == "unknown"`.
  Thus at least one current component digest matches neither approved side;
  this is not yet evidence that event order, a directory, runtime bytes or the
  approval itself is wrong. The component and underlying observation remain
  under investigation. Neither that guard nor its digest comparison is relaxed.
- The previously failing Windows shard 4 passed on this candidate. Other
  matrix jobs are still being collected. Partial passes are not full CI,
  release completion or client recovery, and intermittent failures are not
  erased by an earlier or later success.
- A failure-only observer now composes the existing live-component helper,
  its original sub-observations, classifier and exact validator. It retains
  only fixed component roles, classification states, reason codes and source
  field names. It adds no filesystem query, retry or successful substitute.
  Mapping/result identity and owning thread bind a sample to the actual
  failed validation. Decisive unknown classifications take priority within
  the 32-row cap; the parent rejects impossible enum combinations as well as
  unknown/private values. Original results, exceptions and cleanup remain.
- The source candidate fixture enters the same observer, so its next failure
  will not lose those component boundaries. Root independently checked the
  combined observer, forwarding/restoration and source-fixture contracts:
  32 tests and 44 subtests passed in 24.57 seconds. The implementer previously
  passed the same count in 24.24 seconds. These are diagnostic tests, not a
  correction to the still-unattributed product failure.
- One local full installed-checker execution is underway. Only the diagnostic
  caller's temporary-directory cleanup policy differs: a failed synthetic
  fixture is retained for later inspection rather than automatically erased;
  the global tempfile module, installer, approval, writer, cut and original
  timeout are unchanged. This retained-fixture run is diagnostic evidence,
  not a substitute for the final unchanged public release acceptance gate.
- Run `33966565133` completed: all four Ubuntu shards, all four Windows shards,
  readiness and all three scale checks passed. Installed acceptance failed,
  so aggregate Required CI also failed. The new component observer is not yet
  in that candidate and these results do not resolve the installed refusal.
- The one local retained-fixture run also failed, but for a different observed
  reason: the unchanged 1,200-second journey budget expired with repair resume
  unfinished. The phase protocol was valid with 21 events. Initial update took
  490.313 seconds; healthy noop 124.734, source drift 122.687, ref drift 115.797,
  repair preparation to the cut 283.203, and cut validation 6.813. About 35
  seconds remained for the fresh resume worker. No classifier-unknown error
  was observed before termination. This is neither a pass nor proof that the
  CI cause was fixed. The original synthetic wheel, runtime, approval and
  transaction were retained; all contained processes were confirmed stopped.
- The next bounded diagnostic inspects that exact interrupted state and, if
  its original continuation is valid, runs only the original resume worker.
  There is no rebuild, new approval, extended full-journey deadline or loop
  rerunning the full checker until success. Its result remains independent
  diagnostic evidence and cannot replace final public acceptance.
- That selected original resume passed in 407.953 seconds after a read-only
  exact-journal precheck. The same wheel and driver were used, with zero new
  native approval, download, preparation or initialization. Independent caller
  checks confirmed the same claim file set, unchanged older succeeded claim,
  the original started claim becoming succeeded, unchanged pin and launcher,
  exactly one added domain receipt, and repaired package bytes matching the
  original wheel. All contained processes then exited. Thus the additional
  timeout-induced interruption was recoverable with original authority.
- This remains separate diagnostic evidence. The full local installed gate
  failed its fixed total deadline, and the CI unknown-component failure did
  not reproduce. Production bytes have not been changed on an unproven cause.
  The next exact candidate retains that failure history and adds the reviewed
  component observer to collect the decisive original state if CI fails again.

## Preparation refusal on the next diagnostic candidate

- Candidate `48eca53d` was pushed with the original production code and the
  reviewed component observer. Run `33970833399` installed job `101318924564`
  failed during initial update in 65.015 seconds, before the approval broker.
  Runtime preparation entered and returned; the existing field-level result
  reported failed revalidation. No nested exception or repair continuation
  was reached. This is different observed evidence from the previous unknown
  component refusal, not a confirmed common cause or a successful correction.
- The failure projection had retained only overall preparation state, dropping
  already available per-check results. It now forwards fourteen fixed check
  names and their states, with explicit unclassified for missing/invalid
  observations. Compared values, arbitrary reason strings and paths are not
  copied. No additional query, retry, timeout or product behavior is introduced.
- The parent accepts only the exact fixed shape and rejects an inconsistent
  aggregate when all individual states are known. Known allowlisted blockers
  can use the existing reason-code list. Independent review caught a combined
  list saturation defect in that projection; the final deduplicated list is
  now capped at 32, with a 65-code saturation regression. This correction is
  diagnostic-only, not evidence that the preparation refusal has been fixed.
- The final four-module diagnostic cohort passed 36 tests (unittest-reported
  1.921 seconds, excluding module collection/startup). All four readiness
  checks and 169-file resource synchronization passed. Independent review
  confirmed the final cap correction and found no further actionable issue.
  A new exact candidate still requires full CI; prior failures remain evidence.
