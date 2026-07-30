# Decision Log — v0.3.291 Runtime Version Alignment

Date: 2026-07-30

## Context

A project can have a correct source mirror and version pin while the
`archive` console script selected by `PATH` imports another Python checkout.
The existing version command diagnoses that mismatch, and the project updater
correctly owns only the project mirror, pins, and update receipt.

Automatically repairing the global command would require installer provenance,
environment ownership, rollback, and restart rules that WOM does not yet have.
Runtime Agent Skill lifecycle is separate again and must not be confused with
Python CLI installation.

## Decision

Extend the read-only version report with an explicit runtime-alignment
decision.

- A self-consistent project mirror and pin that match the running import are
  aligned.
- A self-consistent project mirror and pin that differ from the running import
  may expose a project-scoped bridge.
- Shareable version results accept only exact stable version labels. Invalid
  project pin, source, pyproject, running-checkout pyproject, and local Git tag
  payloads remain internal invalid evidence and are projected as `null`;
  only exact `v<major>.<minor>.<patch>` tags can populate head/latest fields.
- The exact bridge argv uses isolated Python `-I -S` mode and is returned only
  after version, real-path, project-local Git metadata, closed runtime-source
  and synchronized-resource trees, safe-index-flag, exact index/`HEAD`, raw
  source-byte, exact annotated-tag, tagged-source, fixed origin-key, and local
  origin-main ancestry checks, and only when local paths were explicitly
  unredacted and `runtime_alignment.integrity.verified` is `true`.
- The bridge is bound to the expected commit, annotated tag, wrapper blob, and
  all runtime-resource blobs. Its in-memory bootstrap executes the verified
  wrapper blob, rejects preloaded external package state, verifies the imported
  package/CLI locations, and permits only the read-only `version` command.
- Runtime-resource verification is constant-process: one bounded full-tree
  inventory, one strict unique-OID `cat-file --batch`, and one bounded full
  stage-zero index inventory. It reuses verified batch bytes for exact
  tree/index/worktree, source/package, byte-count, SHA-256, and Git object-ID
  checks instead of spawning per-resource Git commands.
- The bridge purges project aliases from `sys.path`, never inserts
  `wom-kit/src`, and installs an exact-object-ID finder only for `wom_kit`.
  Post-gate top-level dependency shadows such as `yaml` or `sqlite3` therefore
  cannot execute from the project source root.
- `-S` prevents `site` initialization, executable `.pth` lines, and
  `sitecustomize` before bootstrap. After project-object verification and
  in-memory wrapper compilation, only stdlib `sysconfig`'s `purelib` and
  `platlib` paths are appended without `site.py` processing.
- The Git boundary requires a conventional, real project-local `.git`
  directory and rejects linked worktrees, alternates, grafts, symlinks,
  junctions, and reparse routes. Replacement objects and lazy fetch are
  disabled.
- Integrity snapshots compare the commit tree, stage-zero index, index flags,
  bounded raw worktree bytes, and untracked paths directly. They do not use
  `git status`, hooks, fsmonitor, or repository-configured filters.
- Runtime/source metadata scans stream `os.scandir` under fixed caps. An
  ignored, noncolliding top-level shadow under `wom-kit/src` blocks before
  project-update mutation.
- Repository attributes require LF for every verified runtime Python file.
  Because an existing Windows `core.autocrlf=true` mirror can retain CRLF on
  unchanged files, approved `project-version-update` manually materializes the
  complete tracked target commit tree from exact bounded blobs. It applies
  strict cross-platform path rules, verifies safe file/directory transitions,
  rebuilds the index, and detaches `HEAD` without `git checkout`.
- The update receipt records materialization attempt, success, and verified
  target integrity in receipt schema v0.2; the v0.1 schema remains compatible
  for existing receipts. `no_change` requires exact target, pin, complete
  tracked-tree, and all 103 synchronized-resource integrity agreement.
- Original-branch recovery uses Git-native branch validation rather than an
  application ASCII subset. Full symbolic refs must be exact
  `refs/heads/<branch>` values; only Git return code 1 is detached `HEAD`.
  Abnormal, malformed, or non-head symbolic state blocks before fetch or
  mutation, while valid `+` and Unicode branch names restore exactly.
- A non-revealing digest checkpoints effective Git configuration plus exactly
  `GIT_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_SSH`, and `GIT_SSH_COMMAND`.
  The selected Git executable, `PATH`, `HTTP_PROXY`, `HTTPS_PROXY`,
  `SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `SSH_AUTH_SOCK`, `HOME`, and other
  non-`GIT_*` toolchain/transport environment are unbound trusted-stable
  prerequisites.
- Lock and receipt paths use exclusive `O_EXCL` creation and recorded file
  identities. Source, pin, lock, receipt, and config snapshots detect drift at
  checkpoints. They are not atomic file CAS and do not provide a general
  never-clobber guarantee.
- External editors, sync/backup tools, and other Git writers must remain
  quiescent through the complete approval. After dry-run, every Windows
  approval must include the reviewer plus
  `--affirm-external-writers-quiescent`. Windows results report
  `external_writer_quiescence_required: true`,
  `external_writer_quiescence_affirmed: true`,
  `atomic_file_compare_and_swap: false`, and
  `checkpointed_change_detection: true`; the v0.2 receipt records
  `external_writer_quiescence: {affirmed: true, scope:
  complete_project_version_update_transaction}`. True handle/descriptor-bound
  file CAS remains future work.
- Detected pre-rollback configuration-digest drift skips source/pin restore,
  preserves the owned lock, and returns incomplete rollback.
- Approved project updates are Windows-only in v0.3.291. Held directory handles
  omit `FILE_SHARE_DELETE` across the project, source/`.git`, pin, lock, and
  receipt path chains, preventing rename, deletion, or junction replacement.
  Missing receipt parents are created and held one level at a time, and the
  receipt writer requires the receipt root to be held.
- POSIX dry-run remains a read-only
  `preview_only_platform_unsupported` preview with
  `write_boundary.approval_platform_supported: false`; POSIX approval fails
  closed. An open POSIX directory descriptor does not pin a pathname against
  rename, and the Git/complete-tree transaction is not descriptor-relative end
  to end.
- The integrity check is local and uses no network. It checks only whether
  the fixed origin configuration key exists and never reads its URL value. It
  does not claim a cryptographic signature or current remote freshness.
- Incomplete, malformed, or inconsistent mirror evidence provides no
  executable bridge.
- The bridge runs the verified project source for one invocation; it does not
  replace the global command, mutate a Python environment, infer installer
  provenance, or install the runtime Skill.
- Public and runtime-Skill guidance must use the real
  `wom-kit/cli/archive.py` wrapper and include the required target in project
  update examples.

Do not add a global self-update or run pip, uv, pipx, Git fetch, project
updates, or Skill lifecycle writes from the version inspection.

## Consequences

- Operators and AI runtimes can distinguish “project files are current” from
  “the global command imports those files.”
- A verified project source can be used immediately without falsely claiming
  that machine-wide installation was repaired.
- Default output remains safe for sharing because executable local paths stay
  redacted and arbitrary local version/tag payloads are not echoed.
- A dirty, non-Git, non-local-metadata, alternate/grafted, symlinked, untagged,
  index-hidden, byte-divergent, resource-divergent, or import-shadowed mirror
  cannot produce an executable bridge.
- LF-stable repository attributes keep the raw-byte contract usable on
  Windows and POSIX release checkouts without normalizing untrusted bytes at
  runtime. Existing Windows mirrors transition through the explicit approved
  updater and its receipt rather than through a silent runtime rewrite.
- Manual complete-tree materialization makes update behavior independent of
  checkout hooks and filters, while checkpoint evidence supports bounded
  rollback decisions under the explicit external-writer quiescence rule.
- The project updater remains usable for POSIX planning, but operators must
  perform the approved transaction from Windows until descriptor-relative
  Git/full-tree support exists.
- Global Python tool replacement remains a separate future lifecycle with
  provenance and rollback requirements.
- Runtime Agent Skill installation remains explicitly independent.

Implementation detail and verification evidence are recorded in
`meeting-minutes/2026-07-30-v03291-runtime-version-alignment-implementation.md`.

## Audit Correction — 2026-07-31

An independent follow-up audit showed that the earlier public-guidance bullet
above was too broad. `wom-kit/cli/archive.py` is no longer an ordinary
source-development fallback after the v0.3.291 closed-tree bridge gate. A
normal test or editor import can create `__pycache__`, and ordinary source
changes are also expected during development; both correctly make the direct
wrapper refuse.

The corrected decision is append-only:

- active source development uses `PYTHONPATH=src` plus
  `python -m wom_kit.archive_cli`;
- the direct wrapper is reserved for the exact verified `bridge_argv` or an
  explicit pristine-checkout recovery attempt;
- packaged runtime guidance, English/Korean quick verification, and current
  CLI guidance must preserve that distinction; and
- direct-wrapper refusals expose one of six documented stable
  `WOM_BRIDGE_*` codes followed by the fixed content-free
  `WOM_BRIDGE_RECOVERY_DOC` pointer.

This correction does not weaken the bridge integrity gate or rewrite the
original decision record. It narrows the supported launcher contract so the
code, tests, source documentation, and installed package resources agree.

### Defensive enforcement correction

The same follow-up audit showed that the Windows directory-hold
implementation did not yet enforce the intended pathname-stability claim.
The corrected implementation:

- opens directories with list-directory plus attribute access while still
  omitting delete sharing;
- binds each held handle to its volume/file identity and revalidates the
  current pathname before use;
- rechecks containment, real path components, held parent identity, and
  regular-file type immediately before every tracked unlink;
- purges incomplete handle/identity cache state and closes any surviving
  handle fail-closed; and
- parses all five NUL-delimited Git inventories with strict framing, while
  deriving CRLF eligibility from the exact `ls-files --eol` tracked set rather
  than a filename allowlist.

The preserved local concurrency regression changed from outside-tree deletion
to blocked directory replacement with the outside file unchanged. This is an
enforcement correction to the original Windows-only decision, not an expansion
of the approved write boundary or a claim of atomic file compare-and-swap.
