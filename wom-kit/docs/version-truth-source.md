# WOM-kit Version Truth Source

Status: v0.3.291 read-only runtime alignment plus approval-gated project update

WOM-kit has several places where a human or AI might see a version-like value:
the installed CLI, the source checkout, and a project-local pin left by a setup
or runtime workflow. This page defines the safe order for checking them.

## Canonical Checks

Use these commands before deciding which kit is current:

```powershell
archive --version
archive version --format json
archive version <project-or-archive-root> --format json
archive runtime-context <archive-root> --format json
archive project-version-update <project-or-archive-root> --target vX.Y.Z --dry-run --format json
```

`archive --version` is the fastest human check. The structured `archive version`
form is for AI runtimes and scripts. `runtime-context` includes the same
version summary under `wom_kit_version`, so an agent can confirm archive identity
and kit version in one read-only request.

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
`consistency_state: project_pin_mismatch` so the human can decide whether to
upgrade the project-local source or switch to the intended CLI. UTF-8
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
pin, the complete tracked runtime Python source set, all 103 synchronized
runtime resources, safe index flags, exact index/`HEAD` and raw-byte agreement,
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

If source/pin metadata is incomplete or inconsistent, or any local release
integrity check fails, the result fails closed and provides no executable
bridge argv. A present but unverified mirror also makes the command nonzero.
Preview a verified `project-version-update` first and, when a write is needed,
pause editors, sync/backup clients, and other Git writers for the complete
transaction before completing its affirmed approval from Windows.

## Approval-Gated Project Update

Starting in v0.3.215, a separate command can perform that bounded update after
an explicit preview and human approval:

```powershell
archive project-version-update <project-or-archive-root> `
  --target vX.Y.Z `
  --dry-run `
  --progress `
  --format json

archive project-version-update <project-or-archive-root> `
  --target vX.Y.Z `
  --approve `
  --reviewed-by <actor> `
  --affirm-external-writers-quiescent `
  --progress `
  --format json
```

Approval changes only the project-local source mirror, recognized version pins,
and one project update receipt. The updater manually materializes the complete
tracked target commit tree from bounded Git blobs, without `git checkout`.
Strict cross-platform path checks reject aliases, reserved names, unsafe path
components, and ambiguous file/directory transitions before the first source
write. It then verifies raw worktree bytes, the rebuilt stage-zero index, index
flags, the closed import tree, and all synchronized runtime resources.

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
