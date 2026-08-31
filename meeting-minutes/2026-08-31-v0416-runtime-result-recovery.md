# 2026-08-31 v0.4.16 runtime and update-result recovery

## Context and user intent

The user supplied a read-only pending-approval feedback snapshot after a tester
attempted the v0.4.15 recovery flow. The user emphasized that another narrow
guard or diagnostic command would not be an acceptable response: the repeated
failure must be reproduced, corrected at its actual boundary, and released
without requiring a nontechnical operator to count records, inspect internal
identifiers, or repair WOM metadata by hand.

The development boundary remained strict. The client archive was not updated,
recovered, or used as a development checkout. Work proceeded in a dedicated
v0.4.16 recovery worktree from the exact v0.4.15 merge commit.
Public code and records do not reproduce the private feedback body, client
paths, usernames, or local identifiers.

## Reported behavior

The feedback exposed four separate defects that combined into one unusable
operator experience:

1. An approved project update had durably installed and activated its target,
   written its receipt, removed its update lock, and reached the terminal
   checkpoint, but the command returned exit 1 with no success result.
2. A later project process reported that every runtime check passed except the
   three core-module receipt binding, even though the observed module bytes and
   receipt inventory matched.
3. The create-only emergency feedback lane was available for a live update lock
   but not for the runtime-mismatch state that prevented every approved writer.
4. Ordinary product language containing `GCP Secret Manager` was treated as a
   credential, while the blocked response also made the caller-input safety
   read look like it had not happened.

The report suggested a same-version `--rebind` repair. Review rejected that as
the product fix: the installed runtime and receipt were already valid, so
asking the operator to rewrite them would hide the observation defect and add
an unnecessary approval and write.

Later release-exit review found a distinct gap behind that decision. A false
binding observation needs no rewrite, but an actually damaged same-version
runtime still stopped at `project_runtime_target_directory_invalid`. The
ordinary updater could describe the damage but could not recover it. The user
must not be asked to distinguish those internal cases or invoke a new repair
verb. The existing approved update command will therefore choose reuse for a
valid target and an exact repair transaction for a genuinely invalid target.

## Reproduction and confirmed cause

Cross-version synthetic recovery showed that v0.4.14 durable update states are
accepted and resumed correctly by v0.4.15. Version compatibility was therefore
not the cause.

The exact failure was then reproduced by resuming a genuine v0.4.14
`domain_committed` transaction under v0.4.15 and injecting only a terminal
transaction-cleanup failure. The domain postimage, runtime receipt, succeeded
claim, lock release, and `completed` checkpoint all remained valid, while the
CLI produced empty standard output, exit 1, a failure artifact with no command
result, and an operation-control record whose stage still said `starting`.

The confirmed design flaw was that post-effect finalization ran after the
authenticated writer result but inside an exception boundary that replaced
that result. The same overwrite window also existed when closing the trusted
Git runner and in both the resume and fresh-approval paths.

The previous hard-exit matrix did not cover a cross-version transaction with
`--output`, operation-control reconciliation, or failure after the authenticated
terminal result. Passing that matrix therefore did not prove this boundary.

## v0.4.16 decisions

### Authenticated terminal handoff

A successful project update must publish a fixed, durable, privacy-safe
terminal handoff after the succeeded claim and exact completed state are
verified but before unlock and transaction cleanup can erase the only replay
context. A later process may replay the same result without a writer or another
native approval only after it independently verifies exactly one handoff, the
succeeded claim, plan and target bindings, terminal checkpoint, current exact
postimage, and lock absence.

A cleanup tombstone or cleanup proof is never success authority by itself.
Forged, stale, ambiguous, or claimless handoffs fail closed. Crash-window tests
must cover interruption after handoff publication, lock removal, cleanup, and
service return.

The final handoff uses one same-directory state machine under
`.zettel-kasten/private/version-update-terminal/`: fixed `active.json`, fixed
`display-pending.json`, an exact one-byte guard, and a hash-named consumed
capsule. Each rename has one parent-directory durability boundary. A raw
delivery capability is never serialized. It is derived from the authenticated
one-use claim; only its digest is stored in the signed ready record.

The CLI publishes the complete project-scoped result and writes exactly one
immutable terminal journal event with delivery pending. The output proof binds
the privacy-safe result payload, handoff, normalized output location, run
identifier, and operation reference. Once those bytes are bound, resume rejects
a replacement `--output`. WOM verifies the HMAC-bound output, atomically moves
`active` to `display-pending`, and then displays the exact bound result. After
display succeeds it moves the same capsule to its hash-named `consumed` history
without appending any delivery- or display-committed journal event.

This is an intentional at-least-once display boundary. A hard exit after some
or all stdout was written but before `display-pending` became `consumed` can
cause identifier-free resume to display the identical result again. It cannot
generate a different output or re-enter the domain writer. A consumed capsule
is history, never a replay candidate. The public
`durable_result_delivery_acknowledged` field means that the authenticated
durable output handoff was verified; it does not prove that a person or model
actually saw, read, or understood stdout.

The v0.4.15 cleanup boundary has three distinct classifications. One complete
cleanup tombstone may be restored only after exact validation of its canonical
cleanup plan, entire file and directory set, terminal checkpoint, succeeded
claim, current postimage, and claim-derived legacy cleanup authority. Resume
then publishes the new v0.4.16 handoff before exact cleanup and never derives
success from the tombstone name alone. A canonical cleanup-proof-shaped file
without its transaction and private claim evidence returns
`no_resumable_project_update`, `past_update_success_attributed: false`, and
`current_project_state_independently_verified: false`; it is inert history and
permits only a separately previewed, freshly approved update. Partial,
malformed, mixed, changing, ambiguous, unsafe, or otherwise non-exact residue
remains `terminal_cleanup_outcome_unknown` and blocks both automatic resume and
fresh approval. Proof-only history never mints a handoff or cleanup authority.

### Resource-close truth

Transaction cleanup, service-owned directory handles, the trusted Git-runner
handle, and result delivery are four separate facts. Both close operations are
attempted even when the first one fails. A primary exception keeps its original
identity; a domain or control mapping keeps its result and gains only a
content-free `service_finalization` attention object.

Windows and POSIX require different close-failure rules. A failed Windows
`CloseHandle` leaves a still-owned handle that can be retried. POSIX `close(2)`
may already have consumed a file descriptor when it reports an error, so WOM
consumes local ownership before that call and never retries the integer. This
prevents a later retry or destructor from closing an unrelated file that reused
the same descriptor number.

### Runtime observation

The project launcher executes `python -m wom_kit.archive_cli`, so the executing
entrypoint is legitimately registered as `__main__`. WOM will accept that
standard alias only when its import spec names the exact archive CLI and its
real path, expected runtime identity, receipt inventory row, size, and SHA-256
all agree. An unrelated `__main__` remains rejected.

Blocked results expose only per-component booleans and reason codes. They do not
echo absolute paths or hashes.

### Same-version runtime repair

An invalid but real, non-reparse target runtime is repairable through the
existing project-version update approval. WOM prepares and fully verifies a
private replacement first. The candidate seal also binds the existing runtime
root identity and complete file inventory. After approval, the existing target
is atomically moved into the same update transaction as an exact private
recovery preimage and the verified candidate is atomically promoted into the
target name.

The transaction recognizes the exact `preimage_final`, `backup_only`, and
`candidate_final_plus_backup` crash states. Public resume continues from those
states without repeating a writer. After the durable exact-human ownership
handoff, a later component failure preserves the lock, sealed transaction,
verified new runtime, and exact private recovery preimage. The ordinary
identifier-free `project-version-update --resume` path reauthenticates the
started claim, skips verified components, and continues from the first
unverified component; it does not enter the historical automatic rollback
path. After authenticated terminal handoff, ordinary exact transaction cleanup
removes the sealed private preimage. Cleanup uncertainty is reported separately
and never changes the verified update result. Unsafe links, reparse points,
ambiguous directories, and changed inventories remain fail closed. A valid
same-version runtime keeps the existing no-change and live-reverification path.

### Emergency report preservation

The existing create-only, append-only feedback-body path is extended to the
exact `project_runtime_mismatch` blocker. It remains unavailable to revise,
supersede, lifecycle-record, or other writers and does not bypass unsafe or
invalid project pins. The result records whether the trigger was update
recovery or runtime alignment without exposing private values.

### Secret detection and truthful reads

The broad word matcher is removed only from the source-fidelity caller-input
gate. Product terms such as `GCP Secret Manager`, `OAuth client`, `cookie
policy`, and `token budget` remain ordinary text. High-confidence values remain
blocked through token shapes, quoted assignment keys, authorization values,
private-key markers, and session/auth cookie signals. Placeholder authorization
text and harmless preference cookies remain allowed.

Blocked output now distinguishes a pre-write caller-input safety scan from the
later canonical first-read publication check. It truthfully says that the body
was read for safety while still echoing none of its values.

## Verification feedback loop

Focused verification covers the strict `__main__` runtime binding, rejection
of an unrelated main module, content-free module diagnostics, create-only
feedback under both update recovery and runtime mismatch, negative writer and
invalid-pin cases, product-language acceptance, raw and JSON credential values,
authorization and cookie values, benign placeholders, and blocked-read truth.
It also covers fresh and resumed close failures, both-close attempts, original
exception preservation, collision and cancellation result preservation,
Windows handle retry, POSIX no-retry, exact terminal serialization, the
`active` -> `display-pending` -> `consumed` hard-exit matrix, immutable journal
truth, exact-output reuse, identical at-least-once display, forged or mutated
delivery evidence, operation-control reconciliation, complete legacy tombstone
validation, proof-only non-attribution, partial/malformed fail-closed behavior,
and two consecutive updates.

The first full hard-exit rerun proved all eight recovery outcomes but exposed a
privacy defect in five terminal results: a transaction reference remained
nested in a receipt path and runtime-candidate locator. The terminal projection
was therefore changed from a top-level allow/drop pass to a recursive privacy
projection. It removes private locator keys at every depth, redacts exact
transaction and approval identifiers in both values and dynamic JSON keys,
redacts private scratch roots and absolute local paths, and fails closed if two
redacted keys would collide. Case-variant identifiers are covered explicitly.
The handoff and delivery proof bind only this sanitized domain result.

Independent adversarial review then found that lexical path matching alone was
not a complete privacy boundary. The projection now validates canonical private
identifier and locator shapes before using them as redaction bindings, examines
the original private-root-bearing value before partial replacement, handles
arbitrary absolute Windows and POSIX paths, and carries exact field context
through nested mappings and sequences. Public route syntax is preserved only
for the two explicit root public-route scalar fields; the same bytes in a path,
root, locator, list, nested alias, dynamic key, or ordinary value are redacted.
Malformed bindings and redacted-key collisions fail closed.

The public release-readiness gate and synchronized package-resource check pass;
the current package contains 169 synchronized resources. A synthetic GitHub
token shape initially triggered the public privacy gate, so its test fixture was
changed to runtime concatenation while the same secret-shape rejection test
continued to pass. The public diff contains no client username, client project
name, feedback identifier, private report digest, or client path.

The full transaction and hard-exit matrices, complete CI, wheel installation,
exact tag and release asset verification, and anonymous clean-environment
download remain release exit criteria. Publishing v0.4.16 will not update or
modify any client project; each tester chooses whether and when to install and
run the separately approved project update.

### Late adversarial findings: namespace races and interrupted publication

Before the release gate, an independent replay audit reproduced three further
P1 failure classes. The generic no-replace move validated parent paths and then
used path-based rename authority, so a parent-directory swap could move a
foreign same-name file. Cleanup enumerated a tombstone once and then deleted by
detached pathname, so a post-enumeration replacement could be deleted. A crash
during initial terminal publication could also leave a random, undiscoverable
partial temporary file.

Release remains blocked until the first two transaction primitives retain exact
parent and entry authority across mutation, fail closed under injected source,
destination, file, and descendant-directory swaps, and safely reconcile the
legal proof-plus-byte-identical-plan crash state. The terminal initial-create
path now uses a deterministic name bound to the exact terminal bytes. A complete
stage resumes publication; an incomplete stage is moved without replacement to
an identity-and-content-bound evidence name and is never deleted. POSIX creates
the stage by basename under the held parent descriptor; Windows retains the
non-delete-sharing ancestor chain. Exact-stage resume, partial-stage
preservation, pre-existing-residue conflict, destination collision, and
transition mutation tests pass. The full source-fidelity suite also passes 26
tests and 194 subtests after the closed placeholder vocabulary was hardened.

### Final platform and cleanup boundary

The release review retired the POSIX mutation implementation before release.
Approved project-update mutation, same-version repair, and mutation-bearing
resume are Windows-only in v0.4.16. POSIX keeps preview and read-only inspection,
but every terminal mutation entry point fails before creating the control root,
guard, stage, or any other file. This is an explicit zero-write contract.

On Windows, the transaction retains the exact root and guard handles without
delete sharing. It rejects reparse points, non-regular entries, additional hard
links, alternate data streams, volume changes, and device/inode mismatches. A
torn zero-byte guard may be completed only through the retained exact handle to
the canonical one-byte value. Source swaps, destination races, root swaps,
hard-link substitution, stream substitution, and a swap before a fallback open
all fail closed.

Cleanup now writes `cleanup-plan-v0416.json`, binding the transaction root's
device, inode, and Windows creation time. The released predecessor's
`cleanup-plan.json` is never direct delete authority. Recovery first restores
that complete legacy tombstone, reauthenticates the normal transaction and
claim, then upgrades it to the current bound sidecar. Deletion uses retained
Windows handles and revalidates normalized volume, inode, and creation time;
POSIX deletion remains fail closed.

The final local evidence before publication includes:

- 129 transaction tests and 52 subtests passing;
- 17 terminal-create tests passing, with two platform-specific skips;
- 60 operation-control, terminal, and deletion tests passing, with five
  platform skips and 35 subtests;
- 46 source-fidelity, documentation, and resource tests with 435 subtests;
- 30 project-runtime and candidate tests, two platform skips, and 10 subtests;
- the exact released-predecessor hard-exit recovery passing against the final
  frozen tree without a second approval or writer execution;
- 169 packaged resources synchronized; and
- the public privacy and release-readiness gates passing.

The development branch was given a generic runtime-recovery name before any
push. Publication remains incomplete until the full remote CI matrix, exact
merge commit tag, release asset, anonymous wheel download, and isolated install
all pass. No client archive is modified by those release operations.

The candidate wheel gate then built v0.4.16 outside the repository and installed
it into a fresh isolated environment. It verified all 169 packaged resources,
252 wheel members, all four console and MCP entry points, dependency health,
strict Doctor behavior, and the installed recovery smoke contracts. The wheel
privacy scan covered 15,012,145 text-like bytes and found zero Windows user-path
or secret-pattern matches. Two stale test assertions were also corrected to
construct a genuine predecessor cleanup sidecar and to verify the new
identifier-free terminal summary; the corrected test and both adjacent tests
passed with seven subtests. These are candidate proofs only. The release wheel
will be rebuilt and reverified from the exact merge commit.

### First remote CI feedback loop

PR #92 was opened from the generic release branch, and its first remote CI run
correctly blocked publication. The release-readiness gate, the Letter 148 scale
gate, and the Windows link-index scale gate passed. No merge, tag, GitHub
Release, client installation, or client-data write followed the failed run.

The broad failure count was mostly a cascade from one over-broad test helper
that incorrectly required terminal-result bindings on unrelated compound
failures. The remaining focused failures exposed stale cross-platform fixtures:
Windows mutation tests still ran on POSIX, six updater-routing tests used fake
nonexistent project roots and combined human progress with JSON output, legacy
cleanup fixtures omitted the new result-availability fact, and the runtime skill
exceeded its 1,400-word budget by nine words. The helper assertion was removed,
the routing tests now use real temporary projects and separate output streams
and remain cross-platform. Only tests that perform actual Windows terminal
mutation are skipped on POSIX, while the explicit POSIX zero-write tests remain
active. The fixtures carry the required fact, and the synchronized runtime
skill is 1,399 words.

Two additional Windows shard-1 failures had the same stale-contract character.
The bundle-drift test parsed progress stderr together with JSON stdout, and the
same-version repair hard-exit matrix assumed one approval claim even though the
initial install approval and separately approved repair correctly leave two.
The tests now parse only stdout and distinguish repair boundaries without
removing approval, no-write, rollback, receipt, or privacy assertions.

An independent diff review caught six initially over-broad Windows-only test
decorators. Those tests mock the service boundary and do not perform terminal
mutation, so the decorators were removed and their routing, no-approval,
no-write, and heartbeat coverage remains active on both Windows and POSIX.

Focused Windows tests pass for the corrected contracts. Independent Linux
container runs also pass the affected project-update, transaction, cleanup,
collision, and bytecode-repair selections with platform skips limited to the
declared Windows-only mutations. These corrections are not publication proof:
all remote jobs must run again from the correction commit, and the final wheel
must be rebuilt from the exact merge commit.

The corrected local tree then passed 178 combined transaction, collision,
bytecode-repair, and staged-cleanup tests; 66 release-document, resource,
privacy, and readiness tests with one declared platform skip; and the six
cross-platform updater-routing tests on both Windows and a read-only Linux
container. Every one of the 344 Ubuntu failure or error headers from the first
run maps to a corrected cause, with zero unclassified failures. A new isolated
candidate wheel verified 169 resources, 252 members, four entry points, and the
installed smoke workflows while finding zero Windows user-path or secret-pattern
matches across 14,930,073 text-like bytes. It is still only a candidate; remote
CI and the exact-merge release rebuild remain mandatory.

### GitHub secret-scanning stop and remediation

GitHub secret scanning opened alert #1 against the first PR commit and one
credential-blocking test fixture. Release work stopped immediately: the second
CI run was cancelled, and no merge, tag, release, client installation, or
client-data write had occurred.

The candidate was not recovered from a user, client, credential store,
environment, or archive. Its 35-character suffix was the deterministic sequence
of lowercase `a` through `z` followed by digits `1` through `9`, created in the
same test commit to exercise `credential_secret_present` and no-echo behavior.
Repository and GitHub audits found one alert and one complete candidate only,
with no push-protection bypass. The commit was present only on the PR branch;
`origin/main`, every tag, and every published release remained unaffected.

Even a synthetic provider credential shape must not appear whole in public
source. The fixture now assembles an equivalent high-confidence shape only at
test runtime. The public privacy gate adds content-free `PRIV021` detection for
complete Google API key shapes, including files under `tests/`, and its
regression test proves that neither the candidate nor its tail is echoed. The
credential-blocking test and focused privacy tests pass, while a staged-snapshot
privacy scan reports zero findings.

The PR branch history was replaced from the clean `origin/main` base. The clean
release commit `e78d14b4` has the exact corrected implementation tree, while
the alerted commit is no longer reachable from the PR head. Local and remote
release readiness passed on the replacement history, including the new privacy
rule.
Alert #1 was then resolved as `used_in_tests` with a content-free remediation
comment; the repository has zero open secret-scanning alerts and no bypass
record. Full CI restarted from the clean history, and merge remains blocked
until that entire matrix succeeds.
