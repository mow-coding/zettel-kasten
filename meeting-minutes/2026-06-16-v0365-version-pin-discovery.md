# Meeting Minutes - v0.3.65 Version Pin Discovery

Date: 2026-06-16

## Context

After the R2 setup-guide bridge, remaining feedback noted that version truth was
still confusing when a development checkout, a project-local installed-version
pin, and the current public release did not all line up.

The reported shape was especially easy to miss when the command inspected an
archive folder while the installed-version pin lived in the parent project
folder.

## Decision

v0.3.65 should keep the version truth-source command read-only, but make its pin
discovery match this common project layout.

## Implemented

- `archive version <root> --format json` now checks the inspected root first.
- If the inspected root contains `archive.yml`, it also checks the parent
  project root for the same installed-version pin candidates.
- The JSON result reports logical, redacted locations such as
  `parent_of_archive/.zettel-kasten/installed-version.txt`.
- `project_pin.pin_root` and `project_pin.checked_locations` make the search
  path explicit without exposing local absolute paths.
- UTF-8 BOM-prefixed installed-version files are normalized for Windows-created
  pin files.
- Runtime context inherits the same `wom_kit_version` behavior.

## Safety Boundary

The flow remains local and non-secret:

- no files written,
- no provider calls,
- no secret/keyring/vault/browser-store reads,
- no source document reads,
- no local absolute paths echoed by default.
