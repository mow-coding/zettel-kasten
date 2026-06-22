# WOM-kit Version Truth Source

Status: v0.3.137 read-only version truth-source checkpoint with project source mirror drift discovery

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

The command does not run `git fetch`, update the mirror, switch branches, edit
pins, or repair anything automatically.

## Privacy Boundary

The version check is local and non-secret:

- it writes no files,
- it calls no providers,
- it reads no secrets, keyrings, vaults, browser stores, mailboxes, or source
  documents,
- it repairs no project source mirror,
- it redacts local absolute paths by default.

Use `--no-redact-local-paths` only for trusted local debugging.

## Not Implemented

v0.3.137 does not provide automatic upgrade, installer repair, project source
mirror repair, live provider sync, IMAP execution, secret retrieval, or project
migration. It only gives a clear read-only signal about which WOM-kit version is
running and whether optional project-local pin/source mirror evidence agrees
with it.
