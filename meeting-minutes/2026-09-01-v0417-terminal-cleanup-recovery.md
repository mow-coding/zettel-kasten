# v0.4.17 Terminal Cleanup Recovery Work Record

Date: 2026-09-01

Status: implementation candidate; merge, tag, public release, and client-run
validation must be recorded separately before this work is called released or
resolved.

## Context and user intent

The user supplied a private, read-only pending-approval feedback snapshot from
a tester after the v0.4.16 bootstrap had installed correctly. The report showed
that the project itself had not advanced because the official updater recovery
path remained trapped. A fresh dry-run appeared ready, but the matching
approval stopped immediately at a terminal-cleanup gate and returned only a
generic command failure.

The user was frustrated because several recent releases had invested heavily in
safe interruption recovery, yet the supported client workflow still could not
finish a normal update. The correction was explicit: do not add another
inspection command that leaves the person to interpret private artifacts. Make
the existing workflow recover the exact state it can prove, keep ambiguous
state safe, and give the person a short actionable result.

The development boundary remained strict. The private report was read only.
No client archive, project source, runtime, version pin, credential, provider,
remote service, lock, transaction artifact, or feedback record was modified.
Public code, tests, and records use only synthetic project state and do not copy
private paths, identifiers, digests, or report contents.

## Root cause

v0.4.15 intentionally retained durable evidence when a project update was
cancelled before intent seal. That evidence proves that no project-domain
writer ran and supports later audit.

v0.4.16 added authenticated terminal result delivery and exact cleanup recovery
for a completed approved transaction. It also accepted canonical proof-only
history as inert. However, its fresh-update namespace classifier rejected every
ordinary retained transaction directory except the newly created reservation
for the current approval. Therefore a fully valid preapproval-abort history
created by WOM itself was treated as unresolved residue.

The dry-run did not call that same classifier. It could report
`ready_for_approval`, while approval called the classifier and failed before
native approval. The CLI then reduced the known fixed cleanup gate to a generic
privacy-safe failure sentence. The combined behavior created three problems:

1. dry-run and approval disagreed about the same unchanged project state;
2. an ordinary cancellation could block every later update indefinitely; and
3. the operator received no supported next action despite WOM already having
   enough exact evidence to distinguish safe terminal history from unknown
   residue.

This was a systemic contract defect, not a special property of one client
archive.

## Agreed correction

The top-level command inventory remains unchanged. `project-version-update`
owns preview, approval, and identifier-free recovery.

Fresh dry-run and approval now share one bounded, read-only cleanup namespace
classification before native approval or project-domain writer entry. The
classification recognizes only:

- ordinary namespace absence;
- canonical proof-only inert history;
- one exact authenticated terminal transaction selected by the existing
  recovery locator;
- exact preapproval-abort history produced by WOM; and
- the already supported exact cleanup tombstone states.

Unknown names, extra members, unsafe types, links, changed bytes or identities,
multiple incompatible active candidates, active-lock contradictions, scan
races, and incomplete cleanup continue to fail closed.

Fresh work with exact terminal control history returns a normal structured
blocked result with
`project_version_update_terminal_cleanup_required`. The result tells the
operator to pause other writers for that project and run identifier-free
`project-version-update --resume`. It does not request a transaction ref,
approval id, target, reviewer, filename, count, or digest. Approval reaches the
same result before opening native approval.

Unknown residue returns
`project_version_update_terminal_cleanup_outcome_unknown` and tells the
operator to preserve evidence and stop. It does not authorize repeated resume,
manual lock or pin editing, transaction deletion, cleanup guessing, or a fresh
approval.

## Exact abort-history compaction

An exact completed preapproval abort is terminal private control history, not a
project-domain operation. The v0.4.17 candidate adds an identity-bound cleanup
plan for that narrow state. The plan binds:

- the exact transaction and logical identities;
- the fixed expected file set and the absence of unexpected directories;
- every file's byte length, digest, and filesystem identity;
- reservation and abort-receipt evidence;
- the transaction-root identity;
- archive identity; and
- a dedicated cleanup authority.

Cleanup writes the plan durably, rebuilds the same plan from the still-current
tree, moves the exact directory to a no-replace tombstone, removes only the
plan-bound members, and retains one canonical proof. Recovery handles the
supported original, planned-original, tombstone, proof-link, and final-proof
boundaries idempotently. Every boundary revalidates the lock absence, directory
generation, file identities, links, and bytes.

This operation does not run the project-domain writer, update source, install a
runtime, change the version pin, write archive content, attribute a past update
success, or create fresh approval authority. Proof-only history remains inert
and a new update still requires a new preview and one new exact approval.

An existing authenticated approved transaction continues through the v0.4.16
terminal-handoff contract. Resume reuses its existing claim, postimage, and
cleanup authority, opens no second native decision, and does not replay an
already completed domain writer.

## CLI error truth

Known terminal-cleanup gates cross the CLI exception boundary only through a
small exact allowlist. A recognized fixed internal code becomes a structured
v0.4.17 failure result with the same public reason code, no project-domain
effects, and actionable `next_safe_actions`.

The allowlist does not treat arbitrary code-shaped messages as safe. Other
`ArchiveServiceError` messages and all unrelated exceptions retain the generic
redacted failure artifact. Public results do not reflect raw exception text,
private paths, hashes, transaction or approval identifiers, or private values.

## Independent security feedback and correction

An independent review reproduced two release-blocking authority gaps after the
first recovery implementation. The unbound terminal reader accepted a
canonical-looking active document even when the file had another hard link or
a Windows alternate data stream. Separately, the resume service treated the
presence of an active transaction as enough to continue even when a malformed
cleanup-shaped sibling made the complete namespace unresolved.

Both findings changed the implementation before release. Terminal documents
are now read through a retained parent chain and exact file handle with stable
identity, one-link, private metadata, bounded canonical-byte, and Windows
default-stream checks. Active preapproval states are explicitly classified;
an active transaction plus any unknown, malformed, linked, raced, or unsafe
sibling returns the same privacy-safe unknown result and never reaches
recovery, native approval, or a project-domain writer.

The review also found that a Windows alternate stream attached to an interrupted
abort cleanup plan could otherwise survive the no-replace move into a canonical
proof. Cleanup plan and proof reads now require the default stream only. Tests
create real alternate streams, prove that discovery and cleanup refuse them,
and prove that the original bytes and stream remain untouched for forensic
review.

A later re-review found one remaining reader mismatch in canonical proof-only
classification: that path still used a generic regular-file reader, so a proof
with a Windows alternate stream could be accepted as inert history and let a
fresh approval continue. It now uses the same held, single-link,
default-stream-only cleanup reader as cleanup execution. Dedicated NTFS tests
cover both alternate streams and external hard links on planned cleanup records
and proof-only history. Every case preserves the original and alias data and
stops before preview authority, native approval, recovery, or a domain writer.

The same re-review found a presentation-boundary regression. The hardened
terminal reader correctly rejected an unsafe active document, but that one
fixed error escaped the cleanup gate and became the generic redacted command
failure again. The gate now converts only
`project_version_update_terminal_handoff_invalid` into the structured
cleanup-outcome-unknown result. Every other internal service exception remains
private and is re-raised. Reader-specific parent, reparse, hard-link, alternate-
stream, and exact-allowlist tests keep replay, delivery, approval, recovery, and
domain writers closed.

A result-truth correction was also required. If one exact abort history is
compacted before a later history refuses cleanup, or if compaction accompanies
another authenticated resume, the final result must retain the verified private
control-effect count and mark partial completion where applicable. An empty
project-domain file list is labeled as project-domain scope; it is not a claim
that no private control record changed.

The review identified one bounded-lifetime debt: canonical proof history counts
toward the fixed transaction namespace scan cap. v0.4.17 deliberately does not
delete or rotate evidence without a separate retention authority. A future
decision must introduce an identity-bound proof ledger or rotation contract;
cap exhaustion remains a fail-closed availability stop until then.

## Final concurrency and restart correction

The implementation was paused and resumed across computer shutdowns. Each
resume began by confirming that the development worktree, branch, diff, and
Python sources were intact. The private client project remained read-only and
no installation, recovery, provider call, or data write was performed there.

The final race review found that two individually strict observations were not
enough if another same-project process could change the terminal handoff after
the observation but before a claim checkpoint, domain write, result
publication, or replay cleanup. Fresh approval and mutation-bearing resume now
take one project terminal guard, revalidate the exact observation under that
guard, and retain the guard for the complete authority-bearing interval. A
separate state-and-transaction owner token prevents another in-process state
from borrowing the lease. Nested terminal reads and publications reuse the
already bound parent chain and guard rather than deadlocking on a second lock.

Terminal-ready replay uses the same held boundary for ready-document
revalidation, result reauthentication, delivery capability derivation, and
exact cleanup. The recovery gate correlates a pre-unlock handoff with either
its exact active transaction or the exact same transaction's complete cleanup
tombstone. The latter is the valid process-loss state after a no-replace cleanup
move; an unrelated tombstone is mixed unknown state and remains untouched.

The CLI had a separate discovery seam: it could inspect operation-control
delivery state before the service's strict terminal reader supplied the public
cleanup-unknown result. CLI discovery now takes strict active-handoff snapshots
on both sides and compares state, raw digest, pending-record digest, transaction
correlation, and candidate handoff digest. Exact terminal-document invalidity
and observation drift become the content-free structured unknown result. An
unrelated operation-control exception is not relabelled, while exact consumed
and display-pending delivery remains resumable.

If the terminal boundary changes before a fresh native decision, WOM exactly
cancels its own current reservation where that can still be proven and reports
the private-control effect separately from project-domain effects. If exact
cancellation cannot be proved, the result says the private cleanup may be
incomplete and preserves the evidence instead of claiming zero effect.

Release-surface validation also found stale current-version expectations in
historical tests, one Korean checkpoint, and versioned bootstrap/tool paths.
Those current-facing expectations were moved to v0.4.17 while the historical
v0.4.16 release note and supply-lock bytes remained unchanged. The runtime skill
was kept below its established size budget, packaged resources remained exactly
169 files, and the privacy predecessor gate was preserved without adding a new
literal private-client marker to a test file.

## Human boundary

The person has two meaningful decisions:

1. whether other editors, sync tools, Git writers, and WOM sessions using the
   same project are paused for the complete transaction; and
2. after recovery and a fresh preview, whether to update that project now.

WOM owns artifact classification, exact-set accounting, hashes, identities,
drift checks, cleanup selection, checkpoint resume, proof retention, and
post-update verification. Asking the person to reproduce those facts would
move a machine-verification responsibility back onto the operator and would
not be accepted as a fix.

## Verification plan and feedback loop

The candidate must be verified with synthetic state that combines canonical
proof history, multiple exact preapproval-abort histories, and one supported
authenticated terminal transaction. No client artifact bytes or identifiers
are test fixtures.

Required regression evidence includes:

- dry-run and approval returning the same cleanup blocker for unchanged exact
  history, with no native approval or domain-writer entry;
- exact abort-history classification and rejection of every near-miss shape;
- cleanup plan identity and byte binding;
- interruption and resume at each cleanup boundary;
- idempotent final proof-only convergence;
- preservation of existing proof bytes;
- zero project-domain file changes during abort-history compaction;
- existing authenticated transaction resume without writer replay or a second
  approval;
- fixed privacy-safe CLI reason projection and generic redaction for arbitrary
  errors;
- Windows and POSIX boundary tests, with mutation-bearing execution remaining
  Windows-only; and
- public privacy, packaged resource, wheel, and full cross-platform CI gates.

If any test shows that cleanup can select an unexpected artifact, race an
external writer, misattribute success, or expose a private value, the release
stops and the evidence is preserved. If implementation changes the public
contract, this record, the decision log, operator guidance, release note, and
regression assertions must be updated together before review.

## Release and client boundary

The candidate is not a client fix merely because source code exists. Completion
requires focused tests, full required CI, privacy and resource gates, exact PR
merge, an annotated tag at the merge commit, a public release with a verified
wheel, and an anonymous fresh-install check.

Publishing or installing the wheel changes no client archive or project. A
tester must separately choose the supported recovery, run a new preview, make
one normal update decision, verify the project launcher in a new process, and
then exercise the original ordinary workflow. Until that client-side execution
and its durable evidence succeed, the feedback is release-addressed but not
client-validated or resolved.

## Frozen candidate verification

After the concurrency corrections, the terminal-create and project-update
transaction suites passed 182 tests with 60 subtests; three tests were skipped
only by their declared operating-system boundary. The frozen matrix includes
fresh approval, mutation-bearing resume, terminal-ready replay, exact
state-owned lease checks, competing-guard refusal, same-transaction cleanup
tombstone recovery, foreign-tombstone refusal, partial-effect truth, and every
interruption checkpoint in the exact abort-history cleanup.

The v0.4.17 release-document suite passed together with all historical release
document tests: 120 tests and 1,693 subtests. The separately changed capability,
privacy-boundary, runtime, predecessor-surface, root-shim, metadata-index, and
wheel-install modules passed 270 tests, with four declared platform skips. The
complete CLI module and remote cross-platform CI remain separate release gates;
targeted CLI continuity and privacy tests passed before the full run began.

The public privacy checker reported zero findings. Release readiness passed all
four link, Korean-language, privacy, and runtime-skill gates. Package resources
were synchronized at 169 files, and the runtime skill remained within its
budget at 191 lines and 1,367 words with six references and no reported
problem.

An external candidate-wheel check built and installed v0.4.17 in a new temporary
environment. It verified 169 manifested resources, 252 wheel members, all four
CLI and MCP entry points, the installed smoke workflows, and zero Windows user-
path or secret-pattern matches across 15,049,511 scanned text-like bytes. The
candidate wheel SHA-256 is
`cfc43684bf59ce132270dcb77e8c281658fb51c69f929bbae49796001ca2a382`.
This is candidate evidence only; the release wheel must be rebuilt or
byte-verified from the exact merge commit.

## First remote CI feedback correction

The first public PR run exposed a platform-contract error before merge. The
exact reservation-abort cleanup uses the existing compare-and-delete primitive,
which is deliberately Windows-only. On POSIX, the first candidate could write
a cleanup plan and move the transaction directory before the unsupported exact
delete refused. That behavior was fail-closed with respect to archive data but
was not read-only with respect to private control state.

The production cleanup entrypoints now refuse POSIX before writing a cleanup
plan or moving any namespace entry. A POSIX regression test freezes the complete
project tree before the call, verifies byte-for-byte unchanged state afterward,
and confirms that read-only discovery still reports the original exact terminal
history. Success-path cleanup and mutation-lease tests are explicitly marked as
Windows-only; Ubuntu continues to test discovery, classification, and the new
zero-mutation refusal.

The same CI run found test-only contract drift: one test referred to a helper
local to another test, and three no-handoff mocks returned `None` without
populating the strict observation output. One shared test helper now models an
absent handoff while honoring that output contract. The corrected seven focused
CLI tests passed, and the full project-update transaction module passed 154
tests on supported Windows, with one POSIX-only assertion skipped there.

An unchanged Notion interprocess pacing test also crossed its old 15-second
spawn-readiness timeout on a busy Windows runner. The pacing assertion itself
did not fail. Its process-readiness, result, and join budgets are now 60 seconds,
and `finally` cleanup terminates and joins any surviving child before closing
the queues. Three cold-process repetitions passed locally. This changes only
test reliability and does not relax the archive-wide rate interval.

## Second remote CI feedback: terminal delivery and candidate settling

The corrected public run removed the earlier Ubuntu errors but exposed five
Windows failures in two independent areas. Four belonged to terminal replay.
A valid `active.json` can exist before any complete operation-bound output:
process loss may occur before cleanup, and a cleanup-incomplete result
intentionally carries no delivery proof. CLI discovery incorrectly treated the
stable active handoff plus no delivery candidate as unknown residue, so the
authenticated service replay never ran. The same error blocked the
`lock_unlinked` and `ready_handoff_before_cleanup` hard-exit boundaries.

The CLI now distinguishes that exact normal state from drift. It still compares
the handoff state, raw digest, pending digest, and transaction correlation on
both sides of operation discovery. If the stable active handoff has no bound
delivery candidate, the held service boundary reauthenticates the exact claim,
postimage, and transaction before cleanup. Any discovery error, observation
change, malformed document, or candidate mismatch remains fail-closed.

Review then found a second-order concurrency gap. If two processes both reached
stable active state before either published an output, each could create a
different valid journal for the same handoff. The existing ambiguity check
would preserve data but could permanently block result delivery. Every write
invocation that may create a new updater output now acquires the project
terminal boundary before capture creation, rechecks the exact preflight state
under that boundary, and holds it through service execution, immutable output,
journal completion, and `active` to `display-pending` acknowledgement. A losing
process stops before output, approval, cleanup, or domain writing. The boundary
is released before pending-delivery discovery and final display consumption;
the acknowledgement path reuses an already held lease without self-deadlock.
Boundary-close failure is content-free, preserves the capsule, and leaves
delivery pending instead of reflecting a private error.

The fifth Windows failure was a separate preapproval runtime-candidate race.
Immediately after owned venv, pip, and script mutations, the first strict
bytecode scan observed one directory generation change and converted the new
candidate into manual-review partial state. The scan remains strict. Only the
exact one-argument `project_runtime_tree_changed` result from this first owned
read is retried, at most three times with 0.025- and 0.05-second backoff, and
every attempt requires identical whole-tree shape before and after hashing.
Unsafe, unreadable, colliding, reparse, oversized, or nonexact failures are
never retried. No deletion begins until one complete stable inventory exists;
all later wheel, payload, receipt, seal, and hard-link verification remains.

Deterministic regressions now cover stable pre-unlock and terminal-ready
handoffs without a delivery journal, strict drift rejection, boundary ordering
around output and journal publication, a competing updater losing before
output, nested acknowledgement without self-deadlock, privacy-safe close
failure, one transient tree change, exhausted changes with zero deletion, and
immediate refusal of every nonexact tree error. The previously failing runtime
candidate integration passed in 229.800 seconds. The repaired-runtime and two
hard-exit recovery cases passed together on the final current code in 189.343
seconds.

The complete project-update transaction module then passed 155 tests in
183.351 seconds; its one skip was the declared POSIX-only refusal assertion on
this Windows run. The complete runtime-candidate module passed all 10 tests in
500.826 seconds, including the real venv creation, same-version corrupt and
empty-runtime repair, exact rollback, and transient-tree settling paths. These
are local candidate results; the fresh public PR head must still pass every
required Ubuntu and Windows CI shard before merge.

## Independent final audit correction: stale delivery after guard wait

The second independent final audit found a release-blocking interleaving that
the first layer tests had not covered. Two fresh commands could both initially
observe no active handoff. Invocation A could then complete, acknowledge its
result by moving `active` to `display-pending`, and release the outer guard
before stdout finalization. A delayed invocation B could acquire that guard and
still see `active` absent, which looked identical to its stale first snapshot.
The held fresh-update preflight did not inspect `display-pending`, so B could
reach a new output and writer while A's result still awaited display. A similar
gap existed if A published a complete output and journal but acknowledgement
failed while the same active capsule remained.

The race was reproduced with the real terminal fixture and real
acknowledgement path before correction: `active` was absent,
`display-pending` was present, and the stale unbound boundary incorrectly
opened. The command boundary now repeats the complete strict delivery discovery
while holding the guard and requires both the exact original active observation
and no delivery candidate. A newly appeared display-pending candidate, a newly
complete journal for the same active capsule, observation drift, malformed
state, or discovery error maps to the content-free cleanup-unknown result and
closes the guard before output capture.

Deterministic command-level coverage now proves that the stale invocation
creates no diagnostics output or operation journal, reads no archive identity,
enters no project writer, preserves the terminal bytes, and reflects no private
path or raw state. A second regression uses a valid real acknowledgement rather
than malformed synthetic bytes and proves the exact display-pending capsule is
preserved. The two original hard-exit boundaries passed again in 97.023
seconds, and the same-version repaired-runtime terminal replay passed again in
85.317 seconds on the corrected code.

The complete project-update transaction module then passed 156 tests in
169.937 seconds, with only its declared POSIX-only assertion skipped on
Windows. The newly reachable active-without-delivery-journal security path was
also frozen with one real `ready_handoff_before_cleanup` process-loss fixture.
Three adversarial subtests changed the pending attachment/hash binding, the
ready pending-record hash, and the transaction correlation independently. All
three public identifier-free resumes returned the same content-free unknown
result, entered neither a domain/component writer nor authenticated cleanup,
preserved the exact tampered active bytes for evidence, and reflected none of
the private project path, real or foreign transaction references, or injected
private marker. The focused test passed in 46.493 seconds.

The final independent re-audit found no remaining P0, P1, or P2 issue and
independently reran the real acknowledgement race, command-level stale-display
boundary, and all three no-journal tamper cases: three tests passed in 47.384
seconds. The first broad historical release-document command was launched
without the source package on `PYTHONPATH`, so ten modules failed at import and
no affected test body ran. This was a test-launch mistake, not a product
failure. The corrected command ran all 120 historical and current release-note
tests in 4.136 seconds with no failure. The package-resource, release-readiness,
public-privacy, and v0.4.17 document modules then passed 56 tests in 53.495
seconds, with one declared operating-system skip.

## First exact-head public CI correction: platform-specific boundary trace

The first public CI run for exact head `4d1aa8e8` correctly blocked release.
Ubuntu Python 3.10 and 3.12 shard 1 each completed 2,269 tests with the same two
subtest failures in
`test_project_version_update_terminal_output_precedes_journal_and_atomic_consumption`.
Both failures were in the test's event-list expectation: it required the
Windows-only terminal control boundary to emit `boundary-enter` and
`boundary-exit` on POSIX. The production command intentionally enters that
boundary only when `os.name == "nt"`; unsupported POSIX mutation must not
create the Windows private terminal namespace. The actual Ubuntu sequence
still proved that immutable output preceded operation-journal completion,
display preparation, and terminal display.

The regression now retains one exact event assertion on every platform while
making the platform contract explicit. Windows must include the outer boundary
around output, journal completion, and acknowledgement preparation. POSIX must
include neither boundary event and must retain the same output and display
ordering. This does not weaken the Windows race proof; the Windows CI shard
continues to require both boundary events, while Ubuntu now also proves that a
mocked service result cannot make the unsupported control boundary appear to
have executed. A fresh exact-head public CI run is required after this test
correction; the failed run cannot authorize merge or release.

## Pending release-record additions

Before release closure, append the exact public PR, merge commit, annotated tag,
CI result, release URL, wheel digest, anonymous-install verification, secret-
scan status, and task-owned branch/worktree cleanup evidence. Do not place any
private client identifiers in that appendix.
