# v0.3.317 Public Release Verification

Date: 2026-08-13

## Purpose

This closeout records the evidence that became available only after the WOM-kit
v0.3.317 implementation and frozen-tree verification were complete. Detailed
design and correction chronology remains in these records:

- `meeting-minutes/2026-08-13-human-credential-console.md`
- `meeting-minutes/2026-08-13-letter130-staged-cleanup-evidence.md`
- `meeting-minutes/2026-08-13-v03317-release-preparation.md`

v0.3.317 adds the visible Windows credential console, secure saved-credential
reuse and legacy scope evolution, authoritative Notion bot/PAT scope handling,
and Letter 130 staged-cleanup evidence and durable content-free result support.

## Remote CI and merge evidence

- Pull request: https://github.com/mow-coding/zettel-kasten/pull/64
- Final candidate commit:
  `5d32dd85726abc18f2ba3814689cb9c610d8182d`.
- Final PR CI run:
  https://github.com/mow-coding/zettel-kasten/actions/runs/31665987694
- CI result: release readiness, four Ubuntu shards, four Windows shards, and
  the required aggregate check all completed successfully; 10 checks succeeded
  and none failed or remained running.
- Merge time: 2026-08-13 14:51:38 KST.
- Merge commit: `5d51e083c327c56af15e9394ee6a1fd7ec527189`.
- The local `main` branch and `origin/main` were both verified at that merge
  commit with a clean worktree before packaging.

The first PR run found one Linux-only fixed-error ordering defect. A reparse
`evolutions` directory was already rejected, but a generic local-document code
was raised before the credential evolution boundary could report
`credential_registry_evolution_directory_unsafe`. The follow-up commit retained
the same fail-closed path rejection while preserving the domain-specific error
contract. Both affected Ubuntu shards and the complete required matrix passed
on the final candidate.

## Tagged merged-main artifact evidence

- Annotated tag: `v0.3.317`.
- The tag resolves to merge commit
  `5d51e083c327c56af15e9394ee6a1fd7ec527189`.
- Tag CI run:
  https://github.com/mow-coding/zettel-kasten/actions/runs/31671949001
- The tag release-readiness and packaged-resource synchronization gates both
  completed successfully.
- Public GitHub Release:
  https://github.com/mow-coding/zettel-kasten/releases/tag/v0.3.317
- Publication time: 2026-08-13 14:56:20 KST.
- Published wheel: `wom_kit-0.3.317-py3-none-any.whl`.
- Wheel size: 1,849,118 bytes.
- Wheel SHA-256:
  `e371c84554334824634ac795040da38c3ab6239db9dcd6c0f5d42124380e55b7`.
- GitHub's asset digest, the merged-main build digest, and the anonymously
  downloaded public-file digest were identical.

The wheel was rebuilt from the clean merged `main` commit rather than reused
from the pull-request head. The official install checker verified package
version 0.3.317, 145 of 145 packaged resources, 190 wheel files, both CLI entry
points, both MCP entry points, byte-identical 121-tool MCP inventories, Runtime
Skill lifecycle, onboarding preview and write, and strict Doctor.

## Anonymous download and fresh-install evidence

The published wheel was downloaded directly from its public HTTPS release URL
with `curl.exe`, without a GitHub-authenticated client or authorization header.
Its byte count and SHA-256 exactly matched the merged-main candidate and GitHub
asset metadata.

A newly created Python 3.12 virtual environment installed only that downloaded
wheel and its declared dependencies. Verification established:

- `pip check`: no broken requirements.
- Installed distribution and imported module version: 0.3.317.
- `unicodedata2` distribution 17.0.1 and Unicode database 17.0.0.
- Packaged resource manifest version 0.3.317 with 145 files.
- `archive` and `wom` structured version output: 0.3.317.
- `archive-mcp` and `wom-mcp`: protocol `2025-03-26`, server version 0.3.317,
  121 tools each, complete pagination, and byte-identical canonical inventory
  SHA-256
  `931dc2bd42037c41b3bb2bb05b04dec5b4b4c58ebf384b57deb6420ef2d8be98`.

The first attestation invocation stopped because PowerShell altered nested
quotes in the inline Python `-c` argument after the wheel download and install
had already succeeded. No product assertion failed. The immutable downloaded
wheel was rehashed, the same isolated environment was checked, and the
attestation was rerun with quote-safe input before the remaining probes passed.

## Evidence boundary and closeout

This record proves implementation, local regression, independent review,
remote CI, merge, annotated tag, public GitHub Release, anonymous download, and
fresh isolated installation. It does not claim a live authenticated Notion
operation, a real PAT entry, or beta-client acceptance. Those require a user to
install v0.3.317 and exercise the reviewed workflow in their own WOM workspace.

No protected archive, private zettel, credential value, provider
payload, or authenticated Notion service was read or modified during release
publication and public-wheel verification.
