# WOM-kit Version Truth Source

Status: v0.3.215 read-only version truth plus approval-gated project update

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
mirror, switch branches, edit pins, or repair anything automatically.

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
  --progress `
  --format json
```

Approval changes only the project-local source mirror, recognized version pins,
and one project update receipt. It does not update archive knowledge. See
[Project Version Update](project-version-update.md) for the full preflight,
origin/tag evidence, rollback, restart, and bootstrap boundary.

## Privacy Boundary

The version check is local and non-secret. The update dry-run is also local and
does not fetch or write. Update approval may invoke the configured Git transport
and credential helper, but WOM-kit does not read or echo credential values:

- the version check writes no files and calls no providers,
- update approval writes only its declared project source/pin/receipt boundary,
- it reads no secrets, keyrings, vaults, browser stores, mailboxes, or source
  documents,
- it repairs no project source mirror,
- it redacts local absolute paths by default.

Use `--no-redact-local-paths` only for trusted local debugging.

## Remaining Boundary

v0.3.215 is not an unattended auto-updater, installer repair system, live
provider sync, secret retrieval flow, or project/archive migration engine. It
does not verify a cryptographic tag signature, force-overwrite a colliding tag,
reload the running Python process, update a dirty source mirror, or change user
knowledge. Installations older than v0.3.215 need one final existing/manual
verified update before this command is available for later releases.
