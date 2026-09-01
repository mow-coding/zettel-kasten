# Project Version Update

Status: v0.4.17 exact-human project update with recoverable terminal control history; collision and bytecode repair writers remain closed

Current boundary: `project-version-update` is reopened only through the native
exact-human approval broker. The CLI derives a content-free dry-run digest and
target binding, a person approves that exact context, and the service derives
the preview again and authenticates the one-use claim before the existing
locked updater may fetch or write. Direct unbound service calls fail before a
private project read. Collision preserve-relocate and `project-bytecode-repair`
approval remain fixed closed.

## v0.4.17 Terminal Cleanup Recovery Boundary

Fresh `project-version-update --dry-run` and the matching approval path now run
the same bounded, read-only classification of the private transaction
namespace. The dry-run cannot report `ready_for_approval` when exact terminal
control history would make the approval fail. Both paths instead return
`terminal_cleanup_required` with
`project_version_update_terminal_cleanup_required` before native approval,
approval-key access, or project-domain writer entry.

The operator does not supply a target, transaction ref, approval id, cleanup
proof, file count, or digest. Keep other writers for the same project stopped
and run the public identifier-free recovery command:

```powershell
& <exact-target-bootstrap> project-version-update <project-or-archive-root> `
  --resume `
  --affirm-external-writers-quiescent `
  --progress `
  --format json
```

WOM recognizes a preapproval abort only when its complete fixed control tree,
reservation, abort intent and receipt, identities, hashes, archive identity,
and cleanup authority all agree. It writes an identity-bound v0.4.17 cleanup
plan, moves the exact tree to a no-replace tombstone, deletes only plan-bound
members, and retains one canonical proof. The same authority can resume at
every supported cleanup boundary. Unexpected members, link anomalies, unsafe
types, active locks, identity or byte changes, and namespace races refuse
cleanup without deleting the evidence.

Abort-history compaction is not a project update. It does not enter the domain
writer, modify source, install or replace a runtime, change the pin, alter
archive content, attribute a past success, or authorize a fresh approval. After
recovery converges to proof-only history, run a new dry-run and request one new
exact approval only if that new preview is ready.

If compaction accompanies another resume or stops after completing only some
exact histories, the result preserves both facts. It reports
`terminal_abort_histories_compacted`, `cleanup_proofs_written_or_verified`,
`terminal_abort_history_compaction_state`, and
`terminal_abort_history_compaction_incomplete`. `files_written_scope:
project_domain_only` means an empty `files_written` list does not deny private
control effects. The content-free `effect_summary` records
`private_control_mutation_performed_or_verified` and
`private_control_mutation_may_be_incomplete` without exposing private paths,
references, hashes, or authorities.

Partial, malformed, mixed, changing, ambiguous, or unsafe residue remains
`terminal_cleanup_outcome_unknown` with
`project_version_update_terminal_cleanup_outcome_unknown`. Do not loop resume,
delete a lock, edit a pin, or remove a transaction directory, tombstone, or
proof. Known cleanup gates cross the CLI boundary only through fixed allowlisted
reason codes and privacy-safe next actions; arbitrary internal exception text
is never echoed.

## v0.4.16 Historical Terminal Result Boundary

After the exact one-use claim succeeds and the complete postimage is verified,
WOM writes a private authenticated terminal handoff before transaction cleanup.
The public result keeps approval and transaction locators private and reports
claim, completed checkpoint, lock absence, cleanup, service-resource close,
Git-runner close, durable output delivery, and attention state as separate
facts. Cleanup proof is never used as success or retry authority.

Approved and resumed updates receive a project-scoped
`.zettel-kasten/diagnostics/*.json` output automatically when `--output` is
omitted before a result is bound. The output wrapper, one immutable terminal
journal record, and handoff bind one terminal delivery proof. The private
handoff moves through `active`, `display-pending`, and hash-named `consumed`
states without a later journal append. Once pending delivery exists, resume
rejects a replacement `--output`, reauthenticates the exact succeeded claim and
postimage, and reuses the exact bound output. A crash can cause the identical
result to be displayed again; this at-least-once display never regenerates the
result or reruns the domain writer. Consumed state is history, not a replay
candidate. `durable_result_delivery_acknowledged` means the authenticated
durable output handoff was verified, not that a person or model saw stdout.
`domain_writer_reentry_allowed` and `automatic_retry_allowed` remain false.

Publishing or installing v0.4.16 changes no client archive, source mirror,
runtime, launcher, or version pin. The client separately chooses whether and
when to approve a project update.

## Plain-Language Purpose

A WOM project can have four version states that drift apart:

1. the WOM-kit code currently loaded by Python;
2. the project-local code copy at `.zettel-kasten/source`;
3. one or more small files that remember the intended version, called pins.
4. the project-local installed runtime and launcher used for ordinary commands.

Previously, a human had to receive update files with Git, move the local code to
the release tag, and edit the pin by hand. `project-version-update` turns those
steps into one reviewed transaction with explicit evidence and rollback.

It updates the tool around the archive. It does not rewrite the user's zets,
objets, manifests, source material, or external database.

## v0.4.1 Global CLI Escape Is Not A Project Update

After the public v0.4.1 GitHub Release actually exists and lists the exact
wheel, an operator with the v0.4.0 `uv tool` installation may replace only the
isolated global CLI:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.1/wom_kit-0.4.1-py3-none-any.whl"
archive --version
```

Run the version check in a new process and require exactly `archive 0.4.1`. This does
not touch `.zettel-kasten/source`, `installed-version.txt`, any other project
pin, or the archive. A project-local mirror that was v0.4.0 therefore remains
v0.4.0. The global v0.4.1 CLI can supply the newly exact-approved single
`zettel-objet-link` apply route, but it does not make the project-local updater
safe or authorized.

`project-version-update`, collision preserve/relocate, and
`project-bytecode-repair` approval remain fixed closed in v0.4.1. Keep using
their read-only previews and inspections. Do not hand-edit a pin, copy global
package files into the mirror, or describe the mirror as v0.4.1 without a
future supported project-update transaction and its verification evidence.

## v0.4.3 Project Runtime Activation

For a v0.4.3-or-newer tagged source that carries
`wom-kit/project-runtime-policy.json`, update is not complete when Git and pins
match. The approved updater also requires the running bootstrap to be the exact
public target wheel with a bound SHA-256. It creates, but does not yet activate,
this side-by-side runtime:

```text
.zettel-kasten/runtimes/vX.Y.Z/
```

The tagged policy binds both the public WOM wheel and an exact dependency
supply lock. For v0.4.3 the supported runtime target is CPython 3.12 on Windows
x86-64. The updater verifies every locked artifact's file name, byte size, and
SHA-256, retains those artifacts in the runtime, and installs only from those
local files with pip isolation, package-index access disabled, and dependency
resolution disabled. Unsupported interpreters and platforms fail closed.

The updater verifies the retained artifacts, installed payload bytes, `pip
check`, package version, packaged resource manifest, exact installed
distribution inventory, and a separate new Python process. Existing runtimes
must pass the same live verification before reuse; historical receipt booleans
alone are not sufficient. Windows console-script paths are rebound and
rechecked at the final runtime directory before activation. It then writes the stable project launcher
`.zettel-kasten/bin/archive.cmd`, which contains only a project-relative route
to the exact versioned runtime.

The existing `.zettel-kasten/installed-version.txt` remains the active version
source; no duplicate active pin is introduced. The active pin is written only
after the runtime and launcher pass verification. The user PATH, shared
`archive.exe`, and other project folders are never modified.

An ordinary activation keeps the compatible v0.3 project-update receipt and
binds a v0.1 project-runtime receipt. A same-version invalid-runtime repair
uses the repair-aware v0.4 project-update receipt and exactly binds its v0.2
project-runtime receipt schema and SHA-256. Both receipt pairs bind the release
tag and commit, policy and supply-lock SHA-256, complete artifact inventory,
installed-payload digest, WOM wheel SHA-256, Python version, previous and new
pin values, launcher state, and new-process checks. Crossed schema pairs fail
closed. Before the exact-human durable handoff,
the historical preparation path restores transaction-owned changes on a handled
failure. After that handoff, a component failure preserves the lock, sealed
transaction, verified new runtime, and exact private recovery preimage so the
identifier-free public `--resume` path can continue from the next checkpoint.
It does not silently enter the legacy rollback path. A healthy previous runtime
is never deleted merely because another version is activated. The narrow
same-version repair exception removes the invalid old runtime's private
recovery preimage only after authenticated terminal commit and exact transaction
cleanup.

After success, ordinary project commands should start with:

```powershell
.\.zettel-kasten\bin\archive.cmd version <project-or-archive-root> --format json
```

A project write started by a different running WOM version is blocked before
dispatch as `project_runtime_mismatch`, including writers such as `index` that
do not expose a separate approval flag. Read-only `version` and the updater
bootstrap (`project-version-update`, `version-update`, or `update-wom-kit`)
remain available; all updater names enter the same exact-public-wheel checks.

## Safe Workflow

First preview. This performs no fetch and writes nothing:

```powershell
& <exact-target-bootstrap> project-version-update <project-or-archive-root> `
  --target vX.Y.Z `
  --dry-run `
  --progress `
  --output .zettel-kasten/diagnostics/update-preview-20260811-001.json `
  --format json
```

The target may not exist locally yet. In that case the dry-run may report
`ready_to_fetch_on_approve`, but that informational preview cannot mint an
exact-human approval. Approval must be invoked from the CLI with a safe reviewer
and the complete-transaction quiescence affirmation:

```powershell
& <exact-target-bootstrap> project-version-update <project-or-archive-root> `
  --target vX.Y.Z `
  --approve `
  --reviewed-by person:me `
  --affirm-external-writers-quiescent `
  --progress `
  --format json
```

The approved command first acquires the project update lock and performs one
atomic configured-origin fetch. Before it opens the native dialog it verifies
and fixes the exact annotated tag object, peeled target commit, `origin/main`,
source HEAD, Git trust configuration, recognized pin bytes, public WOM wheel,
runtime policy, dependency supply lock, runtime effect set, and materialization
preflight. Only this `approval_prepared` plan can mint the exact-human approval.

The updater keeps the same lock while the native dialog is open. After approval
it performs no fetch, provider query, or other network operation. It rechecks
the complete prepared snapshot and authenticated claim before the first source,
runtime, launcher, pin, or update-receipt write. Drift fails closed. A cancelled
dialog or failed preparation changes none of those durable project targets and
releases the owned lock; successfully fetched Git refs may remain as explicitly
reported preparation evidence. POSIX remains preview-only.

These project-local output paths opt into v0.3.314 operation observation. When
the command is started from an archive root, use a fresh
`.wom-scratch/diagnostics/*.json` output instead. Stderr prints an opaque
`operation_ref` before the long work. If the caller times out, do not start a
duplicate updater; use `operation-control` status, bounded wait, or recovery
guidance with the exact root and reference. Generic `operation-control` cancel
and resume remain unsupported. The command-specific authenticated recovery path
below is the only supported update resume, and completion still requires a
fresh-process `archive version` check.

## Interrupted Update Recovery

Historically, the v0.4.15 recovery guarantee was bounded to a live
`version-update.lock` or
the exact lockless unlock tail while the original transaction directory still
exists. Its first unsupported boundary is after `completed`, once the original
transaction directory has been successfully renamed to a terminal cleanup
tombstone. A tombstone or cleanup proof is not authenticated outcome or cleanup
authority: v0.4.15 reports `terminal_cleanup_outcome_unknown` with a nonzero
exit and does not infer success, failure, or cancellation, automatically retry,
or delete that evidence.

v0.4.16 closes that historical terminal boundary without treating residue as
authority. A current v0.4.16 update publishes an authenticated privacy-safe
ready handoff bound to the succeeded claim, completed checkpoint, exact
postimage, and cleanup authority before cleanup. One complete legacy v0.4.15
cleanup tombstone can also be restored only when its canonical cleanup plan,
complete file and directory set, terminal checkpoint, succeeded claim, current
postimage, and claim-derived legacy cleanup authority all validate. Resume then
publishes the v0.4.16 handoff before continuing exact cleanup; it never infers
success from the tombstone name or cleanup plan alone.

A canonical cleanup-proof-shaped file without the transaction and private
claim evidence returns `no_resumable_project_update`,
`past_update_success_attributed: false`, and
`current_project_state_independently_verified: false`. That file is inert
history: it does not mint a handoff or authorize cleanup/retry, but it no longer
traps a separately previewed and freshly approved update. Partial, malformed,
mixed, changing, ambiguous, or unsafe cleanup state remains
`terminal_cleanup_outcome_unknown` and blocks both automatic resume and a fresh
approval. If current authenticated cleanup is still incomplete, the public
result keeps the verified update outcome as durable attention and leaves the
active handoff available for exact resume.

If the process stops after approval, `version-update.lock` remains and ordinary
project writers stay blocked. That is intentional: source, versioned runtime,
launcher, active pin, and receipt may not yet describe one version. Never
delete the lock or hand-edit the pin to make the block disappear.

The ordinary recovery command contains no internal identifier:

```powershell
& <exact-target-bootstrap> project-version-update <project-or-archive-root> `
  --resume `
  --affirm-external-writers-quiescent `
  --progress `
  --format json
```

Equivalent compact form:

```powershell
& <exact-target-bootstrap> project-version-update <project-or-archive-root> --resume --affirm-external-writers-quiescent --format json
```

WOM first classifies the exact durable transaction. An interruption before
native approval is handled by proving unchanged preimages and cancelling only
the incomplete preparation scaffold; source, active runtime, launcher, pin,
and update receipt remain unchanged, and a fresh approval is then required.
For an already-approved update, WOM validates the exact live lock or the sole
authenticated unlock-tail transaction, reopens the sealed plan, restores the
original target, transaction, reviewer, and approval context, and inspects only
its bound local claim store. Resume proceeds only when exactly one
authenticated, checkpoint-valid `started` or `succeeded` claim matches that
unchanged context. A zero-claim transaction cancels its scaffold only when
durable state proves it is untouched preapproval, then requires a fresh
approval. Zero claims for an approved or indeterminate transaction, more than
one match, authentication failure, context drift, journal drift, or checkpoint
drift fail closed before a domain write.

Normal resume requires no caller-supplied `--target`, `--transaction-ref`,
`--approval-id`, or `--reviewed-by` and opens no second native approval window.
WOM derives every binding from authenticated durable state; the person never
needs to inspect or supply an internal identifier.

A `started` claim continues only the remaining idempotent checkpoints. A
`succeeded` claim skips the writer and runs only the separately guarded
finalizer. WOM removes the update lock only after the source, runtime, launcher,
pin, and receipt converge and independent verification succeeds. In v0.4.16,
the authenticated ready handoff also carries this result across the original
transaction-to-cleanup rename and any bounded cleanup interruption without
reentering a domain writer. Then start a new process through the project
launcher:

```powershell
.\.zettel-kasten\bin\archive.cmd version <project-or-archive-root> --format json
```

If recovery returns `preapproval_scaffold_cancelled`, the interrupted update
was not applied and `fresh_approval_required` is true. Run a new preview and
request one fresh exact approval instead of treating that result as an update.
In that result, `files_written_scope: project_domain_only` means the empty
`files_written` list covers source, runtime, launcher, pin, receipt, and other
project-domain files only. It is not a claim that recovery had no control
effects. The content-free `effect_summary` separately reports durable control
evidence, cancellation checkpoints or reservation-abort evidence, candidate
cleanup or verified absence, and lock release without returning their paths or
identifiers. `preapproval_recovery` also distinguishes a live lock verified by
this invocation from an exact prior lock binding followed by verified lock
absence.

While recovery is required, ordinary draft, mint, link, index, metadata, and
provider writers remain blocked. The sole incident-reporting exception is an
exact-approved `operator-feedback-compose --intent create`: it may append one
new feedback body and body receipt without revising or superseding an existing
body, changing feedback metadata, marking anything resolved or delivered, or
changing `version-update.lock`, source, runtime, launcher, pin, or update
receipt.

## Ignored-Entry Collision Inspection And Preservation

The ordinary preflight retains the bounded materialization planner whenever
the exact target commit is locally available. Historical approved updater
evidence used the same planner. Every follow-up collision inspection
requires the same plan digest rather than silently binding a new local set.
The public plan reports only fixed reason codes, counts, a
`materialization_plan_sha256`, and sorted ordinal references such as
`update-entry:0001`. An ordinal is meaningful only together with that exact
plan digest. It is not a path hash, cannot be replaced by a bare number, and
does not disclose the ignored local name, absolute path, bytes, or byte hash.
The digest also binds the fixed component comparison scheme and every private
raw-to-canonical mapping used by that run. The one scheme applies NFKC,
case-folding, HFS-ignored characters, Windows trailing-space/dot and reserved
name rules, `.git` aliases, and conservative Win32 8.3-looking-name rejection
to the actual worktree, current tree, and target tree. Those mappings affect the
digest but are never returned. Exact raw current-tree membership is checked
first, so canonical equality cannot turn an ignored alias into a tracked file.

When a result contains multiple references, classify the complete unchanged
set with one planner pass. Do not pass `--entry-ref`; `inspect-all` derives the
exact complete set from the target and materialization digest:

```powershell
archive project-version-update-collision <project-or-archive-root> `
  --target vX.Y.Z `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --action inspect-all `
  --dry-run `
  --format json
```

The CLI returns only counts, fixed entry/runtime kinds, and an eligible
remediation route. It does not print the derived local references, filenames,
relative paths, or absolute paths. If and only if the complete set is verified
as ignored derived Python bytecode plus its cache directories, the output gives
these three separate manual steps:

```powershell
archive project-bytecode-repair-plan <project-or-archive-root> `
  --target vX.Y.Z `
  --expected-materialization-plan-sha256 sha256:<64-lowercase-hex> `
  --dry-run --format json

archive project-version-update <project-or-archive-root> `
  --target vX.Y.Z --dry-run --format json
```

Review the repair plan, then stop. `project-bytecode-repair` approval returns
`compound_exact_human_approval_binding_required` before private project reads
or mutation and removes no bytecode/cache entry or receipt. A later updater
invocation must also remain a fresh preview.

If a result reports one of these references, inspect it without rerunning the
updater:

```powershell
archive project-version-update-collision <project-or-archive-root> `
  --target vX.Y.Z `
  --entry-ref update-entry:0001 `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --action inspect `
  --dry-run `
  --format json
```

Inspection reruns the bounded planner and requires exact digest agreement.
Drift blocks the command instead of silently rebinding the ordinal. Default
output stays opaque. `--reveal-target-relative-path` is an explicit inspect-only
option: it may disclose a path derived solely from the verified public target
tree when that exact mapping is provable. It never discloses an ignored local
path or an unrelated unsafe-entry name.

An eligible ignored regular entry may have a separate preservation preview:

```powershell
archive project-version-update-collision <project-or-archive-root> `
  --target vX.Y.Z `
  --entry-ref update-entry:0001 `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --action preserve-relocate `
  --dry-run `
  --format json
```

Do not replay it as an approved preservation. In v0.4.2 approval returns
`compound_exact_human_approval_binding_required` before private project reads
or mutation and moves no payload or receipt. The detailed transaction below
describes historical v0.3.315 evidence only.

This is a preservation-only transaction, not cleanup. It is limited to an
exact verified target-tree file key whose local obstruction is Git-ignored,
absent from both the current commit tree and index, bounded, regular,
non-reparse, and single-link. Approval retains the exact opened file identity
and its directory chain, then performs one same-volume, no-replace atomic
rename into private project control storage. It writes a create-only private
intent before the rename and a separate create-only completion receipt after
verification. The intent binds a bounded SHA-256, stable Windows volume/file
identity, link count, and size read from the exact opened source handle. The
completion receipt binds the same evidence re-read from the exact no-reparse
destination handle. A later terminal observation reopens and hashes that
payload before accepting both receipts. This provides unauthenticated internal
consistency and detects a changed payload, changed receipt, or replacement file
when the other private artifacts remain intact. These bindings remain private.
Public output truthfully reports whether content was read and the fixed read
stage, but never returns the private source mapping, quarantine path, payload
name, bytes, content hash, or file identity.

This is not a MAC, signature, ACL, or tamper-proof evidence system. A process
already running as the same local user and able to coherently rewrite the
payload plus both private receipts can construct a new internally consistent
state; detecting that coordinated rewrite is outside the v0.3.315 trust
boundary. Result fields therefore qualify terminal verification as
`unauthenticated_private_state_internal_consistency`, report authenticated
binding as false, and advertise only single-artifact drift detection. This is
the same local-user limitation documented for the operation journal.

The action never deletes the collision payload bytes or runs unlink-style
cleanup on that payload. A successful relocation does vacate the original
source name through that one atomic rename. This payload-specific boundary is
the meaning of `write_boundary.deletes: false`; create/remove lifecycle for
owned temporary receipt files and the coordination lock is reported separately
and is not a claim that no control artifact is ever removed. It never
overwrites a destination, follows a symlink/junction/reparse point, repairs a
directory tree or hard link, copies as a fallback, retries the updater, or
changes a version pin. Unsupported kinds and any identity, plan, bounds,
ignore-rule, index, target-ref, or ordinal drift fail closed. If an intent,
rename, completion receipt, or lock transition is incomplete or tampered,
WOM-kit retains the deterministic private case and any retained owned update
lock, reports `recovery_required`, and forbids blind rollback, cleanup, or
replay. Only a strictly verified intent, payload, and completion receipt with
the source name absent and the project-update lock absent is returned as an
idempotent, read-only `preserved_relocated` terminal observation. That
observation does not rebind the ordinal, move the payload, or retry the updater.
Every collision result says `fresh_preview_required: true`. A terminal
observation also says `current_plan_evaluated: false` and returns no current
plan digest: it verifies the private completed case, not the present updater
plan. The final `project_update_lock_absent_verified` field becomes true only
after this invocation releases its owned lock and separately verifies a safe
missing path; a read-only terminal observation may report only the distinct
start-of-observation absence fact.

An unexpected exception during approved preservation is never projected as a
verified no-write result. It reports `outcome_verified: false`,
`writes: null`, `writes_may_have_occurred: true`, and `recovery_required`, and
sets both `preservation_relocation_attempted` and
`preservation_relocation_succeeded` to null while reporting
`relocation_may_have_been_attempted: true`. It retains any owned lock whose
identity is available. The same exception during inspection or dry-run remains
a verified zero-write failure with false relocation fields.

After auditing historical preservation evidence, run a new
`project-version-update --dry-run`. Historical preservation grants no current
authority. The collision surface is CLI-only and has no aliases or MCP method.

## Platform Boundary

Historically in v0.3.291, the write transaction was supported only on Windows.
Windows directory handles are opened without `FILE_SHARE_DELETE`, so every
held write-path directory behind the project root, `.zettel-kasten/source`,
its `.git` tree, pins, lock, and receipts cannot be renamed, deleted, or
replaced by a junction while the transaction resolves child paths.

Every v0.4.3 platform can still run the useful read-only dry-run. POSIX result
is `status: preview_only_platform_unsupported`, includes a warning, and reports
`write_boundary.approval_platform_supported: false`; the exact-human writer is
Windows-only. On Windows, an unbound direct approval call returns
`exact_human_approval_required` before private project reads, and the bound CLI
route must authenticate the exact preview and target. An open POSIX directory
descriptor does not prevent another process from renaming that pathname, and
the Git plus complete-tree update is not descriptor-relative end to end.

## What Approval Verifies

Before changing the checked-out source or a pin, WOM-kit requires:

- an existing project or archive root;
- the exact project-local `.zettel-kasten/source` directory;
- that directory to be the root of a Git working tree;
- a conventional, real project-local `.git` directory, not a linked worktree,
  symlink, junction, reparse route, alternate object store, or grafted history;
- an exact raw snapshot of every tracked worktree file, the index entries, and
  index flags, with no tracked edits or unknown untracked files;
- a non-tracked local `installed-version.txt` as the only allowed untracked
  mirror file;
- no symbolic-link metadata directory, source mirror, pin, or receipt route;
- a configured Git remote named `origin`;
- an exact stable `vMAJOR.MINOR.PATCH` target that is not lower than any
  recognized project pin or project-local source version;
- no existing update lock.

Since v0.3.304, the already loaded WOM-kit runtime is explicitly not part of
the forward-only comparison. The transaction changes the project source mirror
and recognized pins, not the Python code already loaded in the current
process. Therefore an external development runtime newer than the requested
release is reported as informational context and cannot turn an otherwise
forward project transition into a downgrade.

Structured output makes this boundary inspectable:

```text
forward_only.comparison_basis: recognized_project_pins_and_project_source_versions
forward_only.running_runtime_used: false
runtime.used_for_forward_only_decision: false
```

A target below any recognized project pin or source version still fails
closed. Its next action tells the operator to choose a target at least as new
as every recognized project version and rerun the dry-run. Do not hand-edit a
pin to bypass that gate.

Approval then uses one non-force, atomic Git fetch for only:

```text
origin main -> refs/remotes/origin/main
origin exact target tag -> the same local tag
```

A colliding local tag is not force-overwritten. Raw Git stderr and the remote
URL are not copied into WOM output or receipts.

Local Git inspection runs with replacement objects and lazy fetch disabled.
Optional locks, filesystem monitors, repository hooks, attributes, and global
exclude files are disabled for the bounded inspection path. WOM-kit does not
use `git status`, because status can invoke repository-configured clean or
process filters. It instead compares the commit tree, stage-zero index, index
flags, bounded raw worktree bytes, and untracked paths directly.

Immediately before the approved fetch, WOM-kit rechecks a bounded trust digest.
It binds the effective included Git configuration plus exactly these four
`GIT_*` environment variables when present:

```text
GIT_ASKPASS
GIT_PROXY_COMMAND
GIT_SSH
GIT_SSH_COMMAND
```

It does not bind the selected `git` executable, `PATH`, `HTTP_PROXY`,
`HTTPS_PROXY`, `SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `SSH_AUTH_SOCK`, `HOME`, or
other non-`GIT_*` toolchain/transport environment. Those values must remain
trusted and stable for the entire approval.

The fetched target must:

- be an annotated tag;
- resolve to a commit reachable from fetched `origin/main`;
- contain the target version in `wom-kit/pyproject.toml`;
- contain the same version in the package init;
- contain the same version in the repository-root package shim.

This proves agreement with the project's configured origin and main history. It
does not prove a cryptographic tag signature. The result and receipt say so.

## Apply And Receipt Order

After verification, WOM-kit:

1. on Windows, holds the real project root, source tree, `.git` tree, pin
   parent, and lock/receipt path directories against rename or reparse
   replacement;
2. reserves an exclusive project-update lock and records its file identity;
3. reads the complete tracked file tree and bounded blob bytes from the exact
   target commit;
4. validates actual, current, and target names with one component comparison
   scheme, including NFKC/case-folding, HFS-ignored characters, Windows
   trailing-space/dot and reserved names, `.git` aliases, conservative Win32
   8.3-looking names, and path length limits. A case-only tracked rename is
   blocked unless a later design proves it safe. A file/directory transition is
   allowed only for its exact raw tracked ancestry; an ignored file or even an
   empty ignored descendant directory blocks a directory-to-file transition;
5. after the bounded planner finishes, rechecks the complete approved source
   snapshot immediately before the first path write. Any difference preserves
   the changed bytes, performs no source or pin write, releases the owned lock,
   and requires a fresh dry-run instead of reusing approval;
6. manually materializes the complete target commit tree, removes only tracked
   paths that disappeared, writes exact target blobs, restores executable
   modes, and rebuilds the stage-zero index without running `git checkout`;
7. before moving `HEAD`, verifies every target file's exact raw name,
   canonical-key cardinality, body bytes, parent directory spelling, and mode.
   A failed proof never advances `HEAD`; an exact just-written target snapshot
   is restored to the original tree and verified, while any concurrent drift
   retains the owned lock for recovery instead of being overwritten;
8. detaches `HEAD` at the target commit, then verifies the resulting raw
   worktree, index, flags, commit, all three source
   versions, and the full synchronized runtime-resource set;
9. for a target runtime policy, materializes the exact public wheel into the
   versioned side-by-side runtime, verifies it, and prepares the stable
   project-relative launcher without changing PATH;
10. rechecks checkpoint snapshots, writes any recognized mirror or legacy pin,
   and writes the canonical project pin last as the activation checkpoint;
11. creates and immediately holds a missing `receipts/` parent and
   `version-updates/` root one level at a time, validates the applicable v0.1
   ordinary or v0.2 same-version-repair project-runtime receipt
   document, and creates one new receipt under
   `.zettel-kasten/receipts/version-updates/` with `O_EXCL`, never replacing an
   existing path; the receipt writer refuses to run unless that root is
   already held; and
12. rechecks the owned terminal state before removing only the lock reserved by
   this transaction.

This is checkpointed change detection, not atomic file compare-and-swap.
Windows directory handles stabilize directory names against rename/reparse
replacement, while source, index, ref, pin, lock, receipt, and configuration
snapshots are rechecked at defined checkpoints. They cannot prevent an
external editor, sync client, backup tool, or another Git writer from changing
a file between a check and a pathname-based write.

Keep all external writers quiescent for the complete approved operation. The
Windows approval-capable result states this boundary explicitly:

```text
write_boundary.external_writer_quiescence_required: true
write_boundary.external_writer_quiescence_affirmed: true
write_boundary.atomic_file_compare_and_swap: false
write_boundary.checkpointed_change_detection: true
```

True file-handle/descriptor-bound compare-and-swap remains future work.

The receipt is written last. It records commits, target, reviewer, changed pin
roles, source materialization attempt/success/target-integrity evidence,
configured-origin evidence, restart requirement, privacy guards, and
`external_writer_quiescence: {affirmed: true, scope:
complete_project_version_update_transaction}`. Existing v0.1 and v0.2 update
receipts remain readable. An ordinary runtime-policy update writes
`wom-kit/project-version-update-receipt/v0.3` and exactly binds a v0.1
project-runtime receipt. A same-version invalid-runtime repair writes the v0.4
project-update receipt and exactly binds a v0.2 project-runtime receipt. Both
current pairs bind exact policy, dependency supply lock, retained artifact
inventory, installed-payload digest, WOM wheel, runtime, launcher, Python,
transition, and new-process evidence; crossed pairs fail closed. The receipt
contains no local
absolute path, remote URL, raw Git error, or credential value.

Repository attributes require LF bytes for the wrapper and packaged runtime
Python files. Complete commit-tree materialization also handles an existing
Windows mirror: with `core.autocrlf=true`, ordinary Git operations can leave an
unchanged file in its older CRLF materialization. The updater never normalizes
arbitrary working bytes and never trusts status output as proof; it writes only
verified commit blob bytes after approval. A pre-existing, verified CRLF
representation is journaled and restored exactly if rollback returns to that
original snapshot.

`no_change` means more than matching version strings. The mirror must already
be detached at the exact target commit, every recognized pin must match, and
the complete worktree/index/flag and synchronized runtime-resource integrity
gates must pass.

## Failure, Durable Resume, And Rollback

The exact-human durable writer is checkpoint-forward. After its ownership
handoff, a handled component failure or interruption keeps the owned lock,
sealed transaction, completed component checkpoints, and any exact private
recovery preimage. Run the identifier-free public `project-version-update
--resume` path after the blocking condition is removed. It reauthenticates the
started claim, skips verified writers, and continues from the first unverified
component without opening another native approval decision. Only authenticated
terminal commit removes the exact private recovery preimage during transaction
cleanup. Cleanup uncertainty becomes durable finalization attention and does
not erase the proven update result.

The following automatic restoration list applies to the historical/pre-handoff
path and to a separately authorized rollback path, not to a durable component
failure after exact-human ownership has transferred:

- the complete original tracked commit tree, exact original branch or detached
  `HEAD`, stage-zero index, modes, and any verified original EOL bytes;
- the exact original bytes and existence state of every recognized pin;
- only a receipt or lock whose recorded device/inode identity and bytes still
  prove that this transaction owns it; and
- any newly created empty receipt directories when safe.

The original branch is validated with Git's native branch rules, so valid `+`
and Unicode names remain recoverable. WOM reads the full symbolic ref and
accepts only `refs/heads/<branch>`; return code 1 alone is classified as
detached `HEAD`. Any abnormal result or symbolic ref outside that namespace
blocks before fetch or mutation instead of being mistaken for detached state.

These ownership records support checkpointed rollback decisions but do not
make source or pin writes atomic compare-and-swap operations. Rollback checks
the saved source snapshot, configuration digest, pin bytes, and reserved file
identities. Detected drift preserves the owned lock and reports an incomplete
rollback for operator review. In particular, if the bounded Git configuration
digest differs immediately before rollback, source and pin restoration is
skipped, the owned lock remains, and the result is
`failed_rollback_incomplete`.
`KeyboardInterrupt` and other `BaseException` paths follow the same checkpoint
policy. External-writer quiescence is still required; undetected changes inside
a check/write window are not claimed safe.

Fetched refs may remain. They are discovery/version metadata, not the canonical
working tree or user memory. The result distinguishes normal failure from
interruption and complete rollback from incomplete rollback; never claim
success from any failure or interruption state.

## New Process Required

Python cannot replace the already imported WOM-kit module in the middle of this
command. Therefore success is `updated_restart_required`, not simply
`updated`.

Close that invocation, start a new process from the project source mirror, and
run:

```powershell
archive version <project-or-archive-root> --format json
```

Claim the target runtime active only after the new result shows the intended
running version, import origin, source versions, exact head tag, and pins in
agreement.

If the source mirror and pin agree but the global console script still imports
another checkout, v0.3.291 reports
`runtime_alignment.status: project_scoped_bridge_available`. Default output
keeps local paths redacted. On a trusted machine, an explicit
`--no-redact-local-paths` version check can return a structured exact argv that
uses the current Python executable in isolated `-I -S` mode and the verified
mirror's `wom-kit/cli/archive.py`.

That argv is emitted only after local release-integrity checks: real paths, a
conventional project-local `.git` directory, no alternates or grafts, exact Git
root, raw worktree/index/flag agreement, the complete tracked Python and
synchronized runtime-resource sets, a closed import tree, the fixed origin key,
the exact annotated version tag at `HEAD`, tagged source-version agreement, and
local `origin/main` ancestry. The bridge is bound to the expected commit, tag,
wrapper blob, and resource blobs. Its in-memory bootstrap permits only the
`version` command and repeats the object and import-location checks before
dispatch. `-S` prevents `site` initialization, executable `.pth` lines, and
`sitecustomize` before bootstrap. Only after object verification and in-memory
wrapper compilation does the bootstrap append the standard `purelib` and
`platlib` paths reported by stdlib `sysconfig`, without asking `site.py` to
process them. The check performs no fetch, reads no origin URL value, and does
not prove a cryptographic signature or current remote freshness.

Runtime inventories stream `os.scandir` entries under fixed entry/byte caps
instead of materializing an unbounded directory listing. Before any updater
mutation, even an ignored, noncolliding extra top-level entry under
`wom-kit/src` is a shadow blocker.

The bridge never adds `wom-kit/src` itself to `sys.path`. It removes every
project-path alias already present and installs an exact-object-ID custom
finder only for `wom_kit` modules. A top-level shadow such as `yaml` or
`sqlite3` inserted after the integrity gate therefore cannot execute through
the project source root.

The synchronized-resource gate uses exactly three Git children regardless of
resource count: a bounded full-tree inventory at the bound commit, one strict
unique-object `cat-file --batch`, and a bounded full stage-zero index
inventory. It avoids both per-resource process multiplication and long
path-argument lists while preserving exact object framing, OID rehash,
tree/index modes, manifest size/hash, source/package parity, bounded real-file
bytes, and packaged-resource closed-world checks.

v0.3.314 applies the same bounded-process principle to the complete target
tree. Each tree is enumerated once and its unique blobs are materialized
through one strict `git cat-file --batch` stream rather than one child per
path. The controlled four-tree reproduction used eight Git processes instead
of 11,184 and completed the four loads in 2.538 seconds. Object id/type/size,
rehash, framing, per-file and total limits, and trailing-byte checks remain
fail closed. The timing is local benchmark evidence, not a guarantee for every
machine or repository.

The argv is a one-invocation bridge to the project-pinned source. It does not
replace `archive` on `PATH`, update a global Python environment, infer whether
pip/uv/pipx/editable installation owns the command, or update the separate
runtime Agent Skill. A provenance-aware global installer lifecycle remains a
separate feature.

## Bootstrap Boundary

The updater first ships in v0.3.215. An older installation cannot run a command
it does not yet contain. It needs one final update through its existing/manual
verified procedure to reach v0.3.215. Use `project-version-update` for releases
after that bootstrap.
