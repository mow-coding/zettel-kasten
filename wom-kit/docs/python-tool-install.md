# Install WOM-kit As A Python Tool

Status: v0.3.300 GitHub wheel and Letters 098-111 integrated completion checkpoint

WOM-kit is a command-line tool. It should live in its own Python environment
instead of being mixed into an application project's dependencies.

## Recommended Install

Install with `uv` only after the exact WOM GitHub Release exists and lists the
verified wheel. The versioned URL alone is not proof that the asset is
available:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.300/wom_kit-0.3.300-py3-none-any.whl"
archive --version
```

`uv tool install` creates an isolated tool environment and exposes all commands
provided by the package. WOM-kit installs `archive`, `wom`, `archive-mcp`, and
`wom-mcp`.

This release does not publish WOM-kit to PyPI. Therefore
`pip install wom-kit` is not the official command yet. The exact GitHub release
URL keeps the installed artifact tied to a reviewed repository tag.

## Standard pip Alternative

Plain `pip` works when it is placed inside a dedicated virtual environment:

```powershell
py -m venv "$HOME\.wom-tools\wom-kit"
& "$HOME\.wom-tools\wom-kit\Scripts\python.exe" -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.300/wom_kit-0.3.300-py3-none-any.whl"
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
commit, tag, wrapper blob, and all 113 synchronized resources, executes the
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

For existing Windows project mirrors, approved `project-version-update` also
manually materializes the complete tracked target commit tree when prior CRLF
bytes or other exact-tree drift would fail the gate. It validates
cross-platform paths, rebuilds the index, avoids `git status` and repository
filters, streams directory scans with entry caps, and blocks even an ignored
noncolliding `wom-kit/src` shadow before mutation. Exclusive lock and receipt
ownership plus source/pin checkpoints detect observed drift, but they are not
atomic file compare-and-swap and cannot guarantee that an external writer will
never clobber a file.

Before every approval, run the dry-run, then pause editors, sync clients,
backup tools, and every other Git writer for the complete update transaction.
Approve only while they remain paused:

```powershell
archive project-version-update <project-or-archive-root> --target vX.Y.Z --approve --reviewed-by <actor> --affirm-external-writers-quiescent --format json
```

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

In v0.3.291, approval is available only on Windows. WOM holds the verified
project, source/`.git`, pin, lock, and receipt directory chains without
`FILE_SHARE_DELETE`, preventing rename, deletion, or junction replacement. A
missing receipt parent and root are created and held in order, and the receipt
writer rejects an unheld root.

POSIX users can still run the complete read-only preview. It returns
`preview_only_platform_unsupported` and
`write_boundary.approval_platform_supported: false`; POSIX `--approve` is
blocked until the Git/full-tree transaction is descriptor-relative end to end.

The runtime Agent Skill is a third, separate lifecycle. Installing or updating
the Python tool does not automatically install the Skill, and
`runtime-skill-install` does not replace the Python CLI.

Archive creation remains a separate dry-run-first operation:

```powershell
archive onboard --target-root <new-archive-folder> --type personal --archive-id <archive-id> --principal-id <principal-id> --dry-run --format json
```

Review the preview before replacing `--dry-run` with `--approve`.

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
in a disposable host directory, previews and creates a disposable archive, and
runs strict Doctor. A release wheel may be preserved only after that entire
check passes.
