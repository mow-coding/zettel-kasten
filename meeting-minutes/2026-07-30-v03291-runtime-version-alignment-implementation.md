# v0.3.291 runtime version alignment implementation record

- Date: 2026-07-30
- Branch: `codex/v0.3.291-runtime-version-alignment`
- Starting point: `b938abaedb8f705f8f58e42c95f54a73cad9352f`
- Status: local checkpoint verification in progress; release-order rebase
  remains pending

## User intent

The user asked the WOM development team to keep working through the beta
tester backlog carefully, release improvements in a trustworthy sequence, and
include beta letter 104 rather than stopping after the previously queued work.

## Evidence from beta letter 104

The read-only audit found three different version surfaces:

- the beta project's source mirror and pin are v0.3.286;
- the `archive.exe` selected by `PATH` belongs to the machine's Python 3.12
  Scripts directory;
- that interpreter's editable-install pointer imports the main development
  checkout, which reports v0.3.282.

`project-version-update` correctly updates the project mirror, pin, and
receipt, but does not and must not silently mutate the global Python
installation. Runtime Skill lifecycle commands manage AI guidance, not the
Python CLI. The resulting version skew is therefore real, while a blind
self-update would cross an unowned installer boundary.

The audit also found two stale runtime Skill examples:

- one referenced nonexistent `wom-kit/archive.py` instead of
  `wom-kit/cli/archive.py`;
- one omitted the required `--target` argument from
  `project-version-update`.

No WOM command was executed in the beta archive and no beta file was changed.

## Plan

1. Extend the existing read-only version result with explicit runtime
   alignment states and bounded safe actions.
2. Return an exact project-scoped bridge argv only after self-consistent mirror
   and pin verification, local Git release-integrity verification, and explicit
   local-path disclosure.
3. Preserve default path redaction and existing mismatch exit codes.
4. State explicitly that PATH, the Python environment, and runtime Skill
   installation remain unchanged.
5. Correct the shipped update examples and document the Python-tool/runtime
   Skill lifecycle boundary.
6. Add focused redaction, bridge, fail-closed, aligned-state, text-output, and
   documentation regressions.
7. Rebase onto the exact public v0.3.290 predecessor, then run the complete
   source and clean-wheel release lifecycle before publication.

## Parallel ownership

- Production: `archive_services.py`, `archive_cli.py`
- Regression tests: `test_cli.py`
- Supervisor: docs, runtime Skill references, capability matrix, version and
  release surfaces, resource synchronization, integration review, commits,
  rebases, and release

Workers are not authorized to commit, push, tag, publish, or touch the beta
archive.

## Implementation evidence

- `archive version` now returns a bounded `runtime_alignment` object with
  `not_inspected`, `aligned`, `project_source_update_required`, and
  `project_scoped_bridge_available` states plus deterministic
  `next_safe_actions`.
- The exact one-invocation bridge argv is path-redacted by default and appears
  only under explicit `--no-redact-local-paths`; it invokes Python in isolated
  `-I -S` mode.
- Executable argv requires `runtime_alignment.integrity.verified: true`.
  Integrity evidence checks real in-project path components, the exact Git
  worktree root, a conventional real project-local `.git` directory, no
  linked-worktree pointer, alternate object store, graft, symlink, junction,
  or reparse route, the actual pin remaining untracked, the complete runtime
  Python and synchronized-resource sets at `HEAD`, safe index flags,
  index/`HEAD` agreement, exact bounded raw worktree bytes, a closed import
  tree, a valid `HEAD`, the exact annotated version tag at that commit,
  matching package/pyproject/root-shim versions inside the tag, and local
  reachability from `origin/main`.
- The snapshot does not run `git status`. It compares `ls-tree`, the stage-zero
  index, `ls-files -v` flags, bounded raw worktree bytes, and untracked paths
  directly, with hooks, fsmonitor, attributes, excludes, replacement objects,
  and lazy fetch disabled for local inspection.
- The origin probe checks only the fixed `remote.origin.url` key name. It
  never reads the configured URL value.
- The bridge argv binds the expected commit, annotated tag, wrapper object, and
  runtime-resource objects. Its in-memory bootstrap executes the verified
  wrapper blob, rejects preloaded external `wom_kit`, verifies the imported
  package and CLI locations, and permits only the read-only `version` command.
  It purges project aliases from `sys.path`, never inserts `wom-kit/src`, and
  installs an exact-object-ID finder only for `wom_kit`, so post-gate
  top-level dependency shadows cannot execute from the project tree.
  Repository attributes keep all verified runtime Python source LF-stable
  across Windows and POSIX checkouts.
- `-S` prevents `site` initialization, executable `.pth` lines, and
  `sitecustomize` before the bootstrap runs. Only after Git-object verification
  and in-memory wrapper compilation does it append stdlib `sysconfig`'s
  `purelib` and `platlib` paths, without invoking `site.py` processing.
- A present mirror that fails any integrity check returns
  `project_source_update_required`, exits nonzero, and never emits
  `bridge_argv`.
- The evidence explicitly records that no network or origin contact occurred
  and that neither a cryptographic tag signature nor current remote freshness
  was verified.
- Text output renders alignment status, reason, integrity state, bridge
  availability, safe actions, and unchanged installation boundaries.
- Runtime Skill examples now use `wom-kit/cli/archive.py`, include the required
  project-update target, and require the verified integrity field before using
  a bridge.
- Version, release note, decision log, changelog, English/Korean install and
  upgrade guides, README surfaces, capability matrix, and deterministic
  packaged resources were advanced to v0.3.291.

## Independent Review Findings And Corrections

The first independent review found three Medium release blockers:

1. Status output could hide an edited wrapper or runtime module through
   `assume-unchanged` or `skip-worktree`. Integrity now enumerates every
   tracked runtime Python file, rejects unsafe index flags and index/`HEAD`
   divergence, and directly compares worktree bytes with the tagged `HEAD`
   blobs.
2. The proposed argv did not isolate environment search paths, while the
   wrapper inserted the selected source only when absent. A hostile
   `PYTHONPATH` could therefore win. The argv first moved to `-I`, then the
   final bootstrap hardening added `-S`; the final wrapper instead removes
   project aliases from `sys.path`, loads only `wom_kit` through exact object
   IDs, and verifies package/CLI import locations.
3. The origin check used `git config --get remote.origin.url`, which reads a
   possibly credential-bearing URL while evidence claimed no secret value was
   read. It now requests only the fixed matching key name and never reads the
   URL value.

The supervisor then found two cross-platform/import follow-ups before the
candidate returned to verification:

4. Raw blob equality would reject ordinary Windows `core.autocrlf=true`
   checkouts. `.gitattributes` now materializes the wrapper and every packaged
   runtime Python source with LF on all platforms, preserving raw-byte
   equality rather than normalizing untrusted bytes at runtime.
5. Correct `.py` bytes alone did not exclude ignored `__pycache__`, bytecode,
   native extensions, or shadow source. The integrity gate and wrapper now
   enforce a closed source tree and create no bytecode cache during bridge
   execution.

The completed import gate also uses a source-only loader that rechecks each
module's exact Git blob object ID on the bytes passed to compilation. This
closes the gap between an initial tree scan and the actual imported bytes.

## Windows Transition And Updater Correction

A fresh v0.3.291 clone with the new `.gitattributes` materializes verified
Python sources as LF. A separate transition fixture proved that this is not
enough for an existing Windows `core.autocrlf=true` mirror: an ordinary legacy
checkout of the new tag can leave an unchanged `.py` file in its older CRLF
form.

The approval-gated project updater was therefore extended within its existing
source/pin/receipt write boundary:

- read the complete tracked target commit tree, path/mode/object-ID set, and
  every bounded blob;
- validate cross-platform path safety before mutation, including `.git` and
  reserved-name aliases, Unicode/case collisions, length limits, real path
  components, and safe file-to-directory or directory-to-file transitions;
- manually remove only disappearing tracked paths, create needed directories,
  write exact target blobs, restore executable modes, rebuild the stage-zero
  index, and detach `HEAD`, without `git checkout`;
- directly recheck the raw worktree, index, flags, closed tree, versions, and
  all synchronized runtime resources before any pin or receipt success;
- record attempted/succeeded/target-integrity evidence under
  `runtime_source_materialization` in the
  `wom-kit/project-version-update-receipt/v0.2` schema-backed receipt while
  preserving the v0.1 schema unchanged for existing receipts;
- restore the complete original tracked tree, branch/detached state, index,
  modes, and verified original EOL bytes before declaring rollback success;
- return `no_change` only for an already detached exact target whose pins,
  complete tracked tree, and synchronized runtime resources are all verified.

## Transaction And Git Hardening

Later adversarial review expanded the source-integrity correction into a
complete transaction boundary:

- Local Git commands remove ambient `GIT_*` variables except the small approved
  transport set used only for fetch. Local inspection disables optional locks,
  replacement objects, lazy fetch, fsmonitor, hooks, attributes, and global
  excludes.
- The updater rejects non-project-local Git metadata, linked worktrees,
  alternates, grafts, symlinks, junctions, and reparse routes.
- It does not call `git status`, because status may run configured clean or
  process filters. A complete raw worktree/index/flag/untracked snapshot is
  used for preflight, checkpoint drift detection, terminal verification, and
  rollback decisions.
- The trust digest binds effective Git configuration plus exactly
  `GIT_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_SSH`, and `GIT_SSH_COMMAND`.
  Selected `git`, `PATH`, `HTTP_PROXY`, `HTTPS_PROXY`, `SSL_CERT_FILE`,
  `CURL_CA_BUNDLE`, `SSH_AUTH_SOCK`, `HOME`, and other non-`GIT_*`
  toolchain/transport environment remain unbound trusted-stable prerequisites.
- Pin and source bytes are snapshotted and compared at checkpoints. This does
  not turn their pathname-based writes into atomic compare-and-swap.
- The update lock and receipt use `O_EXCL` no-overwrite creation. Their
  device/inode identity and exact bytes form ownership journals. A colliding
  receipt name advances to a new suffix rather than replacing an existing
  receipt.
- `BaseException`, including `KeyboardInterrupt`, enters the same owned
  rollback path. When source, pin, lock, receipt, or config ownership becomes
  uncertain at a checkpoint, WOM-kit preserves the lock and reports incomplete
  rollback. If the configuration digest drifts immediately before rollback,
  restoration is skipped and the owned lock remains.
- The final directory-replacement review established a platform boundary.
  Windows opens and holds the real project root, metadata root, every existing
  source/`.git` directory, pin/lock parents, and existing receipt directories
  without `FILE_SHARE_DELETE`. These handles prevent rename, deletion, and
  junction replacement while pathname-based Git and complete-tree work runs.
- A missing receipt parent and `version-updates` root are created and held
  sequentially under an already held parent. The exclusive receipt helper
  refuses to write unless the final receipts root is held.
- POSIX directory descriptors confirm identity but do not prevent pathname
  rename. Because Git and the full-tree writer are not descriptor-relative end
  to end, POSIX `--approve` is blocked. POSIX dry-run remains useful and
  returns `preview_only_platform_unsupported` plus
  `write_boundary.approval_platform_supported: false`.
- The review explicitly rejected a stronger concurrency claim. Windows
  directory rename/reparse stability plus checkpoints do not prevent external
  file-content edits between a check and write. The complete approval therefore
  requires editor/sync/backup/other-Git-writer quiescence. After dry-run, every
  Windows approval requires the reviewer and exact
  `--affirm-external-writers-quiescent` flag, exposed as
  `external_writer_quiescence_required: true`,
  `external_writer_quiescence_affirmed: true`,
  `atomic_file_compare_and_swap: false`, and
  `checkpointed_change_detection: true`. The v0.2 receipt records
  `external_writer_quiescence: {affirmed: true, scope:
  complete_project_version_update_transaction}`. True
  file-handle/descriptor-bound CAS is a follow-up.
- Runtime tree and metadata walks stream `os.scandir` entries under caps. An
  ignored, noncolliding `wom-kit/src` top-level shadow is rejected before any
  updater mutation.
- The bridge is explicitly `version_command_only: true` and records
  `expected_runtime_resources_bound: true` only when every gate is verified.
- The final privacy review found that conventional local Git tag names and
  malformed pin/source/pyproject version strings could still be copied into
  shareable version results. The service now projects only exact stable
  versions, returns invalid metadata as null/fail-closed evidence, filters
  both head and latest-tag fields, and re-filters `runtime_alignment` inputs.
  Focused regressions use private marker payloads in all three metadata files,
  the running checkout pyproject, and a `v*` non-release local tag, then require
  null fields and complete marker absence from stdout, stderr, and serialized
  JSON.
- Rollback originally accepted a narrower ASCII branch regex than Git itself.
  A valid `feature+rollback` or Unicode branch could therefore pass preflight
  but become impossible to reattach after a later failure. Recovery now uses
  `git check-ref-format --branch`, binds the exact branch ref to the saved
  commit before mutation and before reattachment, and classifies full
  `symbolic-ref --quiet HEAD` results explicitly. Only return code 1 is
  detached; abnormal, malformed, or non-`refs/heads/*` state blocks before
  fetch or write. Focused failure injection proved exact branch, commit,
  index, worktree, EOL, and pin restoration for `+`, Unicode, and detached
  states; abnormal symbolic state proved no-fetch/no-write.
- The bridge's first all-resource implementation launched roughly eight Git
  children per manifest row, approximately 828 processes for 103 resources.
  A one-resource bridge approached the existing 30-second subprocess limit,
  making the otherwise safe route operationally unusable. The wrapper now
  performs one bounded full-tree inventory, one strict unique-OID
  `cat-file --batch`, and one full stage-zero index inventory. Batch parsing
  rejects malformed, truncated, reordered, wrong-type, wrong-size,
  wrong-hash, missing-separator, extra-response, and trailing-byte results.
  Independent cold-clone evidence on the real 102-row v0.3.290 manifest used
  exactly three Git children and completed the resource verifier in 2.233
  seconds. Repeated complete inner bridge runs completed in 21.525 to 22.107
  seconds under the unchanged 30-second limit; the clean-swap canary and
  concealed-resource regressions also passed.

The local subset schema validator does not globally enforce
`additionalProperties`. Enabling that keyword would change the validation
behavior of many existing receipt schemas, so v0.3.291 deliberately limits
the new receipt contract to required fields, types, conditional
attempted/succeeded truth, and target-integrity `true`. General unknown-field
enforcement remains a separately scoped compatibility task.

Each finding was converted into a focused regression before acceptance.

## Final Public And Operator Guidance Alignment

- English and Korean root README/upgrade guidance now describe the same final
  `-I -S`, exact-object-ID finder, no-source-root-on-`sys.path`, streaming-scan,
  Windows-only approval, checkpoint/non-CAS, and exact Git-config/env boundary.
- Every literal current `project-version-update --approve` example includes
  the reviewer and `--affirm-external-writers-quiescent`, after instructing the
  operator to pause editors, sync/backup clients, and other Git writers for the
  complete transaction.
- Public results and v0.2 receipt guidance names required and affirmed
  quiescence plus
  `external_writer_quiescence: {affirmed: true, scope:
  complete_project_version_update_transaction}`.
- Personal, family, company, and runtime Agent Skill source templates carry the
  same approval boundary. Their packaged resource mirrors and release-note
  mirror must be regenerated by the deterministic package-resource sync before
  final release verification.

## Verification evidence

Completed on the local stacked checkpoint so far:

- 14 runtime-alignment methods passed; 2 additional Windows tests skipped only
  because this host cannot create the required symlink fixtures;
- 13 project-version-update regressions passed;
- 4 new CRLF transition, same-target repair, exact-source rollback, and
  materialization-receipt truth regressions passed;
- the packaged receipt schema and real CRLF success receipt validation passed;
- the source-only bridge loader and receipt-write rollback false-success
  regressions passed independently;
- focused coverage includes redacted and opt-in output, exact argv, aligned
  state, no-project compatibility, inconsistent metadata, non-Git and dirty
  mirrors, tracked pin, wrapper drift, wrong/lightweight/not-at-HEAD tags,
  tagged root-shim mismatch, missing origin, missing/unreachable
  `origin/main`, and symlink/reparse paths when supported;
- every integrity regression asserts no network/origin contact and no
  executable bridge on failure;
- complete documentation contract suite: 145 tests passed, 0 failures;
- deterministic package-resource synchronization: 103 files for v0.3.291;
- production memory-only compilation, manual local bridge/refusal matrix,
  Windows exact-blob transition, approved local-origin update/receipt, and
  immediate verified `no_change` replay: passed;
- worker `git diff --check`: passed apart from expected Windows line-ending
  notices.

The later complete-tree, no-status, ownership-journal, interrupt, Git-metadata,
Windows directory-hold/POSIX preview-only boundary, bounded-config checkpoints,
explicit external-writer quiescence/non-atomic
file-CAS boundary, streaming scan/shadow preflight, exact-OID finder,
`-I -S` bootstrap, and 103-resource changes remain part of the current focused
verification pass. They are not represented by the earlier test counts above.

The final focused pass then completed with:

- project-update regressions: 40 tests and 31 subtests passed, with no skips
  or failures;
- version regressions: 29 tests and 85 subtests passed, with three
  environment-dependent skips and no failures;
- documentation contracts: 145 tests and 3,847 subtests passed;
- release readiness: 4 of 4 checks passed;
- deterministic package resources: 103 files synchronized;
- source/package v0.1 and v0.2 receipt schemas: valid JSON and byte-identical
  pairs; and
- Python compilation and focused bridge batching, concealment, rollback, and
  resource-integrity checks: passed.

The first final version run exposed six stale test cases. The new complete
no-status Git snapshot correctly rejected changed execution bytes and unsafe
index flags first as `project_git_worktree_dirty`, before the narrower
tracked-Python recheck. The tests still mocked `git status`, which the current
implementation deliberately does not use. Production ordering stayed
unchanged. The regressions now preserve a clean first snapshot, introduce the
execution-source change afterward, and prove that the independent narrow
recheck returns `project_tracked_python_bytes_mismatch` or
`project_tracked_python_index_flags_unsafe`. The six corrected cases and the
complete version subset pass.

The final documentation gate also found ten missing literal contract anchors
in the version truth, capability matrix, and project update pages. Those
anchors now state the read-only/no-secret boundary, logical pin and mirror
fields, runtime integrity evidence, restart status, bootstrap boundary, and
incomplete-rollback status explicitly. The complete documentation contract
suite passes after the correction.

Still required after independent review and the exact v0.3.290 rebase:

- complete source suite;
- release-readiness and resource gates on the final tree;
- exact merged-commit clean wheel;
- PR/main/tag CI, public GitHub Release, unauthenticated artifact download,
  digest, and fresh-install verification.

## Release-order boundary

This branch starts from the local v0.3.290 checkpoint. It cannot be published
until v0.3.287 through v0.3.290 are public and this candidate is rebased onto
their exact final chain.
