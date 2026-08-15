# WOM-kit v0.3.320 Public Release Verification

Date: 2026-08-15

Status: Public release verified; task-owned cleanup follows after this evidence is durably pushed.

## Why this record exists

The user explicitly corrected the completion boundary after the implementation PR had
passed CI: finishing this release-scoped task meant merge, exact-tag publication,
GitHub Release publication, anonymous download, fresh installation, and cleanup—not
stopping at a green draft PR. The release workflow therefore continued without any
credential enrollment, provider call, archive mutation, or live recovery operation.

## Product PR and merge

- PR: `#69` — `Add one-use credential capability broker`
- Final PR head: `59c99f162ade96b473d293c686f812264e7ece86`
- Full PR CI run: `31881904010`
- Full PR result: 10/10 checks passed, including `Required CI`
- Merge time: `2026-08-15T13:06:19Z`
- Merge commit: `4d0a28c33e2e1325809730cd5e185584043b851d`
- Main push CI run: `31886319725`
- Main push result: release readiness and packaged-resource synchronization passed;
  matrix and aggregate jobs were skipped by the workflow's main-push condition.

The product tag remains on the product merge commit. This later records-only closeout
must not move that tag.

## Exact merge-SHA release candidate

A clean detached worktree was created at the exact merge commit. Its porcelain was
empty before and after the build. The repository release-readiness checker passed all
four public gates, and package resource synchronization passed for 146 files.

The official wheel checker returned `wom-kit/wheel-install-check/v0.2` with `ok: true`.

- Wheel: `wom_kit-0.3.320-py3-none-any.whl`
- Size: 1,890,494 bytes
- SHA-256: `e58fdb0316eddb529bb46111c99b451c1cb63c8f4453ab5ce999494f5670db96`
- ZIP members: 193
- Manifested and verified resources: 146/146
- Verified resource bytes: 596,453
- Entrypoints: `archive`, `wom`, `archive-mcp`, `wom-mcp`
- MCP protocol: `2025-03-26`
- MCP server name: `zettel-kasten-archive-mcp`
- MCP tools: 121 for each alias
- MCP inventory bytes: 102,829
- MCP inventory SHA-256:
  `931dc2bd42037c41b3bb2bb05b04dec5b4b4c58ebf384b57deb6420ef2d8be98`
- The two MCP inventories were byte-identical.
- Runtime Skill lifecycle, onboarding preview/write, and strict Doctor all passed.

The source release note was 6,241 UTF-8 bytes with SHA-256
`4c6710abb93331870df4c18f59976b2cc2a5ef524d9c697647c91c3c77b9a991`.

## Annotated tag and tag CI

- Tag: `v0.3.320`
- Annotated tag object: `41c17c7f7173cbe4efeb129302480c8f8356f2a5`
- Peeled commit: `4d0a28c33e2e1325809730cd5e185584043b851d`
- Tag push CI run: `31886497027`
- Tag push result: release readiness and packaged-resource synchronization passed;
  matrix and aggregate jobs were skipped by the workflow's tag-push condition.

The pre-existing `v0.3.319` tag was not moved or modified.

## Public GitHub Release

- Release URL: <https://github.com/mow-coding/zettel-kasten/releases/tag/v0.3.320>
- Release database id: `371052786`
- Published at: `2026-08-15T13:11:57Z`
- State: public, non-draft, non-prerelease, latest
- Asset count: exactly 1
- Asset id: `515706184`
- Asset name: `wom_kit-0.3.320-py3-none-any.whl`
- Asset size and GitHub digest matched the verified candidate exactly.
- The GitHub Release body matched the committed source release-note text exactly.

## Anonymous download and fresh installation

The public asset URL was fetched with `curl.exe --disable`, an empty Authorization
header, no cookie, redirects enabled, and no GitHub CLI session. The final response was
HTTP 200.

- Downloaded size: 1,890,494 bytes
- Downloaded SHA-256:
  `e58fdb0316eddb529bb46111c99b451c1cb63c8f4453ab5ce999494f5670db96`
- Candidate/public bytes: equal by size and SHA-256
- Fresh interpreter: Python 3.12.10
- Installed dependencies: PyYAML 6.0.3 and unicodedata2 17.0.1
- `pip check`: no broken requirements
- Distribution/module version: 0.3.320 / 0.3.320
- Module path: inside the fresh virtual environment, from an empty working directory
- Installed manifest SHA-256:
  `85662c76ceef690265ed8644c66e5af3d15b0dd44eee91f48577814351b1b205`
- Installed resources: 146, all byte counts and SHA-256 values verified
- Installed resource bytes: 596,453
- Installed entrypoints: all four present and executable
- Installed MCP aliases: 121 tools each, pagination complete, inventories byte-identical
- Installed wheel `direct_url.json` recorded the exact public-wheel SHA-256.

## Corrections made during the release workflow

The chronology includes three harmless wrapper/query mistakes so later operators do
not repeat them:

1. The first temporary-directory wrapper used an unsupported `New-Item -LiteralPath`
   parameter. It failed before creating a directory or touching the repository. The
   corrected wrapper used a containment-checked `-Path`.
2. The first readiness invocation supplied an unsupported `--format json` option.
   The resource check and wheel checker still ran, and the readiness checker was then
   rerun with its supported `--repo-root` option and passed all four gates.
3. The Release was created successfully, but the immediate `gh release view` query
   requested an unsupported `isLatest` JSON field. REST API queries then confirmed
   public/non-draft/non-prerelease/latest state, one asset, digest equality, and exact
   release-body text.

None of these wrapper/query errors changed product code, tags, assets, or release
contents.

## Evidence and privacy boundary

This release proves the capability-broker software artifact and public installation
boundary. It does not prove a live credential registration, Windows Credential Manager
read/write, Notion authentication, provider request, page recovery, 620-page run,
Basoon/archive mutation, or human acceptance of a real secret workflow.

No real PAT, credential value, account label, workspace label, anchor UUID, reviewed
request path, provider payload, or archive authentication material was read, written,
logged, transmitted, or included in this record.

The release evidence was first committed and pushed on the closeout branch. After that
durable remote copy existed, the registered detached merge-SHA build worktree was
removed through `git worktree remove`, and the exact task-owned v0.3.320 build and
anonymous-install TEMP roots were deleted. No task-owned process referenced either
root at deletion time, and both paths were confirmed absent afterward.

The short-lived v0.3.320 implementation/closeout branches and dedicated closeout
worktree remain only until this records-only change is merged; they are then removed
with safe branch/worktree commands. Older v0.3.319 evidence roots are out of scope and
remain preserved because their corresponding durable cleanup record has not been
established here. The user's primary workspace is also preserved unchanged.
