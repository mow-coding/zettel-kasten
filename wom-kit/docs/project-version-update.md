# Project Version Update

Status: implemented in v0.3.215; bounded Git batch and operation observation in v0.3.314

## Plain-Language Purpose

A WOM project can have three version states that drift apart:

1. the WOM-kit code currently loaded by Python;
2. the project-local code copy at `.zettel-kasten/source`;
3. one or more small files that remember the intended version, called pins.

Previously, a human had to receive update files with Git, move the local code to
the release tag, and edit the pin by hand. `project-version-update` turns those
steps into one reviewed transaction with explicit evidence and rollback.

It updates the tool around the archive. It does not rewrite the user's zets,
objets, manifests, source material, or external database.

## Safe Workflow

First preview. This performs no fetch and writes nothing:

```powershell
archive project-version-update <project-or-archive-root> `
  --target vX.Y.Z `
  --dry-run `
  --progress `
  --output .zettel-kasten/diagnostics/update-preview-20260811-001.json `
  --format json
```

The target may not exist locally yet. In that case
Windows may report `ready_to_fetch_on_approve`, which means only that local
preconditions passed and the approved command will fetch and verify the release
before materializing the target commit tree. POSIX instead reports the
preview-only platform status described below.

After a human reviews the preview, pause editors, sync clients, backup tools,
and every other Git writer for the complete transaction. While they remain
paused, run approval on Windows with the required affirmation:

```powershell
archive project-version-update <project-or-archive-root> `
  --target vX.Y.Z `
  --approve `
  --reviewed-by <actor> `
  --affirm-external-writers-quiescent `
  --progress `
  --output .zettel-kasten/diagnostics/update-apply-20260811-001.json `
  --format json
```

These project-local output paths opt into v0.3.314 operation observation. When
the command is started from an archive root, use a fresh
`.wom-scratch/diagnostics/*.json` output instead. Stderr prints an opaque
`operation_ref` before the long work. If the caller times out, do not start a
duplicate updater; use `operation-control` status, bounded wait, or recovery
guidance with the exact root and reference. Cancel and resume are unsupported,
and completion still requires a fresh-process `archive version` check.

## Ignored-Entry Collision Inspection And Preservation

The ordinary preflight and the approved updater use the same bounded
materialization planner whenever the exact target commit is locally available.
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

Approval replays the unchanged plan and requires a reviewer plus whole-operation
writer quiescence:

```powershell
archive project-version-update-collision <project-or-archive-root> `
  --target vX.Y.Z `
  --entry-ref update-entry:0001 `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --action preserve-relocate `
  --approve `
  --reviewed-by <actor> `
  --affirm-external-writers-quiescent `
  --format json
```

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

After preservation, run a new `project-version-update --dry-run`. Approval of
the preservation action grants no authority to approve the updater. The
collision surface is CLI-only and has no aliases or MCP method.

## Platform Boundary

In v0.3.291, the approved write transaction is supported only on Windows.
Windows directory handles are opened without `FILE_SHARE_DELETE`, so every
held write-path directory behind the project root, `.zettel-kasten/source`,
its `.git` tree, pins, lock, and receipts cannot be renamed, deleted, or
replaced by a junction while the transaction resolves child paths.

POSIX can still run the useful read-only dry-run. Its result is
`status: preview_only_platform_unsupported`, includes a warning, and reports
`write_boundary.approval_platform_supported: false`. Running `--approve` on
POSIX is a blocker and writes nothing. An open POSIX directory descriptor does
not prevent another process from renaming that pathname, and the Git plus
complete-tree update is not yet descriptor-relative end to end.

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
9. rechecks checkpoint snapshots, then writes the canonical project pin and
   any recognized existing mirror or legacy project pin;
10. creates and immediately holds a missing `receipts/` parent and
   `version-updates/` root one level at a time, validates the v0.2 receipt
   document, and creates one new receipt under
   `.zettel-kasten/receipts/version-updates/` with `O_EXCL`, never replacing an
   existing path; the receipt writer refuses to run unless that root is
   already held; and
11. rechecks the owned terminal state before removing only the lock reserved by
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
complete_project_version_update_transaction}`. v0.3.291 writes
`wom-kit/project-version-update-receipt/v0.2`; the existing v0.1 schema remains
available and compatible for old receipts. The receipt contains no local
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

## Failure And Rollback

If anything fails or is interrupted after mutation starts, WOM-kit attempts to
restore:

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
