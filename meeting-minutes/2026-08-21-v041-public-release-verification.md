# WOM-kit v0.4.1 public release verification

Date: 2026-08-21 KST

## Purpose and boundary

This record closes the public-release boundary for WOM-kit v0.4.1. It records
only public, content-free release evidence. No protected archive, credential,
provider account, real native approval popup, or private source value was
opened or mutated during release verification.

Letter 139's local-commit and remote-backup authority remains the separate
v0.4.2 planning and implementation track. It is not part of v0.4.1. This
release also does not claim to update a project-local source mirror.

## Pull-request correction and implementation merge

The first draft head correctly failed its whole-tree privacy gate because a
new public meeting-minute path repeated a protected archive-specific name. The
five references were generalized without weakening the sealed predecessor
rule. The corrected privacy module passed locally, and the complete replacement
CI run passed on the corrected head.

- Implementation pull request:
  <https://github.com/mow-coding/zettel-kasten/pull/73>
- Final pull-request head:
  `59e8267e4819d04df82279050a5d0e16e6f0a9b0`
- Final Required CI run:
  <https://github.com/mow-coding/zettel-kasten/actions/runs/32476723009>
- Final CI result: the release-readiness gate, eight platform/version test
  shards, and aggregate `Required CI` job all completed successfully.
- Final run interval: `2026-08-21T11:20:02Z` through
  `2026-08-21T12:04:40Z`.
- Merge time: `2026-08-21T12:05:42Z`.
- Two-parent merge commit:
  `f7b82c7bf16350d5e2ab0bc2cf9c53cef574b740`
- First parent: `f24bfd262651f808e3c7dade5c476aea6f66d4ed`.
- Second parent: `59e8267e4819d04df82279050a5d0e16e6f0a9b0`.
- The merge tree and final pull-request-head tree were identical:
  `c223cf6f4f6b81a2abbae19629f4cacf32706271`.
- Main-push readiness run:
  <https://github.com/mow-coding/zettel-kasten/actions/runs/32480246427>
- Main-push result: success. Matrix tests and aggregate PR-only gate were
  skipped by workflow design.

The repository remained public after merge.

## Exact merged-commit artifact

A new detached worktree pinned to the exact merge commit produced the release
artifact. The package-resource synchronization check reported 158 files for
v0.4.1, and all four release-readiness checks passed: public links, Korean
product language, public privacy, and Runtime Skill packaging.

The exact merged-commit wheel checker reported:

- Package version: `0.4.1`.
- Manifested and verified resources: `158/158`.
- Verified resource bytes: `659,549`.
- Wheel members: `218`.
- Entrypoints: `archive`, `wom`, `archive-mcp`, and `wom-mcp`.
- MCP inventories: `130/130`, byte-identical, with canonical SHA-256
  `2168629227ea71bc2d9c912f086eb9a142a62538a47046459b378b27b9f27f0a`.
- Runtime Skill lifecycle: passed.
- Onboarding preview: passed; onboarding write remained fixed closed.
- Strict Doctor: passed on the checked-in synthetic fake archive.
- Installed Letter 140 smoke: exact body and snapshot preserved, canonical
  link exact, one v0.2 receipt validated from the installed package.

The authoritative artifact is:

- Name: `wom_kit-0.4.1-py3-none-any.whl`.
- Size: `2,064,685` bytes.
- SHA-256:
  `49bc2958c4d7375df3a277322e2b32a8616c06f1cd21926ec8d483c1ee5ed519`.

The committed source release note and packaged release note were byte-identical
at 13,890 bytes with SHA-256
`a5d3f506d93877768ecb9368e01a6e1581daa131287b392d6522a136f0d42704`.
The published Release body was byte-identical to that committed note. The
packaged resource manifest was 39,833 bytes with SHA-256
`ccf38ac349967da201a1c049a5363ff46303669aff92b7c438c476e8e2205b29`.

Before publication, an isolated tool root installed the public v0.4.0 asset,
reported `archive 0.4.0`, then installed this exact local merge wheel without
`--force`; both CLI aliases then reported the exact product string
`archive 0.4.1`.

## Annotated tag and public Release

- Tag: `v0.4.1`.
- Annotated tag object:
  `f8213ce15dcf4c0dce5f523f7c57d699ed9c9211`.
- Peeled commit:
  `f7b82c7bf16350d5e2ab0bc2cf9c53cef574b740`.
- Tag-push readiness run:
  <https://github.com/mow-coding/zettel-kasten/actions/runs/32480622449>
- Tag-push result: success.
- Public Release:
  <https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.1>
- Release id: `374375274`.
- Published at: `2026-08-21T12:11:24Z`.
- State: stable, non-draft, non-prerelease, and Latest.
- Release body: exact committed v0.4.1 release-note bytes.

The Release contains exactly one asset:

- Asset id: `523697595`.
- Name: `wom_kit-0.4.1-py3-none-any.whl`.
- Size: `2,064,685` bytes.
- State: uploaded.
- GitHub digest:
  `sha256:49bc2958c4d7375df3a277322e2b32a8616c06f1cd21926ec8d483c1ee5ed519`.
- Public download:
  <https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.1/wom_kit-0.4.1-py3-none-any.whl>

## Anonymous download and public installation

The asset was retrieved from the public URL with client configuration disabled
and empty Authorization and Cookie headers. The final response was HTTP `200`.
The anonymous download was `2,064,685` bytes, and its SHA-256 matched both the
locally verified artifact and GitHub asset digest. An unauthenticated GitHub
API request independently returned release id `374375274`, tag `v0.4.1`,
stable public state, and exactly the same single asset.

One new isolated `uv tool` root then exercised the actual public upgrade path:

- Public v0.4.0 asset installed first and reported `archive 0.4.0`.
- The public v0.4.1 asset installed over it without `--force`.
- The `archive` and `wom` executables both reported the exact product string
  `archive 0.4.1`.
- Package metadata reported `wom-kit 0.4.1`.
- The imported module resolved inside the isolated tool's `site-packages`.
- The three installed packages were dependency-compatible.

A second empty isolated tool root performed an independent public v0.4.1 fresh
install. Python `3.12.10` loaded package `0.4.1` from that isolated tool's
`site-packages`; both CLI aliases reported `archive 0.4.1`; help exited
successfully; strict Doctor returned `ok: true` on the checked-in synthetic
fake archive; and the installed dependencies were compatible.

The shared `archive 0.4.1` version string is intentional product branding for
both executable aliases; it is not evidence that the `wom` executable was
skipped.

An earlier direct-import probe was run with the release checkout as its current
directory and therefore resolved the checkout's root shim. That result was
explicitly rejected as installation evidence. Both accepted import probes were
rerun from content-neutral temporary working directories and resolved inside
their respective isolated tool environments.

## Scope truth

This release reopens only one exactly approved Zettel-Objet link apply. Link
revert, Objet capture, project update, and the remaining fixed-closed compound
writers stay closed. The checks used only repository synthetic fixtures; they
do not claim a real provider contact, real credential enrollment, native popup
interaction, or protected-archive repair.

The verified public upgrade replaces the isolated global Python CLI selected
by `PATH`. It does not mutate an archive, change a project pin, update a
project-local source mirror, or install an AI-host Agent Skill. No archive
migration is required for the v0.4.1 CLI.

## Cleanup checkpoint

The exact merged-commit artifact directory, anonymous-download directory,
local and public upgrade roots, public fresh-install root, and detached exact-
release worktree remain preserved until this first closeout commit is stored on
the remote branch. Those task-owned artifacts and the detached release
worktree will then be removed through exact, verified targets, and the results
will be recorded in a follow-up closeout commit.

The merged implementation worktree and its local and remote branch, plus the
closeout worktree and its local and remote branch, remain until the closeout
pull request is merged and `origin/main` is independently verified to contain
this record. They will then be removed as a separate post-merge cleanup phase.
Unrelated historical worktrees, branches, and temporary evidence are outside
both cleanup phases and will not be touched.
