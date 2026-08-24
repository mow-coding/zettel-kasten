# Install WOM-kit As A Python Tool

Status: v0.4.3 conditional GitHub wheel and exact recovery boundary

WOM-kit is a command-line tool. It should live in its own Python environment
instead of being mixed into an application project's dependencies.

## One Windows account with multiple client folders

An isolated `uv tool` environment isolates Python dependencies; it does **not**
make the exposed `archive.exe` private to the folder from which it is called.
Every process under the same Windows account that resolves the same executable
on PATH can see a replacement immediately on its next invocation. Therefore
`archive --version` reports the running shared tool version, not proof that one
client project was updated.

For same-computer beta clients, inspect both layers:

```powershell
archive --version
archive version <project-or-archive-root> --format json
```

Use the second result's project source, pin, and `project_runtime` evidence to
decide whether that client project needs an update. During development and
release verification, install the wheel in a dedicated temporary virtual
environment and invoke its `Scripts\archive.exe` by explicit path; do not
replace the user-shared PATH tool as a side effect of testing.

The approved v0.4.3 updater then installs the verified release wheel under the
selected project at `.zettel-kasten/runtimes/vX.Y.Z/` and activates the stable
`.zettel-kasten/bin/archive.cmd` launcher. Ordinary project commands use that
launcher. Other project folders and the user-shared PATH executable do not
change. This is WOM's supported project runtime boundary; it does not isolate
arbitrary non-WOM programs or separate Windows user permissions.

The v0.4.3 URL below is a conditional contract, not proof that an artifact is
public. Use it only after the matching GitHub Release exists and lists the
verified wheel. See the [v0.4.3 release note](releases/v0.4.3.md) for the
separate source and release-evidence boundary.

An installed v0.4.2 client contains the Git read-only planners but not v0.4.3's
exact commit/push writer, source-property backfill, or reopened project updater.
Updating repository files alone does not replace the isolated `uv tool` or
virtual-environment wheel. After the verified v0.4.3 asset exists, install that
exact wheel and start a new process.

## Recommended Project Bootstrap

Create a temporary bootstrap only after the exact WOM GitHub Release exists and
lists the verified wheel. The versioned URL alone is not proof that the asset
is available:

```powershell
py -m venv .wom-bootstrap-v043
& .\.wom-bootstrap-v046\Scripts\python.exe -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.6/wom_kit-0.4.6-py3-none-any.whl"
& .\.wom-bootstrap-v043\Scripts\archive.exe --version
```

After the new process reports exactly `archive 0.4.3`, use that explicit
bootstrap executable for `project-version-update`. After approval succeeds,
verify the project runtime and use its launcher:

```powershell
.\.zettel-kasten\bin\archive.cmd version <project-or-archive-root> --format json
.\.zettel-kasten\bin\archive.cmd git-backup-plan <archive-root> --remote origin --dry-run --format json
```

It observes the checked-out symbolic branch and remote ref without a write.
Its exact approval/resume path may commit and non-force push only the bound
selection. See [Git Backup Plan And Reconciliation Plan](git-backup-plan.md)
before interpreting or approving its result.

`uv tool install` creates an isolated tool environment and exposes all commands
provided by the package. WOM-kit installs `archive`, `wom`, `archive-mcp`, and
`wom-mcp`. The environment is dependency-isolated but its exposed commands are
user-shared PATH entrypoints, not project-folder-local commands.

This release does not publish WOM-kit to PyPI. Therefore
`pip install wom-kit` is not the official command yet. The exact GitHub release
URL keeps the installed artifact tied to a reviewed repository tag.

### Replace an installed older global CLI

After the v0.4.3 Release and wheel actually exist, replace the isolated
`uv tool` environment and verify the result from a new process:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.6/wom_kit-0.4.6-py3-none-any.whl"
archive --version
```

The official `uv` contract says a repeated `uv tool install` generally replaces
an existing `uv`-managed tool. Use `--force` only if `uv` explicitly reports an
unmanaged executable collision and a human has reviewed that executable; the
flag permits replacing executables that `uv` does not manage. See the
[official `uv tool install` reference](https://docs.astral.sh/uv/reference/cli/#uv-tool-install).

Require exactly `archive 0.4.3`. This is a global CLI-only bootstrap. It does
not change a project-local `.zettel-kasten/source` mirror or version pin. The
project updater is a separate exact-human workflow; collision mutation and
bytecode repair remain fixed closed. Do not hand-edit the pin. See [Project
Version Update](project-version-update.md) and the [Upgrade Guide](../../UPGRADE.md).

## Standard pip Alternative

Plain `pip` works when it is placed inside a dedicated virtual environment:

```powershell
py -m venv "$HOME\.wom-tools\wom-kit"
& "$HOME\.wom-tools\wom-kit\Scripts\python.exe" -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.6/wom_kit-0.4.6-py3-none-any.whl"
& "$HOME\.wom-tools\wom-kit\Scripts\archive.exe" --version
```

The environment is only for the tool. It is not a WOM archive and should not
be placed inside an archive.

## What The Wheel Contains

The wheel contains the Python commands and the runtime resources needed by
those commands:

- JSON schemas used by validation and Doctor,
- personal, family, company, and runtime templates,
- the progressively disclosed `wom-archive` Agent Skill package,
- base zettel-kasten rules and link types,
- the current release identity note.

The repository copies remain the source of truth. A deterministic manifest
binds each packaged mirror file to its exact byte length and SHA-256.
Before release, the wheel checker also requires that manifest to match the
reviewed repository manifest byte for byte, requires the packaged resource set
to be exact, and verifies every resource against both its declared digest and
the repository packaged mirror.

## What Installation Does Not Do

Installation does not:

- create or modify an archive,
- read zet bodies or objet bytes,
- contact a provider, object store, or external database,
- read credentials,
- install the packaged Agent Skill into an AI host's configuration directory,
- make a generated graph canonical.

## When The Project And Global Command Differ

`archive version <project-or-archive-root> --format json` compares the running
import with the project's source mirror and version pin. A project update does
not silently replace the Python tool selected by `PATH`.

Since v0.3.291, a self-consistent project mirror that differs from the running
import can report `project_scoped_bridge_available`. Trusted local debugging
may use `--no-redact-local-paths` to obtain its exact structured bridge argv.
The argv exists only when `runtime_alignment.integrity.verified` is true after
local real-path, project-local Git-metadata, raw worktree/index/flag, exact
source/resource-byte, closed-import, annotated-tag, tagged-version, and
`origin/main` ancestry checks. Its Python `-I -S` bootstrap binds the expected
commit, tag, wrapper blob, and every synchronized resource listed in the manifest, executes the
wrapper from verified memory, and permits only the read-only `version`
command. It does not put the project source root on `sys.path`: it purges
project aliases and an exact-object-id custom finder loads only `wom_kit`, so
a post-gate top-level `yaml` or `sqlite3` shadow cannot execute. `-S` blocks
site initialization, executable `.pth` lines, and `sitecustomize`; after
verification, only stdlib-`sysconfig` `purelib` and `platlib` paths are added
without `site.py` processing. It uses no network and reads no origin URL
value. That argv runs the
verified project source for one invocation. It does not update, reinstall, or
remove the global tool, and WOM does not guess whether pip, uv, pipx, or an
editable checkout owns that tool.

For existing project mirrors, `project-version-update --dry-run` inspects the
complete tracked target commit tree when prior CRLF bytes or other exact-tree
drift would fail the historical gate. It validates
cross-platform paths, rebuilds the index, avoids `git status` and repository
filters, streams directory scans with entry caps, and blocks even an ignored
noncolliding `wom-kit/src` shadow before mutation. Exclusive lock and receipt
ownership plus source/pin checkpoints detect observed drift, but they are not
atomic file compare-and-swap and cannot guarantee that an external writer will
never clobber a file.

In v0.4.3, approval is available only on the reviewed Windows native exact-
human path. The plan binds current source/pin, target annotated tag and commit,
rollback state, and the receipt's approval reference. Cancelled, drifted,
ambiguous, or unsupported-platform attempts make no project change. Collision
mutation and bytecode repair remain separate fixed-closed surfaces.

From v0.3.314, the explicit output also prints an opaque `operation_ref` early.
If the caller times out, retain that reference and use `operation-control`
status or bounded wait against the exact starting root instead of launching a
duplicate updater. Output-supervised archive-root updates use a fresh
`.wom-scratch/diagnostics/*.json` path instead. Cancel and resume are not
implemented, and status does not replace a fresh `archive version` check after
the update finishes.

The result reports `external_writer_quiescence_required: true`,
`external_writer_quiescence_affirmed: true`,
`atomic_file_compare_and_swap: false`, and
`checkpointed_change_detection: true`. The v0.2 receipt records
`external_writer_quiescence: {affirmed: true, scope:
complete_project_version_update_transaction}`; old v0.1 receipts remain
compatible. True file-handle/descriptor-bound CAS is future work. This
project-scoped update does not reinstall or replace the global console tool.

The configuration checkpoint binds effective Git configuration plus exactly
`GIT_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_SSH`, and `GIT_SSH_COMMAND`. It does
not bind the selected Git executable, `PATH`, `HTTP_PROXY`, `HTTPS_PROXY`,
`SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `SSH_AUTH_SOCK`, `HOME`, or other non-Git
toolchain and transport environment. Keep those trusted operational
prerequisites stable too. If the bound configuration digest changes
immediately before rollback, WOM skips restoration, preserves its owned lock,
and reports incomplete rollback.

Historically in v0.3.291, the writer was available only on Windows. WOM held the verified
project, source/`.git`, pin, lock, and receipt directory chains without
`FILE_SHARE_DELETE`, preventing rename, deletion, or junction replacement. A
missing receipt parent and root are created and held in order, and the receipt
writer rejects an unheld root.

All v0.4.3 users can run the complete read-only preview. POSIX returns
`preview_only_platform_unsupported` and
`write_boundary.approval_platform_supported: false`. It does not run the
Windows native exact-human writer.

The runtime Agent Skill is a third, separate lifecycle. Installing or updating
the Python tool does not automatically install the Skill, and
`runtime-skill-install` does not replace the Python CLI.

Archive creation remains a separate dry-run-first operation:

```powershell
archive onboard --target-root <new-archive-folder> --type personal --archive-id <archive-id> --principal-id <principal-id> --dry-run --format json
```

In v0.4.3 stop after the preview. Onboarding approval returns
`compound_exact_human_approval_binding_required` before target/template/provider
reads and creates no archive.

## Optional Agent Skill Activation

Python installation only makes the activation commands available. It does not
run them. Preview the current Codex user-scope target separately:

```powershell
archive runtime-skill-install --dry-run --format json
```

Approve only the exact returned plan. See
[Install The WOM Archive Agent Skill](runtime-skill-install.md) for user,
repository, custom-host, update, status, and safe uninstall workflows.

## Release Verification

Maintainers run:

```powershell
python wom-kit/tools/sync_package_resources.py --check
python wom-kit/tools/check_wheel_install.py --format json
```

The second command builds a wheel from a clean source copy, inspects every
manifested resource, and installs it in a fresh virtual environment. It
executes both CLI version probes and performs initialize/list/EOF handshakes
against both MCP aliases, requiring strict UTF-8, empty stderr, bounded
output/runtime, descendant-process containment, and byte-identical complete
tool inventories. It then previews/installs/verifies/uninstalls the Agent Skill
in a disposable host directory, previews archive onboarding, proves the real
onboarding write is fixed-closed with zero files written, and runs strict
Doctor against the checked-in fake archive through the installed entrypoint.
For v0.4.1 it also copies that synthetic fixture into a second temporary
archive and uses only the isolated installed wheel to prove one ready
`zettel-objet-link` plan, one exact approved `written` result, the exact
canonical object link, unchanged leading Markdown body bytes, an exact
snapshot, a schema-valid v0.2 receipt, and successful receipt lookup.
A release wheel may be preserved only after that entire check passes. The JSON
result uses `wom-kit/wheel-install-check/v0.3` and records the onboarding write
state as `fixed_closed` plus the installed Letter 140 workflow evidence; it
does not claim that v0.4 created a new real archive.
