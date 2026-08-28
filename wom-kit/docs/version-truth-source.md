# WOM-kit Version Truth Source

Status: v0.4.13 exact setup evidence and create-only object-storage preservation

Current checkpoint: Status: v0.4.13 exact setup and remote preservation truth

Previous checkpoint: Status: v0.4.12 indexed-link and same-generation delta-or-dirty truth

Previous checkpoint: Status: v0.4.11 runtime, byte-evidence, and operator truth

Previous checkpoint: Status: v0.4.10 authenticated batch intake and capture

Previous checkpoint: Status: v0.4.9 single-file intake and truthful doctor operability

Previous checkpoint: Status: v0.4.8 interruption-safe integrity recovery

Previous checkpoint: Status: v0.4.7 exact local capture and field-scoped recovery

Previous checkpoint: Status: v0.4.6 R2 bytes preservation plus formal adoption

Previous checkpoint: Status: v0.4.5 Common Controls v6 activation plus byte-packed Task Dialog ABI

Previous checkpoint: Status: v0.4.4 machine-verified human decision plus exact project runtime

Previous checkpoint: Status: v0.4.3 PATH shadow diagnosis plus exact-human project update

Previous checkpoint: Status: v0.4.2 bounded Git plan/reconciliation with no writer

Previous checkpoint: Status: v0.4.1 one exact link apply plus content-free operator recovery

Previous checkpoint: Status: v0.4.0 exact human approval and operator-friction checkpoint

Previous checkpoint: Status: v0.3.320 one-use credential capability broker

Previous checkpoint: Status: v0.3.319 native credential popup and causal-evidence corrections

Previous checkpoint: Status: v0.3.291 read-only runtime alignment plus approval-gated project update

WOM-kit has several places where a human or AI might see a version-like value:
the installed CLI, the source checkout, and a project-local pin left by a setup
or runtime workflow. This page defines the safe order for checking them.

## Current Public Tool

The v0.4.13 URL is a conditional release-artifact contract. Use it only after
the matching public GitHub Release exists and lists the exact wheel:

```powershell
py -m venv .wom-bootstrap-v0413
& .\.wom-bootstrap-v0413\Scripts\python.exe -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.13/wom_kit-0.4.13-py3-none-any.whl"
& .\.wom-bootstrap-v0413\Scripts\archive.exe --version
```

Require exactly `archive 0.4.13` from a new process. The installed runtime adds
exact-first object-storage setup evidence and conditional create-only emergency
preservation with durable three-state receipts and manifest-bound resume.
A bootstrap install alone changes no archive, remote ref, project-local source
mirror, pin, shared PATH tool, other project, or provider. Project update is a
separate native exact-human workflow that creates and activates the
project-local runtime with its own receipt. Provider access and byte
preservation require another explicit client-authorized operation. WOM verifies
counts, hashes, setup identity, drift, provider evidence, checkpoints, and
receipts; the person does not count or compare technical values. See
[ExactOperationManifest v1](exact-operation-manifest-v1.md), the
[object-storage execution contract](object-storage-adapter-execution-contract.md),
and the [v0.4.13 release note](releases/v0.4.13.md).

## Canonical Checks

Use these commands before deciding which kit is current:

```powershell
archive --version
archive version --format json
archive version <project-or-archive-root> --format json
archive version <project-or-archive-root> --progress --format json
archive runtime-context <archive-root> --format json
archive project-version-update <project-or-archive-root> --target vX.Y.Z --dry-run --format json
.\.zettel-kasten\bin\archive.cmd version <project-or-archive-root> --format json
```

`archive --version` is the fastest human check. The structured `archive version`
form is for AI runtimes and scripts. `runtime-context` includes the same
version summary under `wom_kit_version`, so an agent can confirm archive identity
and kit version in one read-only request.

For a v0.4.13 project, the `project_runtime` object is also canonical evidence.
It separately reports the versioned receipt, a freshly observed installed-
payload tree hash, installed module inventory, stable launcher, current
executable/module/prefix and isolated Python flags, project-relative
`project_runtime_argv`, pin/runtime agreement, and whether the running process
matches the project. A receipt or matching version number alone is not live
process proof. Ordinary writes should use
`.\.zettel-kasten\bin\archive.cmd`. A different running version is blocked
before an approved writer dispatches with `project_runtime_mismatch`; the
result changes no files and returns the exact project-local argv.

### Windows PATH shadow and bounded Git probes (v0.4.3)

On Windows, `archive version` now returns `path_shadow_diagnostic`. A bounded
system application-resolution probe enumerates at most 64 `archive` launcher
candidates in actual selection order without executing any alternate. It
reports candidate 1 as selected, compares that selection with the running
process launcher when observable, and separately reports the imported WOM-kit
module version/origin and inspected project source version. It explicitly does
not claim that an unexecuted alternate launcher imports a particular module.

Exact launcher and module paths remain redacted by default. Use
`--no-redact-local-paths` only during attended local diagnosis. The report
never edits PATH, replaces a launcher, installs Python, or changes a project.

`--progress` writes an immediate content-free line to stderr before source and
Git provenance work. All Git reads in one version inspection share a 12-second
total budget, in addition to the existing per-child limits. Once that deadline
is exhausted, later Git probes are skipped and the result reports
`source_probe_budget.budget_exhausted: true`; no write process is started. This
prevents a chain of stuck Git or credential-helper children from leaving the
operator with indefinite silence.

## Source Of Truth

The package version is the canonical implementation value:

```text
wom_kit.__version__
```

When WOM-kit is running from a source checkout, the version report also compares
that package value with `wom-kit/pyproject.toml`. A mismatch blocks the report
with a warning because it means packaging metadata and runtime imports no longer
agree.

## Optional Project Pin

A project may record which WOM-kit it was installed or pinned with:

```text
.zettel-kasten/source/installed-version.txt
.zettel-kasten/installed-version.txt
installed-version.txt
```

These files are optional. If one is present under the inspected root,
`archive version <root> --format json` compares it with the running CLI version.
If the inspected root is an archive root containing `archive.yml`, the version
check also searches the parent project root. This covers the common layout where
the project pin lives beside the archive folder instead of inside it.

The JSON result reports safe logical locations such as
`parent_of_archive/.zettel-kasten/installed-version.txt`; it does not print the
local absolute path unless `--no-redact-local-paths` is explicitly used. A
mismatch does not rewrite anything; it simply returns `ok: false` with
`consistency_state: project_pin_mismatch` or `project_runtime_mismatch` so the
human can run the intended project launcher or perform a reviewed update.
UTF-8
BOM-prefixed pin files are normalized for Windows-created text files.

The pin is also an untrusted local input. Only an exact stable
`v<major>.<minor>.<patch>` value is eligible for the shareable result. Other
text is reported as invalid with `installed_version: null`; WOM does not copy
the raw value into JSON, text output, or `runtime_alignment`.

## Optional Project Source Mirror

A project may also keep a checked-out WOM-kit source mirror at:

```text
.zettel-kasten/source
```

Starting in v0.3.137, `archive version <root> --format json` reports a
`project_source_mirror` block when that folder exists. The check is still
read-only. It compares:

- mirror package version from `wom-kit/src/wom_kit/__init__.py`,
- mirror `wom-kit/pyproject.toml` version,
- mirror `installed-version.txt`,
- exact Git head tag when available,
- latest fetched semver tag when available.

Those source, pyproject, pin, and tag fields expose only exact stable version
labels. Malformed version strings and arbitrary local tag names are
fail-closed evidence and appear as `null`; even a conventional local `.git`
directory cannot use a tag name as a general-purpose output payload.

This catches a common drift case: a project-local mirror may still point at an
old source checkout even though newer tags have been fetched locally. In that
case the JSON can return:

```text
consistency_state: project_source_mirror_behind_latest_fetched_tag
```

or:

```text
consistency_state: project_source_mirror_mismatch
```

The read-only `archive version` command does not run `git fetch`, update the
mirror, switch branches, edit pins, or repair anything automatically. In
contract terms, the version check writes no files and calls no providers;
update dry-run is also local, reads no secrets, and repairs no project source
mirror.

## Runtime Alignment And Project-Scoped Bridge

Starting in v0.3.291, `archive version <root> --format json` also returns a
bounded `runtime_alignment` decision and `next_safe_actions`. This makes the
important difference between these two situations explicit:

```text
project source and pin agree with the running import -> aligned
project source and pin agree with each other but not the running import
                                              -> project_scoped_bridge_available
```

The second state commonly occurs when the global `archive` console script
imports a different Python checkout from the project's verified source mirror.
It does not mean that `project-version-update` failed: that command owns the
project mirror and pins, not the machine-wide Python installation.

Default output remains path-redacted and provides only logical locations and
safe actions. For trusted local debugging, explicit
`--no-redact-local-paths` may return one structured `bridge_argv` using the
current Python executable, an in-memory bootstrap, isolated Python `-I -S`
mode, and the inspected root. The bootstrap loads the verified
`wom-kit/cli/archive.py` blob from the expected Git object rather than trusting
a later path read. WOM emits that argv only when the mirror package version,
mirror pyproject version, pin, wrapper object, tag, and commit agree.

`runtime_alignment.integrity` then applies a second gate. It requires real
non-symlink/reparse project paths, the exact Git worktree root, and a
conventional real project-local `.git` directory with no linked-worktree
pointer, alternate object store, graft, symlink, junction, or reparse route.
It directly compares the commit tree, stage-zero index, index flags, bounded
raw worktree bytes, and allowed untracked `installed-version.txt`; it does not
use `git status` or repository-configured filters. It requires an untracked
pin, the complete tracked runtime Python source set, every synchronized
resource listed in the resource manifest, safe index flags, exact index/`HEAD` and raw-byte agreement,
and a closed source tree with no extra importable Python, bytecode cache, or
native extension. It also requires the fixed origin configuration key, the
exact annotated `v<source-version>` tag at `HEAD`, all three tagged source
version files in agreement, and local evidence that the tag is reachable from
`origin/main`. The origin check reads only the fixed key name, not its URL
value.

Runtime source and metadata inventories stream `os.scandir` entries and stop at
fixed caps. The updater repeats the closed-source check before mutation; even
an ignored, noncolliding top-level shadow under `wom-kit/src` blocks.

The bridge binds the expected commit, annotated tag, wrapper object, and
runtime-resource objects into its argv. The in-memory bootstrap rechecks those
objects, rejects a preloaded external `wom_kit`, and verifies the imported
package and CLI module locations. It permits only the read-only `version`
command; it is not a general write command bridge.

The final import boundary does not place `wom-kit/src` on `sys.path`. It purges
all project-path aliases and installs a custom finder that loads only
`wom_kit` modules through their exact expected Git object IDs. Thus a
post-gate project shadow for a top-level dependency such as `yaml` or `sqlite3`
cannot be selected from that source root. Repository attributes make the
verified Python sources byte-stable across Windows and POSIX release checkouts.
These are local checks only: `-S` prevents `site` initialization, executable
`.pth` lines, and
`sitecustomize` before bootstrap; after object verification and wrapper
compilation, only stdlib `sysconfig`'s `purelib` and `platlib` paths are
appended without processing them through `site.py`. Replacement objects and
lazy fetch are disabled, `network_used` remains false, no origin URL or
credential value is read, and this report does not claim cryptographic
signature verification or current remote freshness.

The bridge runs the verified project source for one invocation. It does not:

- replace the global `archive` on `PATH`;
- install, update, or remove a pip, uv, pipx, or editable tool;
- guess how the active command was installed;
- change an already imported Python process; or
- install or update the separate `wom-archive` runtime Agent Skill.

### Same-account multi-project boundary

Multiple project folders under one Windows account may resolve the same
user-level `archive.exe`. Replacing that executable changes the running tool
seen by every such folder on its next invocation; the current working directory
does not sandbox it. Conversely, a project source mirror and pin may remain on
an older version because project update is a separate transaction.

For that reason, `archive --version` alone is never project-update evidence.
Use `archive version <project-or-archive-root> --format json` and compare the
running import, project source, pin, PATH selection, and runtime alignment.
The read-only project bridge remains version-command-only and does not claim to
isolate general commands per folder. Release verification should use an
explicit executable inside a dedicated temporary environment when replacing a
same-account shared PATH tool is not intended.

If source/pin metadata is incomplete or inconsistent, or any local release
integrity check fails, the result fails closed and provides no executable
bridge argv. A present but unverified mirror also makes the command nonzero.
In v0.4.3, preview a verified `project-version-update --dry-run`, review its
content-free exact-human binding, and use the Windows CLI approval route only
when the target and complete-transaction quiescence are intentional. The
service recomputes the same preview and authenticates the exact claim before
the locked updater starts. Collision and bytecode-repair writers remain fixed
closed. See [Project Version Update](project-version-update.md).

## Source Development Launcher

The direct `wom-kit/cli/archive.py` wrapper is not the normal launcher for an
active development checkout. Its closed-tree checks intentionally reject
ordinary development state such as bytecode caches, extra Python sources, or
modified tracked runtime bytes. Use the package module instead.

From inside `wom-kit/` in PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m wom_kit.archive_cli <command> ...
```

From inside `wom-kit/` in a POSIX shell:

```bash
PYTHONPATH=src python -m wom_kit.archive_cli <command> ...
```

The direct wrapper has two narrow supported roles:

1. the exact isolated invocation returned in a verified `bridge_argv`; and
2. an explicit recovery attempt from a pristine, exact tagged checkout.

Do not make a development tree look pristine by deleting or reverting unknown
work. Preserve the work, use the module launcher for development, and use a
separate pristine checkout when recovery evidence is required.

## WOM Bridge Refusal Codes

The direct wrapper exposes exactly these six stable external refusal codes:

- `WOM_BRIDGE_PRELOADED_MODULE`: `wom_kit` was already loaded before the
  verified bridge import boundary;
- `WOM_BRIDGE_SOURCE_TREE_UNSAFE`: the Git, source-byte, index, closed-tree, or
  synchronized-resource gate did not verify;
- `WOM_BRIDGE_PROJECT_PATH_ON_SYS_PATH`: a project-path alias remained on
  `sys.path` after the required purge;
- `WOM_BRIDGE_IMPORT_FAILED`: the exact verified package or CLI module could
  not be imported;
- `WOM_BRIDGE_IMPORT_SOURCE_MISMATCH`: an imported module did not come from
  the exact verified project source path; and
- `WOM_BRIDGE_ENTRYPOINT_INVALID`: the verified CLI module did not expose a
  callable `main` entrypoint.

Every such refusal writes the code followed by this fixed, content-free line:

```text
WOM_BRIDGE_RECOVERY_DOC=https://github.com/mow-coding/zettel-kasten/blob/main/wom-kit/docs/version-truth-source.md#wom-bridge-refusal-codes
```

The line contains no inspected path, module name, repository payload, or
exception text. For an ordinary development checkout, switch to the module
launcher above. For a generated bridge, do not bypass the gate: start a new
process, rerun `archive version <root> --format json`, and follow its
`next_safe_actions`. For pristine recovery, use a separate exact tagged
checkout and keep the original checkout unchanged for diagnosis.

## Project Update Preview And Exact-Human Contract

The v0.4.3 command keeps the bounded preview and adds the Windows exact-human
approval path described in the project-update guide:

```powershell
archive project-version-update <project-or-archive-root> `
  --target vX.Y.Z `
  --dry-run `
  --progress `
  --output .zettel-kasten/diagnostics/update-preview-20260811-001.json `
  --format json
```

An unbound direct writer returns `exact_human_approval_required` before private
project reads. The bound CLI writer must rederive the same preview and target
digests after approval before entering the updater. The implementation details
below remain the updater's current lock, mutation, rollback, and receipt
contract; collision and bytecode-repair mutation stay fixed closed.

From v0.3.315, a locally available exact target uses the same digest-bound
materialization planner in preview and approval. Its cross-map covers the
current tree, target tree, index, and worktree using NFKC/case-folding,
HFS-ignored characters, Windows trailing/reserved/`.git` aliases, and
conservative 8.3-looking-name rejection. Public results carry fixed codes,
counts, one `materialization_plan_sha256`, and opaque `update-entry:NNNN`
references, never ignored local paths or hashes.

A bound collision must be inspected through the separate CLI-only
`project-version-update-collision` surface. An eligible ignored regular entry
may be preserve-relocated only after its own fresh dry-run and reviewed
approval. That action never retries the updater. After it completes, the
operator must run a fresh updater dry-run and approve that new updater plan
separately. Private receipts provide only
`unauthenticated_private_state_internal_consistency`; they are not signatures
or same-user tamper protection. Nullable write/relocation fields and
`recovery_required` mean the outcome is uncertain and retained evidence must
not be deleted or blindly replayed.

From v0.3.316, a complete collision batch can be classified once with
`project-version-update-collision --action inspect-all`. Only an exact complete
set of supported ignored Python cache artifacts can route to a separately
planned and approved `project-bytecode-repair` bound to the same target and
materialization digest. The repair shares the updater lock but does not fetch,
change `HEAD` or the installed-version pin, retry the updater, or grant update
approval. Therefore version truth remains unchanged until a fresh updater
preview is separately approved and a new process verifies running import,
source, pin, and exact-tag agreement.

These project-local output paths opt into v0.3.314 operation observation. An
archive-root invocation instead uses a fresh
`.wom-scratch/diagnostics/*.json` output. Stderr prints an opaque
`operation_ref` early. If a caller times out, inspect that exact operation from
a later process rather than starting another writer:

```powershell
archive operation-control <project-or-archive-root> --operation-ref op:sha256:<digest> --action status --dry-run --format json
archive operation-control <project-or-archive-root> --operation-ref op:sha256:<digest> --action wait --timeout-seconds 60 --dry-run --format json
archive operation-control <project-or-archive-root> --operation-ref op:sha256:<digest> --action recovery-plan --dry-run --format json
```

A wait deadline is neutral. Cancel is fixed unsupported and writes nothing;
resume, daemon, queue, background launch, force kill, and lock deletion are not
implemented. A completed operation artifact still does not reload the caller;
start a new process and verify `archive version`.

Approval changes only the project-local source mirror, recognized version pins,
and one project update receipt. The updater manually materializes the complete
tracked target commit tree from bounded Git blobs, without `git checkout`.
Strict cross-platform path checks reject aliases, reserved names, unsafe path
components, and ambiguous file/directory transitions before the first source
write. It then verifies raw worktree bytes, the rebuilt stage-zero index, index
flags, the closed import tree, and all synchronized runtime resources.

From v0.3.314, each complete tracked target tree uses one bounded `ls-tree`
inventory and one strict unique-blob `cat-file --batch` stream instead of one
Git child per file. In the controlled four-tree reproduction, this reduced
11,184 Git processes to eight and loaded the four trees in 2.538 seconds.
Object framing, type, size, rehash, per-file/total byte caps, and trailing bytes
remain fail closed. The timing is one local benchmark, not a universal update
runtime guarantee.

The transaction reserves its lock and receipt with exclusive `O_EXCL` creation
and records file identity before writing. Source, pin, configuration, lock, and
receipt snapshots provide checkpointed change detection, not atomic file
compare-and-swap. Windows directory-name stability also does not freeze file
content. External editors, sync/backup tools, and other Git writers must remain
quiescent for the entire approval, and every approval must carry
`--affirm-external-writers-quiescent` plus the reviewer.

On the Windows approval path, results expose:

```text
write_boundary.external_writer_quiescence_required: true
write_boundary.external_writer_quiescence_affirmed: true
write_boundary.atomic_file_compare_and_swap: false
write_boundary.checkpointed_change_detection: true
```

Detected drift preserves the owned lock and produces incomplete rollback.
Configuration-digest drift immediately before rollback skips source/pin restore
entirely. True handle/descriptor-bound file CAS remains future work. v0.3.291
writes receipt schema v0.2 with `external_writer_quiescence: {affirmed: true,
scope: complete_project_version_update_transaction}`, while the v0.1 schema
remains compatible for existing receipts. An already-targeted mirror is
`no_change` only after the same integrity and pin checks pass. It does not
update archive knowledge. See
[Project Version Update](project-version-update.md) for the full preflight,
origin/tag evidence, rollback, restart, and bootstrap boundary.

The approved transaction is Windows-only in v0.3.291. Windows holds every
verified write-path directory without `FILE_SHARE_DELETE`, preventing rename,
deletion, or junction replacement across the source/`.git`/pin/lock/receipt
path chains. A missing receipt parent and receipt root are created and held in
order; the receipt writer refuses an unheld root.

On POSIX, dry-run remains available and returns
`preview_only_platform_unsupported` with
`write_boundary.approval_platform_supported: false`. POSIX `--approve` fails
closed because an open directory descriptor does not pin its pathname against
rename and the Git/complete-tree transaction is not descriptor-relative end to
end.

## Privacy Boundary

The version check is local and does not contact the origin. The update dry-run
is also local and does not fetch or write. Update approval may invoke the
configured Git transport and credential helper, and credential access may
therefore occur. WOM-kit limits its own evidence boundary as follows:

- the version check writes no files and calls no providers,
- update approval writes only its declared project source/pin/receipt
  boundary, including complete commit-tree materialization and owned rollback,
- effective Git configuration streams directly into a one-way digest process;
  its original config text is not exposed to the Python result,
- only `GIT_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_SSH`, and `GIT_SSH_COMMAND`
  contribute environment values to that digest,
- the selected `git` executable, `PATH`, `HTTP_PROXY`, `HTTPS_PROXY`,
  `SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `SSH_AUTH_SOCK`, `HOME`, and other
  non-`GIT_*` toolchain/transport environment remain trusted-stable operator
  prerequisites and are not bound,
- WOM-kit does not itself query keyrings, vaults, browser stores, mailboxes, or
  archive source documents, while the configured Git transport or credential
  helper remains outside that guarantee,
- the read-only version check repairs no project source mirror,
- it redacts local absolute paths by default.

Use `--no-redact-local-paths` only for trusted local debugging.

## Remaining Boundary

v0.3.291 is not an unattended global auto-updater, installer repair system, live
provider sync, secret retrieval flow, or project/archive migration engine. It
does not verify a cryptographic tag signature, force-overwrite a colliding tag,
reload the running Python process, update a dirty source mirror, or change user
knowledge. The project-scoped bridge is not a global-tool replacement.
Project-update approval is not available on POSIX in this release.
Installations older than v0.3.215 need one final existing/manual verified
update before the project updater is available for later releases.
