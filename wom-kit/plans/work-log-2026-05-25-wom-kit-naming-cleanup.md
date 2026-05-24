# Work Log: v0.2.19 WOM-kit Naming Cleanup

Date: 2026-05-25

Branch: `codex/v0.2.19-wom-kit-naming-cleanup`

## Goal

Rename the implementation/tooling layer to WOM-kit while keeping the repository root as `zettel-kasten` and preserving command behavior.

## Naming Decisions Applied

- Public implementation/tooling name: `WOM-kit`
- Filesystem implementation folder: `wom-kit/`
- Python import package: `wom_kit`
- Repository root: `zettel-kasten`
- Product/system language remains `WOM`, `zet`, and `ZET`.

## Implementation Notes

- Moved the implementation folder to `wom-kit/`.
- Moved the Python package to `wom-kit/src/wom_kit/`.
- Updated imports, tests, wrapper scripts, MCP startup examples, command examples, schema titles, and package metadata.
- Kept `archive` and `archive-mcp` compatibility console scripts.
- Added preferred `wom` and `wom-mcp` console script aliases.

## Safety Notes

- No command behavior change.
- No lifecycle command removal.
- No source-intake implementation.
- No provider sync or UI implementation.
- No change to WOM/zet/ZET philosophy.

## Verification Plan

- `python -m unittest discover -s wom-kit\tests`
- `python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict`
- `python -m wom_kit.archive_cli doctor wom-kit\examples\fake-life-archive --strict`
- `git diff --check`
- naming searches
- privacy scan

## Review Follow-Up

Claude reviewed the rename and found no critical logic blockers. The follow-up work focused on release hygiene and checkout behavior:

- Track the root `wom_kit/__init__.py` checkout shim intentionally.
- Remove stale `__pycache__` files and keep cache artifacts ignored.
- Correct `CITATION.cff` `date-released` to `2026-05-25`.
- Document that MCP wire identifiers remain stable for compatibility even though the public implementation name is now WOM-kit.
- Add a root shim import/version guard test.
- Verify the new `wom` / `wom-mcp` console aliases through an editable install.
- Replace public example paths that used a personal-looking placeholder with `C:\Users\example`.

## Verification Results

- `python -m unittest discover -s wom-kit\tests` passed with `189` tests and `8` skipped.
- `python wom-kit\cli\archive.py doctor wom-kit\examples\fake-life-archive --strict` passed with `0` errors and `0` warnings.
- `python -m wom_kit.archive_cli doctor wom-kit\examples\fake-life-archive --strict` passed with `0` errors and `0` warnings.
- `python -m pip install -e wom-kit --no-deps` succeeded.
- `wom --help` and `archive --help` both exited successfully.
- `git diff --check` reported no whitespace errors; only Windows line-ending normalization warnings appeared.
- Naming scans found no stale implementation names, old import names, title-case `zet` product nouns, or mixed-case `WOM` variants in current-facing files.
- Privacy scan found no real local paths, tokens, secrets, private file names, or private user data in public changes.
