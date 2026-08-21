# WOM-kit v0.4.2 public release verification

Date: 2026-08-22 KST

## Purpose and boundary

This record closes the public-release boundary for WOM-kit v0.4.2. It records
only public, content-free release evidence. No protected archive body, private
feedback body, credential value, provider account, real approval popup, or
real user worktree content was opened or mutated during release verification.

v0.4.2 implements only Letter 139's privacy-preserving read-only Git planning
foundation. It adds the CLI-only `git-backup-plan` and
`git-backup-reconcile-plan` observations. It does not add a Git writer, an MCP
Git writer, approval authority, commit grouping, add, commit, fetch, pull,
push, merge, rebase, reset, checkout, clean, deletion, provider-side backup
confirmation, or a completion receipt.

## Pull request and exact candidate CI

The implementation and release pull request was:

- <https://github.com/mow-coding/zettel-kasten/pull/75>

The first candidate head was
`d5db46fb7fc9c187852161504aa0381abe940243`. Its first CI run was:

- <https://github.com/mow-coding/zettel-kasten/actions/runs/32497078595>

The release-readiness gate and seven of eight platform/version shards passed.
Windows Python 3.12 shard 2/4 made continuous successful test progress until
GitHub cancelled it at the configured job limit. The exact annotation was
`The job has exceeded the maximum execution time of 45m0s`. The unittest step
ran for 44 minutes 33 seconds and reported no test failure before
cancellation. A same-head failed-job rerun was started, then intentionally
superseded after 18 minutes once the timeout evidence was independently
confirmed; that rerun is not presented as release evidence.

The correction changed only Windows shard 2/4's job limit from 45 to 75
minutes and updated its exact CI-contract test and chronological record. It did
not skip, remove, reorder, or weaken a test and did not change product runtime
behavior. The equivalent v0.4.1 success had consumed 44 minutes 16 seconds of
the former 45-minute job, so the old limit had only 44 seconds of headroom.

The final pull-request head was:

- `835a3574371568e51bbe3244372afd709a792773`

Its final Required CI run was:

- <https://github.com/mow-coding/zettel-kasten/actions/runs/32503152329>
- Interval: `2026-08-21T16:29:07Z` through `2026-08-21T17:13:20Z`.
- Result: release-readiness gate, all eight platform/version shards, and the
  aggregate `Required CI` job completed successfully.
- The corrected Windows 2/4 unittest step completed successfully after 43
  minutes 27 seconds; the complete job finished successfully after about 44
  minutes 2 seconds.

The pull request merged at `2026-08-21T17:14:16Z` as the two-parent commit:

- Merge commit: `27593ccde79ff0efb47d40d390962acf85c062ad`.
- First parent: `0730c4a4528b90da08e0132e8cd3c8431c9c8543`.
- Second parent: `835a3574371568e51bbe3244372afd709a792773`.
- Merge tree and final pull-request-head tree:
  `2c17c70fef996d9280f7ad4af9715c6f90743476`.

The main-push gate succeeded at the exact merge commit:

- <https://github.com/mow-coding/zettel-kasten/actions/runs/32507105678>

The repository remained public, with `main` as its default branch.

## Exact merged-commit artifact

A new clean detached worktree pinned to
`27593ccde79ff0efb47d40d390962acf85c062ad` produced and verified the release
artifact. The repository wheel checker built the wheel, installed that exact
wheel into a clean environment, preserved the verified bytes, and removed its
internal temporary environment on success.

The exact checker reported:

- Package version: `0.4.2`.
- Manifested and verified resources: `158/158`.
- Verified resource bytes: `653,731`.
- Wheel members: `219`.
- Entrypoints: `archive`, `wom`, `archive-mcp`, and `wom-mcp`.
- MCP inventories: `130/130`, byte-identical, with canonical SHA-256
  `c8e7ad47f1bc9ccb6c8418b5d06d84b064d09c658c71fd32bfba544f83458883`.
- Runtime Skill lifecycle: passed.
- Onboarding preview: passed; onboarding write remained fixed closed.
- Strict Doctor: passed on the checked-in synthetic fake archive.
- Installed Letter 140 smoke: body and snapshot preserved, canonical link
  exact, and one v0.2 receipt validated from the installed package.

The authoritative artifact is:

- Name: `wom_kit-0.4.2-py3-none-any.whl`.
- Size: `2,086,008` bytes.
- SHA-256:
  `a7873605a294d0a9b80bc751ff7f24a2cc78fe58bbe3fc319907f40ac044df6e`.

The committed source release note, packaged release note, and published
Release body were byte-identical at 8,072 bytes with SHA-256
`eff8541b1923b75c01e7c365b22617735be6dec14d7d2226c1663b040bb0b053`.
The committed and packaged resource manifests were byte-identical at 39,832
bytes with SHA-256
`0b79c0f5722a517488cb72f62f2f8714ec3a8977bbd3fccd8466af8080dbb559`.

## Annotated tag and public Release

- Tag: `v0.4.2`.
- Annotated tag object:
  `7b8b09bc746392e0fbacf3c5b48f55a34b10644b`.
- Peeled product commit:
  `27593ccde79ff0efb47d40d390962acf85c062ad`.
- Tag-push gate:
  <https://github.com/mow-coding/zettel-kasten/actions/runs/32507375643>.
- Tag-push result: success.
- Public Release:
  <https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.2>.
- Release id: `374559061`.
- Published at: `2026-08-21T17:18:32Z`.
- State: stable, non-draft, non-prerelease, and Latest.

The Release contains exactly one asset:

- Asset id: `524029706`.
- Name: `wom_kit-0.4.2-py3-none-any.whl`.
- Size: `2,086,008` bytes.
- State: uploaded.
- GitHub digest:
  `sha256:a7873605a294d0a9b80bc751ff7f24a2cc78fe58bbe3fc319907f40ac044df6e`.
- Public download:
  <https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.2/wom_kit-0.4.2-py3-none-any.whl>.

## Anonymous download and public installation

The Release page, tag API, Latest API, and exact wheel URL were requested with
client configuration disabled and empty Authorization and Cookie headers. All
four final responses were HTTP `200`. The anonymous API independently returned
release id `374559061`, stable public state, Latest tag `v0.4.2`, and exactly
one asset. The anonymous wheel was `2,086,008` bytes and its SHA-256 matched
the local verified artifact and GitHub digest.

One isolated `uv tool` root exercised the real public upgrade path:

- The public v0.4.1 asset installed first.
- `archive` and `wom` both reported `archive 0.4.1`.
- The public v0.4.2 asset installed over it without `--force`.
- `archive` and `wom` both then reported `archive 0.4.2`.
- Package metadata reported `wom-kit 0.4.2`.
- A probe from a content-neutral working directory imported `wom_kit` from
  the isolated tool environment's `site-packages`.
- All three installed packages were dependency-compatible.

A second empty isolated tool root performed an independent public fresh
install:

- Package metadata and both CLI aliases reported version `0.4.2`.
- The import again resolved inside that isolated environment's
  `site-packages` from a content-neutral working directory.
- `git-backup-plan --help` and `git-backup-reconcile-plan --help` both exited
  successfully and exposed their installed commands.
- Strict Doctor returned `ok: true` on the checked-in synthetic fake archive.
- All installed dependencies were compatible.

The shared `archive 0.4.2` version string is intentional product branding for
both executable aliases; it is not evidence that the `wom` executable was
skipped. These isolated checks did not modify the user's ordinary global tool
installation or shell `PATH`.

## Scope truth

The two Git commands remain content-free, bounded, fail-closed observations.
They always keep `ready_for_write: false`, `writer_available: false`, and
`would_change: []`. A plan digest is not an approval token. No actual archive,
provider repository, credential helper, private remote, or user worktree was
used as a release fixture.

This release does not claim that Letter 139's end-to-end backup request is
complete. Exact file selection, commit grouping, one-writer pause, commit and
push authority, provider re-query, and a completion receipt remain future
work. The verified public upgrade replaces only the isolated global CLI
selected by its tool-bin directory; it does not update a project-local source
mirror, archive content, project pin, or AI-host Agent Skill installation.

## Historical public-history privacy debt

A bounded public-history audit found one class of non-placeholder Windows
user-home path metadata in older commits. It found two distinct
non-placeholder user segments, eight related commits, seven safe public paths,
and twelve unique commit/path/direction events. The finding is absent from the
current tree and is classified as historical non-credential privacy debt: the
path metadata is not a credential, token, private key, provider secret, or
protected archive body.

The exact release candidate passed the hardened public-privacy gate. GitHub
secret scanning and push protection were enabled at release time, and the
repository reported zero open and zero resolved secret-scanning alerts.
Non-provider generic patterns and validity checks were disabled, so this
record does not claim universal secret-format coverage or provider-side
validity testing.

The gate now uses content-free diagnostics, scans exact index blobs separately
from the worktree, covers every tracked regular file plus bounded sensitive
untracked candidates, rejects symlink/reparse and changing-index states, and
blocks the same covered local-path class from entering future release trees.
It does not retroactively remove existing Git objects, and this record does not
claim that the historical debt has been remediated.

No history rewrite was performed as part of v0.4.2. At audit time, a complete
rewrite from the first occurrence would have changed approximately 503
mainline commits and 382 tags, disrupted existing beta-tester clones, and
required force updates. The user explicitly chose to keep the repository
public and release v0.4.2 without that rewrite while retaining the old-path
cleanup as a future obligation.

Any later cleanup requires a separately approved migration with a publication
freeze, preserved backup refs, an exact rewrite map, tag and Release
reconciliation, coordinated remote updates, mandatory beta-tester re-clone
instructions, independent post-migration verification, and a rollback plan.
Third-party clones or caches cannot be guaranteed erased. The historical
values themselves must not be repeated in new public records.

## Cleanup checkpoint

The first closeout commit,
`171e59c5ddbbd6021748cb8a54a36dd1ec78f47c`, was stored on the remote
closeout branch before cleanup.

The first cleanup safety check stopped without deleting anything because the
Git worktree registry used forward-slash path spelling while the resolved
Windows path used backslashes. The target was normalized and reverified rather
than weakening or bypassing the exact-path check.

The exact-merge release worktree was then verified as an ordinary non-reparse
directory, clean at
`27593ccde79ff0efb47d40d390962acf85c062ad`, and registered at the normalized
exact path. It was removed through Git's worktree operation and is absent from
both the filesystem and worktree registry.

The verified wheel directory, anonymous-download evidence directory, isolated
public-upgrade root, and isolated public-fresh root were each verified as
ordinary non-reparse directories under the operating-system temporary root
and sent to the Windows Recycle Bin. All four are absent from their original
paths and remain recoverable from the Recycle Bin. The public annotated tag,
stable Release, and exact uploaded asset remain published with the recorded
identities and digest.

The implementation worktree and its local and remote branch, plus this
closeout worktree and branch, also remain. They will be removed only after the
records-only closeout pull request passes Required CI, merges into `main`, and
`origin/main` is independently verified to contain this record. Unrelated
historical worktrees, branches, and temporary evidence are outside this
cleanup scope and will not be touched.
