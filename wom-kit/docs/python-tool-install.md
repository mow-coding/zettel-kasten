# Install WOM-kit As A Python Tool

Status: v0.3.253 GitHub wheel and optional MOW Harness compatibility checkpoint

WOM-kit is a command-line tool. It should live in its own Python environment
instead of being mixed into an application project's dependencies.

## Recommended Install

Install the verified wheel attached to the exact WOM release with `uv`:

```powershell
uv tool install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.253/wom_kit-0.3.253-py3-none-any.whl"
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
& "$HOME\.wom-tools\wom-kit\Scripts\python.exe" -m pip install "https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.253/wom_kit-0.3.253-py3-none-any.whl"
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

## What Installation Does Not Do

Installation does not:

- create or modify an archive,
- read zet bodies or objet bytes,
- contact a provider, object store, or external database,
- read credentials,
- install the packaged Agent Skill into an AI host's configuration directory,
- make a generated graph canonical.

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
manifested resource, installs it in a fresh virtual environment, checks all
four entrypoints, previews/installs/verifies/uninstalls the Agent Skill in a
disposable host directory, previews and creates a disposable archive, and runs
strict Doctor. A release wheel may be preserved only after that entire check
passes.
