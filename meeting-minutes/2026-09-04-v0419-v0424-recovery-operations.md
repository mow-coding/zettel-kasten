# v0.4.19-v0.4.24 Recovery And Operations Work Record

Date: 2026-09-04

Status: accepted execution plan; implementation begins with v0.4.19. A public
release does not by itself close any client report.

## Context and user intent

Repeated beta feedback showed a gap between a command appearing available and
the same command working in the client runtime. It also exposed long silent
diagnostics, unclear batch targets, mixed work from several AI applications,
credentials that could not be reused safely, incomplete Notion recovery,
incomplete object-storage proof, and cleanup workflows that could not finish.
The user asked that these problems be completed as operating workflows instead
of accumulating more diagnostic-only commands.

The user also corrected the human boundary. A person must not count archive
rows, copy identifiers, construct JSON, compare hashes, choose checkpoints, or
decide where a resume starts. WOM performs those mechanical checks. The person
decides only the meaningful action: beginning or handing off work, entering a
secret in a native secure form, approving a comprehensible batch, deciding a
relationship, or resolving genuinely ambiguous evidence.

## Release train decision

The work is split into six independently complete releases:

1. v0.4.19 makes project update, runtime inspection, capability reporting,
   Doctor output, and Windows child-process behavior tell the same truth.
2. v0.4.20 binds new writes to an opaque client-app, named-workstream, and
   work-session chain while retaining one archive-wide writer lock.
3. v0.4.21 provides local-only paged target previews and completes supported
   title and remint reconciliation.
4. v0.4.22 introduces the scoped Windows credential broker and completes the
   evidence-built Notion recovery workflow.
5. v0.4.23 proves complete R2 bytes, safely offloads eligible local objects,
   and automatically rehydrates them when requested.
6. v0.4.24 completes relation decisions, session-scoped artifact and Git
   handling, legacy responsibility assignment, and evidence-backed feedback
   closeout.

Each release is integrated and applied in order. Later domain code may be
prepared on isolated branches, but an incomplete external service cannot hold
back a completed earlier safety result.

## Safety and privacy boundary

- Development takes place only in dedicated worktrees rooted at the public
  development repository.
- The beta client's archive, runtime, credentials, providers, and feedback
  ledger remain read-only to the development team.
- Public fixtures are synthetic. Human-readable labels, target titles,
  filenames, provider identifiers, and absolute paths do not enter public
  manifests, logs, receipts, errors, or binding records.
- A release can be described as release-addressed only after its reviewed
  public wheel is published and independently installed. A client problem is
  resolved only after the client launcher executes it and returns a durable
  receipt plus independent verification.
- Repository closeout is part of every release: the feature and evidence PRs
  are merged, branches and task worktrees are removed, and the primary checkout
  is rechecked against the remote.

## v0.4.19 implementation split

Three bounded branches were created from the same clean `origin/main`:

- runtime observation and project-update revalidation truth;
- one capability-availability decision shared by user-facing surfaces; and
- noninteractive Windows child-process hiding plus Doctor scan/progress work.

The integration branch owns the release documentation, package metadata,
cross-domain verification, independent review, PR, tag, wheel, publication,
and cleanup. The canonical checkout remains clean during implementation.

## Verification loop

For every release the team records the current remote state, runs focused and
full tests, exercises interruption/resume/rollback and drift, runs public
privacy and package-resource gates, obtains an independent review, verifies
the exact merged commit and annotated tag, downloads the public wheel without
credentials, installs it in a new process, and finally removes task-owned
branches and worktrees. Counts or provider facts that drift are recomputed by
WOM and stop only the affected operation before human approval.

## v0.4.19 integration progress

The integration implementation now includes four-state source, Git, pin,
runtime, prepared-candidate, and lock observations; field-level approved
preparation revalidation; one parser-derived capability decision consumed by
help, capabilities, Doctor suggestions, dry-run interpretation, MCP inventory,
and actual dispatch; one explicit Windows child-process visibility policy; and
generation reuse in the operational Doctor boundary projection.

Independent review found and corrected several places where an unreadable
candidate, lock, source file, or Git query could otherwise have collapsed into
an observed mismatch or absence. Confirmed byte or identity drift remains
`failed`; inability to obtain trustworthy evidence remains `unavailable`; and
checks blocked by an earlier prerequisite remain `not_reached`. Runtime
candidate cleanup tests also preserve bound timestamp evidence instead of
weakening the product's exact preimage check.

The public release documents now distinguish the current v0.4.19 contract from
the retained v0.4.18 history. The package-resource set was regenerated at 169
files. The release-document group passed 99 tests, 2 skips, and 853 subtests;
the capability-matrix documentation passed 152 tests and 4,072 subtests. The
public link, Korean product-language, public privacy, and runtime-skill release
gates all passed. At this checkpoint the full cross-platform suite, wheel
installation proof, PR, tag, release, and post-release evidence PR are still
pending, so v0.4.19 is not yet released and no client result is claimed.

The development work never opened or changed a beta archive, project runtime,
credential, provider, or feedback ledger. The GitHub source baseline remained
the public v0.4.18 release with no open pull request; the prior synthetic
Google-key alert was verified resolved and no open secret-scanning alert was
present.

## v0.4.19 critical review loop

The first integrated candidate was deliberately held back after independent
review found cases where a completed invalid observation and a temporary
inability to observe were still collapsed into one scalar result. The affected
public source, Git, project-pin, runtime-integrity, update-preparation, lock,
runtime-candidate, and exact-component paths are being converted to explicit
`passed`, `failed`, `not_reached`, and `unavailable` observations. Confirmed
malformed bytes, duplicate or inconsistent Git output, policy overflow, and
identity drift are failures. Process launch, access, or stable-read failures
remain unavailable and do not become an observed absence.

Review also reproduced an exact-writer race: a target created by another
writer after the preimage check could be replaced by an unconditional atomic
write. This is a release blocker. The writer must use a no-loss conditional
publication protocol, preserve a concurrently replaced target, and prove the
expected live preimage at the publication boundary. A check immediately before
an unconditional replace is not sufficient because it leaves a check-to-use
race. The fault matrix includes concurrent create, replace, and in-place change
as well as interruption at every durable publication checkpoint.

A real v0.4.15 producer fixture exposed a second compatibility boundary. A
transaction interrupted after `approval_bound` but before its first component
cannot safely reuse the old approval, and the old cleanup authority cannot be
silently replaced by a new claim. The implementation therefore remains blocked
until one of two complete outcomes exists: a versioned, append-only authority
transition with full cleanup semantics, or a separately approved durable
prewrite-abandonment protocol that keeps the old transaction and claim
immutable, proves zero domain mutation, safely transfers the active recovery
locator, and starts a fresh current transaction. Merely failing closed is a
useful regression test but does not satisfy the interrupted-update recovery
goal.

## v0.4.19 Doctor full-scale evidence

The first exact Letter 148 scale run stayed responsive and private but missed
the time limit: operational Doctor took 230.302473 seconds and default deep
Doctor took 225.051172 seconds. Both printed their first status immediately,
kept their maximum heartbeat gap to 5.1 seconds, parsed and staged the object
manifest once, and emitted none of the private sentinels. The dominant stages
were zettel validation, object-manifest validation, mint and retired-draft
receipts, and the archive boundary inventory.

The first performance correction reused pure lexical projections and exact
stage observations, prefetched independent stable generations with bounded
workers, and parallelized final identity revalidation without removing
descriptor-bound reads, object hashing, stage revalidation, archive-root
checks, or completion revalidation. A fresh full-scale candidate passed, but a
second independent review found two release-blocking races: a dequeued task
could start after cancellation, and a new file created in a previously empty
inventoried directory could be missed while the cache was still reported as
current. The final implementation linearizes worker start against shutdown and
stores a content-free child name, type, and identity projection for every
inventoried directory. It revalidates the complete directory projection twice
after the last archive read.

After those corrections, a newly generated 22,441-Objet, 8,612-Zet fixture
passed again: operational Doctor took 126.359814 seconds and deep Doctor took
144.622635 seconds. Both emitted their first state at 0.0 seconds, kept the
maximum heartbeat gap at 5.0 seconds, and emitted no private sentinel. Deep
Doctor hashed all 22,441 unique object paths exactly once and reported current
completion revalidation. The focused Doctor suite passed 65 tests, including
real Windows directory-handle, junction, 8.3 alias, late-mutation,
bounded-queue, and blocked-worker process-exit cases. The benchmark used only
its temporary synthetic archive, called no provider, and did not persist an
archive mutation.

These results are candidate evidence only. Full supported-platform CI, wheel
installation, merge, tag, public release, and the release-evidence closeout are
still pending, so v0.4.19 and every client outcome remain unresolved.

## v0.4.19 second independent truth and writer review

A separate reviewer reproduced five additional four-state consistency defects.
A current nine-field approval could be weakened merely because the runtime
candidate used an older shape; a known runtime binding mismatch could be hidden
by an unrelated unavailable observation; deterministic executable, module,
prefix, and core-module mismatches could likewise be hidden; and one copied
post-bundle helper still collapsed `not_reached` into `unavailable`. The
comparison now selects predecessor compatibility only from the exact approved
policy shape and applies the common precedence `failed`, `unavailable`,
`not_reached`, then `passed` at every reviewed boundary. A clean installation
whose target runtime does not yet exist is no longer treated as a broken
installation plan; actual plan blockers, drift, and unavailable evidence remain
distinct.

The Windows exact publisher was also exercised before rename, after rename,
after delete-on-close cancellation, across a directory durability failure, and
against a concurrent name replacement. It retains the exact temporary handle,
uses no-replace publication, performs no path-based temporary cleanup, and
returns only fixed path-free service errors. The final focused review passed
110 tests, 2 skips, and 202 subtests; the dedicated writer regression passed 15
tests and 11 subtests. Full repository CI is still pending.

## v0.4.15 interrupted-update compatibility work

The real v0.4.15 producer fixture now reaches one successful current v0.4.19
domain update through one fresh native approval. The predecessor claim remains
started and byte-identical, the predecessor transaction is staged rather than
silently rewritten, and only the fresh transaction performs domain component
writes. This is a milestone, not completion evidence.

Independent review found that the first control-plane candidate still lacked
active-locator resume routing, authenticated terminal closeout, complete deny
restoration, and crash-safe primitive behavior at several namespace boundaries.
It also found that a directly appended JSONL recovery journal could be left
with a partial final line. The work is therefore still blocked from release
while the control records are converted to immutable create-only checkpoints,
directory and deletion operations are bound to retained Windows handles, the
active locator is connected to resume discovery, and deny, success, and every
power-cut boundary are tested end to end. No client archive, runtime,
credential, provider, or feedback ledger has been touched.

## v0.4.19 deterministic reservation recovery review

The legacy compatibility review found that allocating an exact fresh
transaction reference was not sufficient on its own. A process could stop
after creating the transaction directory, its marker, or its append guard, and
the predecessor `reserve` implementation would reject the durable prefix as an
unrelated existing transaction. The replacement protocol now prepares the
complete immutable reservation document before any filesystem write and offers
an exact `reserve_or_resume_exact` path. Only the empty directory, exact marker,
and exact marker-plus-guard prefixes may advance; every other byte, entry,
hardlink, reparse point, alternate data stream, or cleanup residue is preserved
and blocked with a fixed content-free error.

The implementation binds POSIX operations to retained directory descriptors
and binds Windows operations to no-delete directory handles plus an
inode-derived, bounded-wait mutex. It rechecks cleanup residue inside the same
guard and returns the already verified reservation rather than closing the
directory generation and reopening it by path. Focused Windows tests passed the
three real hard-exit boundaries, actual overlapping two-process convergence,
foreign-prefix preservation, retained-root replacement blocking, ADS rejection,
and create-only predecessor compatibility. An independent reviewer found no
remaining primitive-level P0 or P1 issue. The full transaction suite and the
service integration remain pending, so this is not release evidence yet.

This primitive depends on two explicit higher-level authorities: all WOM
publishers must obey the archive-wide quiescence and terminal-recovery locking
contract, and the recovery service must durably authenticate the exact prepared
reservation fields and SHA before materialization. The second binding, the
six-state service router, cancellation evidence, terminal result delivery, and
the real v0.4.15 producer replay are still release blockers.

## v0.4.19 authenticated terminal recovery resolver

The follow-up terminal resolver now reconstructs an interrupted legacy update
only from an authenticated, immutable evidence chain. It verifies the private
recovery seed, intent, predecessor transaction stage, pre-update snapshot,
allocation, prepared reservation, exact reservation, prepared inventory,
post-update snapshot, prospective current plan, cancellation result, cleanup
and restoration evidence, receipt, terminal locator, and the authenticated
preterminal locator-history record. Every record is bound to the same recovery
reference, intent, journal head, and required cross-digests before the caller
may expose a stored terminal result or materialize a missing exact reservation.

Independent review found and closed three important cross-boundary gaps during
this work. The terminal locator must name the exact HMAC-authenticated
preterminal history record, predecessor stage evidence must match the exact
staged or already-staged semantic proof for the immutable predecessor
transaction, and the `locator-history` directory itself must remain a retained
real directory rather than a symlink or junction. Adversarial tests now reject
wrong keys, cross-reference substitution, missing or extra fields, digest
tampering, success-result substitution, active/terminal collisions, unsafe
intermediate paths, and unsupported key creation without disclosing private
reviewer material or filesystem paths in the public result.

The frozen resolver passed 35 focused tests, Python compilation, and diff
validation both in the implementation pass and in independent re-execution.
The independent reviewer reported no remaining P0 or P1 defect in this
primitive. Commit `74ba695c` records the authenticated terminal resolver and
its regression matrix. This is still implementation evidence rather than
release or client-resolution evidence: the production six-state caller must
obey the terminal-control and recovery serialization order, its cancellation
delivery path remains under review, and full repository CI, wheel validation,
merge, tag, public release, and client-run verification are pending.

## v0.4.19 per-call Windows child-process enforcement

The Windows no-console policy is now checked at every process-creation call
site rather than by counting helper names in source text. The AST regression
requires each noninteractive `subprocess` call to use the exact common hidden
child helper, permits only the explicitly interactive KeePass window, and
binds each `multiprocessing` creation to the corresponding per-scope helper.
Import aliases, from-import aliases, raw zero flags, omitted flags, incorrect
helper arguments, count offsets, and direct starts are all negative fixtures.
The independent full test file passed 15 tests and 12 subtests, and commit
`737c071d` records this enforcement. Native approval, credential UI, progress,
errors, and receipts remain visible; this change does not suppress the human
interaction surface.

## v0.4.19 pending-cancellation restart correction

An actual cancellation restart exposed two deliberately different digest
domains that the first resolver had accidentally treated as one: transaction
semantic JSON and delivery-payload semantic JSON omit the storage newline,
while durable private documents and their HMAC-bound records include it. The
resolver now names and validates those domains separately, without accepting a
second format or weakening immutable-document and HMAC checks. It reconstructs
a pending cancellation only when the exact capsule, unapproved receipt, and
active `unapproved_restored` locator all cross-bind.

Independent review then found that the first test incorrectly treated an
active `terminal_completed` locator before retirement as a valid pending
state. That state is now fixed-closed as a state change and every related
control byte is preserved. The corrected primitive passed 35 focused tests and
18 subtests plus the actual service restart fault reproduction. A second
reviewer re-ran the critical two cases with 14 subtests and reported P0/P1 zero.
Commit `a0839be4` records the corrected primitive. Production caller
integration and its final fault matrix remain pending.

## v0.4.19 runtime cleanup sidecar review

The runtime cleanup candidate introduced a private sibling sidecar so a fresh
process can resume cleanup without trusting transient Python state. Its initial
focused, parent-durability, runtime, Doctor, and capability suites passed, but
an independent destructive-boundary review rejected the frozen candidate with
four P1 findings before service integration.

First, a self-described sidecar was not cross-checked against the surviving
normal candidate seal, so a changed target commit could still authorize tree
cleanup. Second, an NTFS alternate data stream on the sidecar was detected only
at final retirement, after destructive cleanup. Third, replacing the sidecar
with a byte-identical file changed its identity but the old in-memory capsule
could still delete the replacement. Fourth, the retire API accepted a transient
hash string rather than a disk-revalidated durable outer acknowledgment. The
next candidate must bind the capsule creation identity in its own durable
document, verify the sidecar and normal seal including default-stream-only
state before any destructive resume, and require a typed transaction
acknowledgment that revalidates its exact checkpoint or abort receipt from
disk. Normal runtime promotion, sealed cancellation, and unsealed abort must
all record the full terminal-evidence digest and capsule identity before the
sidecar is retired. Until those corrections are re-frozen and independently
approved, the runtime primitive and v0.4.19 remain release-blocked.
