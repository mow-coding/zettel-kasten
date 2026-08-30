# 2026-08-30 v0.4.15 interrupted project-update recovery

## User intent and operating boundary

- The user asked the development team to explain and fix a report that the
  latest WOM release could no longer write a Zet draft.
- The work must correct the recurring recovery failure, not weaken the archive
  safety guard or ask a human to inspect private implementation state.
- The public development repository is the only write scope of this task. A
  client archive, its retained update lock, credentials, provider state, and
  feedback ledger remain outside the developer-side write scope.
- A public release makes recovery possible. It is not evidence that a client
  update was recovered or that draft creation works again in that client
  project.

## Chronology and diagnosis

1. The failure was reproduced in a synthetic archive before changing the
   guard. Draft creation still reaches its normal writer in a clean, aligned
   v0.4.14 project.
2. A hard exit during a project-version update can leave the verified source
   mirror and candidate runtime at the target version while the active project
   pin and launcher still identify the prior version.
3. WOM deliberately retains a durable update lock in that mixed state. The
   project write guard then blocks every ordinary approved write, including
   `create-draft`, with `project_update_recovery_required`. This prevents two
   sessions from mutating an archive whose runtime identity is not yet
   coherent.
4. The actual product defect was the recovery interface. Resume required the
   operator to reconstruct the target, transaction reference, reviewer, and an
   opaque locator. Some of that state could disappear with the interrupted
   process or console, so the operator could not recover from ordinary visible
   state.
5. The hard-exit regression test had hidden this defect by enumerating private
   recovery storage and injecting the locator directly. That made the test pass
   through a route that a client must never need to use.

The recurring symptom therefore looked like a draft-writer regression, but the
root cause was an interrupted update plus an unusable resume contract. The
fail-closed write guard was correct and remains in place.

## v0.4.15 implementation direction

### Authenticated identifier-free resume discovery

- The ordinary human command contains only the project root, `--resume`, and
  `--affirm-external-writers-quiescent`.
- WOM validates either the live durable lock or the exact prior lock binding
  and verified absence at the supported lockless unlock tail, opens the
  already-authenticated private plan, and restores the target, transaction
  reference, reviewer, and exact approval context internally.
- WOM binds the already-existing recovery directory without creating it, reads
  bounded directory entries, and considers only authenticated records matching
  that reconstructed exact update context.
- A candidate must also satisfy the correct durable checkpoint guard for its
  current state. Authentication alone is insufficient.
- Exactly one authenticated, context-matching, checkpoint-valid candidate is
  required. Zero candidates, multiple candidates, invalid authentication,
  context drift, or checkpoint drift all fail closed before the domain writer
  runs.
- Discovery never creates a key, directory, lock, or claim. It does not display
  private paths, private values, or the internal locator.
- Postapproval resume reuses the already granted exact approval and does not
  show a second native approval prompt. A proven preapproval cancellation does
  not reuse nonexistent approval authority; it returns
  `fresh_approval_required`, and a later fresh update must request one new
  native approval.
- The ordinary human flow requires no target, transaction reference, reviewer,
  or internal approval locator. If the live lock and authenticated plan do not
  reconstruct one coherent operation, WOM stops before any domain write.

### One public command for preapproval and postapproval interruption

- A later audit found that the original seven-boundary matrix still used
  private cleanup helpers for the first two preapproval exits. That evidence
  overstated what a client could recover.
- The public `--resume` route now classifies the exact transaction before claim
  discovery. An empty locked reservation is durably aborted without recreating
  a missing lock. A complete sealed preapproval candidate is bound and
  cancelled only after exact preimages are reverified.
- A third boundary was added after the durable `lock_backlinked` checkpoint but
  before any approval claim. Authenticated discovery must prove zero candidates
  and the journal must contain only that preapproval checkpoint before the
  scaffold can be cancelled.
- Tampered or unauthenticated claim-shaped files are no longer treated as an
  empty claim store. They fail closed and preserve the transaction for review.
- The postapproval tail may be discovered after the exact lock unlink only when
  one sealed, backlinked, exact-journal transaction has reached the verified
  unlock tail. Missing or multiple candidates fail read-only.
- Preapproval cancellation is itself resumable: the matrix interrupts recovery
  after exact candidate cleanup and proves that a second invocation of the
  same public command completes cancellation without recreating the candidate
  or requiring a private identifier.
- All eight hard-exit boundaries now enter the same public CLI with only the
  project root, `--resume`, and the quiescence affirmation. Preapproval recovery
  returns `fresh_approval_required`; it never pretends that the update ran.

The hard-exit matrix now resumes with only the project root, `--resume`, and the
external-writer quiescence affirmation. It neither enumerates private storage
nor passes hidden recovery fields, removing the previous test-only escape
hatch.

### Narrow emergency feedback preservation

The normal write guard remains global while update recovery is pending. One
narrow escape route is added so WOM can preserve a new problem report even when
the update itself is the blocker:

- only `operator-feedback-compose --intent create` may enter the lane;
- the exact plan digest, explicit reviewer, and `--approve` confirmation remain
  required; this lane does not claim a native TaskDialog or exact-human claim;
- the lane creates only the new feedback body and its body receipt as domain
  records; a bounded cross-process mutex may remain as content-free control
  evidence, but it is not another feedback record and does not replace, edit,
  or release `version-update.lock`;
- it does not register feedback metadata, revise or supersede an existing
  report, mark anything delivered or resolved, or enable any other writer;
- an identical retry is idempotent and performs no second write;
- the project update remains explicitly in recovery-required state.

This lane preserves the user's words without pretending that normal archive
writes are safe. Draft creation remains blocked until the interrupted update is
recovered.

### Verified pip bootstrap contract

The project updater needs the exact public wheel SHA-256 recorded in the
running distribution metadata. A tool installer can install a valid public
wheel while omitting that archive hash, which makes the installation unsuitable
as update authority.

v0.4.15 therefore keeps verification strict:

- bootstrap instructions use the exact public wheel in a dedicated external
  CPython 3.12 virtual environment through `python.exe -m pip`;
- the installed-wheel verifier checks that pip recorded the same SHA-256 as the
  wheel bytes that were actually installed;
- a missing or malformed recorded hash fails closed and returns safe next
  actions;
- WOM does not delete an update lock, infer a hash, or lower the supply-chain
  check merely to make resume proceed.

## Developer and client responsibilities

The development session is responsible for:

1. implementing and reviewing the recovery path;
2. passing focused tests, full CI, privacy and path checks;
3. publishing and anonymously re-verifying the exact release wheel; and
4. providing a short client-safe recovery command sequence.

The client project is responsible for:

1. installing the verified release bootstrap in an isolated environment;
2. running resume with only its project root and the external-writer
   quiescence affirmation;
3. confirming that the source mirror, runtime, active pin, and launcher align;
4. starting a new project-runtime process and testing one ordinary draft
   creation; and
5. returning terminal receipts or equally durable evidence.

The developer must not delete or edit a client's update lock and must not write
directly into the client archive. Until the client-side sequence succeeds, the
correct status is “recovery implementation in progress” or “client-ready after
release,” not “client recovered.”

## Verification status at this checkpoint

The following focused results are confirmed on the development branch. The
sets overlap, so they are intentionally reported as separate bundles rather
than added into a misleading total.

- Generic exact-approval workflow and authenticated-claim routing: 33 tests and
  12 subtests passed.
- Focused runtime, project-update, and CLI bundle: 74 passed, 2 skipped, and 17
  subtests passed.
- Hard-exit recovery matrix: 1 test and 8 subtests passed in approximately 428
  seconds, with every boundary entering the public CLI recovery route and the
  checkpointed-preapproval boundary surviving a second interruption during
  recovery itself.
- Emergency feedback preservation lane: 1 test and 3 subtests passed.
- Bootstrap and installed-wheel hash checks: 5 focused tests passed.

These results prove the focused implementation paths only. They do not yet
authorize a release.

## Pending before any completion claim

1. Finish implementation review and public-safe release documentation.
2. Run the complete Ubuntu and Windows CI matrix, scale checks, resource
   synchronization, privacy, credential-shape, and absolute-path checks.
3. Build the final wheel from the exact reviewed commit and prove its clean pip
   installation retains the exact wheel SHA-256.
4. Merge the exact reviewed head, tag the merge commit, publish one release
   asset, download it anonymously, and repeat the hash and install checks.
5. Give the client the bounded recovery instructions. The client then performs
   resume and verifies an ordinary Zet draft from a fresh process.
6. Record the client result only after durable terminal evidence exists.

As of this checkpoint, full CI, pull-request merge, tag, public release, and
client-side recovery have not been completed.

## Files in the implementation scope

- `wom-kit/src/wom_kit/archive_cli.py`
- `wom-kit/src/wom_kit/archive_services.py`
- `wom-kit/src/wom_kit/exact_human_approval.py`
- `wom-kit/src/wom_kit/exact_human_approval_workflow.py`
- `wom-kit/src/wom_kit/project_runtime.py`
- `wom-kit/src/wom_kit/project_update_transaction.py`
- `wom-kit/tests/test_cli.py`
- `wom-kit/tests/test_exact_human_approval_workflow.py`
- `wom-kit/tests/test_project_runtime.py`
- `wom-kit/tests/test_project_update_transaction.py`
- `wom-kit/tests/test_wheel_install.py`
- `wom-kit/tools/check_wheel_install.py`
- `meeting-minutes/2026-08-30-v0415-interrupted-project-update-recovery.md`
- `archive-infra-decision-log-2026-08-30-v0415-authenticated-update-resume.md`

## Freeze hardening: supplied approval id cannot bypass discovery

A late review found one remaining diagnostic-only escape hatch. When
`project-version-update --resume` received `--approval-id`, the CLI routed that
identifier directly to the single-claim resume core instead of first scanning
the complete bounded claim store. A caller who already knew one valid id could
therefore avoid the zero/one/multiple candidate decision that ordinary resume
enforces.

The public CLI now always enters authenticated automatic discovery. An optional
supplied approval id is carried into that workflow only as an assertion. WOM
first authenticates and checkpoint-checks the full bounded candidate set,
requires exactly one candidate, and only then compares the supplied value with
the discovered id. A mismatch fails before the writer; a supplied id cannot
choose one candidate from an ambiguous set. Successful diagnostic resume still
reports that operator identifiers were supplied without echoing the id.

Focused verification on Python 3.12 confirmed:

- the four new workflow/CLI regression cases passed;
- the complete exact-human-approval workflow file passed with 24 tests and 4
  subtests; and
- the v0.4.15 release-document/parser checks plus the public CLI routing case
  passed with 9 tests and 25 subtests.

These focused results overlap and do not replace the required full CI matrix.

## Release-freeze review and race corrections

An independent release review found that the first implementation still had
five gaps. No public branch, pull request, tag, wheel, release, or client-side
write had occurred, so the candidate remained frozen while they were handled.

1. Automatic claim discovery released the archive authentication-key lock and
   reacquired it for resume. A second matching claim could theoretically appear
   in that interval. Discovery, the zero/one/multiple decision, optional legacy
   assertion, selected-claim rehydration, checkpoint guard, writer, and
   finalizer now stay inside one key-provider consumer.
2. Zero-claim cancellation and fresh claim publication could select competing
   branches. Both now reuse the transaction's existing `append.guard` with the
   fixed lock order `credential registry lock -> append.guard`. The publication
   guard ends before the domain writer so transaction appends cannot deadlock.
3. A supplied legacy approval identifier could be ignored on an early
   preapproval branch, and the public audit flag did not consistently include
   all supplied assertions. A supplied identifier must now match an actual
   unique candidate before any cancellation effect, and the flag is the OR of
   target, transaction, reviewer, and approval assertions on every branch.
4. Later verified cancellation tails were accepted by inspection but routed
   back through the first cancellation checkpoint. Verified tails now resume
   monotonically from `preapproval_cancel_requested` through `completed`, while
   torn or unexpected tails remain fail closed.
5. A durable-state reopen failure could leave a partially acquired directory
   handle set alive. Ownership is now explicit and every pre-transfer failure
   closes all held Windows handles or POSIX descriptors.

The exact transaction tests cover claim publication versus cancellation,
missing-store creation races, tampered and ambiguous claims, lockless-locator
races, cancellation tails, directory-guard partial acquisition, and preservation
of the client archive tree.

## Terminal cleanup scope boundary

The review also identified a larger, separate terminal-evidence feature. After
the transaction reaches `completed`, automatic cleanup renames the original
transaction directory to a cleanup tombstone and eventually leaves a compact
proof. That proof does not independently authenticate whether the earlier
terminal branch was success or preapproval cancellation. Treating its embedded
digest as new public authority would be circular.

This is not the blocked-draft defect: cleanup starts only after the domain is at
the exact postimage or exact preimage, the update lock is durably absent, and
ordinary project writers are no longer blocked. The v0.4.15 contract is
therefore deliberately limited to a live update lock and the exact lockless
unlock tail while the original transaction directory still exists.

If only terminal cleanup evidence remains, v0.4.15 performs a bounded,
streaming, read-only observation and returns the nonzero status
`terminal_cleanup_outcome_unknown`. It does not read that evidence as authority,
does not infer success, failure, or cancellation, does not reopen a writer or
native approval window, and does not delete or repair the evidence. A future
v0.4.16 acceptance item is a fixed terminal handoff published before unlock,
bound to checkpoints and independently reauthorized by the succeeded claim or
deterministic cancellation evidence.

## Preapproval-cancellation result truth correction

A freeze review found two misleading public fields even though the underlying
cancellation was safe. The top-level `files_written: []` named no
project-domain files, but it could be misread as proof that recovery persisted
no transaction control evidence. The result also hard-coded
`exact_live_lock_verified: true`, including retries that entered after the lock
had already been exactly released.

The result now declares `files_written_scope: project_domain_only` and includes
a content-free effect summary. It reports no path or identifier, but separately
states that project-domain writes were absent and that durable control evidence,
cancellation checkpoints or reservation-abort evidence, candidate cleanup or
verified absence, and lock release were written or reverified. Lock truth is
split into a live lock verified by this invocation, an exact prior lock binding,
a binding completed during recovery for the sealed-but-not-backlinked edge, and
verified lock absence after recovery. Empty reservation recovery and all six
durable cancellation tails have focused regression coverage; 4 focused tests
and 6 subtests passed after this correction.

## Package-resource synchronization correction

The official resource synchronizer hit a reproducible Windows `Errno 22` while
truncating the tracked manifest after the release documentation changed. The
writer now creates a same-directory temporary file, writes exact ASCII JSON
bytes with LF and a final newline, flushes and fsyncs it, preserves deterministic
POSIX mode `0644`, and performs a bounded Windows sharing-error replace. Failure
keeps the old manifest and removes the temporary file; a pre-adoption `fdopen`
failure also closes the raw descriptor.

Focused tests prove exact bytes, success cleanup, one transient replace retry,
retry exhaustion with original-byte preservation, descriptor cleanup, and the
167-file v0.4.15 resource synchronization. POSIX parent-directory fsync is not
claimed by this developer synchronization tool.

## Verification status after the corrections

Confirmed focused evidence now includes:

- exact approval workflow: 31 tests and 6 subtests passed;
- project-update transaction module: 56 tests and 13 subtests passed before the
  terminal-cleanup unknown observer was added;
- combined workflow, transaction, release-document, and package-resource bundle:
  98 tests passed at the preceding integration checkpoint;
- current release-document checks: 12 tests passed;
- capability-document checks: 152 tests passed;
- package-resource checks: 11 tests passed and 167 resources synchronized; and
- focused CLI routing, publication-boundary, hidden-assertion, and emergency
  feedback cases passed.

One first hard-exit rerun correctly exposed an obsolete test expectation: a
synthetic exception after durable cancellation selection is now sanitized as an
unknown workflow state instead of leaking the raw exception. The test was
updated to require that privacy-safe nonzero result and a successful second
resume. The complete hard-exit matrix must be rerun after the final
terminal-cleanup observer settles.

These are still development-branch results. Full CI, merge, exact tag, public
wheel, anonymous download/hash/install verification, and client-run recovery
remain pending.

## Final public-output and archive-boundary corrections

The final combined review found that an authenticated automatic resume could
return internal approval and transaction locators in several nested result
objects. Removing only the top-level approval fields was insufficient because
the domain writer also returned a nested operation approval and transaction
summary. Automatic resume now applies one recursive content-free projection at
the discovery boundary. It removes approval objects, approval ids, transaction
references, logical transaction references, and strings or paths containing
those locators while retaining safe state, evidence digests, and the ordinary
domain result. The result explicitly reports that approval and transaction
identifiers were not exposed. Ordinary native approval and explicit legacy
resume APIs keep their existing contracts; this projection is limited to
automatic discovery.

Another final review corrected the cleanup-unknown archive-access claim. The
CLI now performs the bounded project-update cleanup observation before output
path preparation and before opening `archive.yml` or the approval archive
boundary. The ordinary cleanup-unknown result therefore reads no archive
identity metadata, archive domain content, key, claim store, or cleanup
artifact content. If cleanup residue appears only after that preflight, the
inner race guard reports truthfully that archive identity metadata was already
read while separately stating that archive domain content was not read. A
supplied approval id still fails closed instead of selecting this claimless
result.

The progress reporter now emits `starting` before the cleanup preflight, so a
bounded but slow metadata scan cannot violate the first-status contract. The
normal tracked path does not duplicate that operator-visible start signal.

## Final frozen-source verification

After the production implementation and its review corrections stabilized, the
official package-resource synchronizer confirmed 167 v0.4.15 resources. That
production source then passed the real-process eight-boundary update recovery
matrix in 603.626 seconds. The boundaries cover lock acquisition, candidate
seal, preapproval checkpoint, approval binding, component intent, domain
commit, succeeded claim, and exact lock unlink. Every case resumed through the
same public identifier-free command and completed without a second native
approval prompt.

A later broad affected-test run found no new product failure, but exposed four
legacy CLI test doubles that did not yet accept the new
`claim_publication_boundary` keyword. Those test-only doubles now forward the
same publication boundary to the shared approval helper, or explicitly accept
it in the pre-claim attack simulation where it is intentionally unused. The
production modules and the hard-exit matrix scenario were not changed by this
compatibility correction. The identical broad affected-test selection was
rerun before the local gate was called complete. That final rerun passed 46
tests and 71 subtests with zero failures in 839.81 seconds, including every
previously incompatible test-double branch and all later affected cases.

Independent public/security review found no new client-specific identifier,
private project path, Windows user path, credential, token, or private URL in
the public diff or these release records. Focused final evidence also includes
33 exact-approval workflow tests, 69 project-update transaction tests with 27
subtests, the cleanup/archive-boundary and progress regressions, synchronized
release resources, and passing release-document and package-resource checks.

These results complete the local release-candidate gate. Pull-request CI,
merge, exact merge-SHA tag, public wheel publication, anonymous download and
hash/install verification, and client-run recovery remain required before the
defect is reported as resolved.
