# Meeting minutes: v0.3.318 public release verification

Date: 2026-08-14 (Asia/Seoul)

Status: v0.3.318 is merged, tagged, published, anonymously downloaded, and
fresh-install verified. Physical paste gestures and a live credential/provider
enrollment remain separate acceptance work.

## Scope and protected boundary

This closeout records the public release that follows Letter 131 credential
console and failure-stage work. The protected feedback source and archive
remained read-only. No real PAT, provider account, reviewed page identifier,
private locator, Credential Manager entry, or protected-archive content was
used during release verification.

## Product PR and CI

- Product PR: [#66](https://github.com/mow-coding/zettel-kasten/pull/66)
- Final PR head:
  `3d5b6572d69eeaa8c6eaaa3eddf7de0ae70819ff`
- Required PR run:
  [31708966066](https://github.com/mow-coding/zettel-kasten/actions/runs/31708966066)
- The release-readiness job, four Ubuntu shards, four Windows shards, and the
  aggregate Required CI job all completed successfully: 10/10 required checks.
- An earlier PR head failed the sealed public-surface privacy test because the
  two new internal minutes repeated a protected project proper name nine times.
  The predecessor count and empty allowlist were not relaxed. The records were
  generalized to `protected archive`, the exact gate returned to its sealed
  predecessor surface, and only the corrected final head is release evidence.

PR #66 merged at `2026-08-13T21:58:40Z` as merge commit:

```text
264d318ca29afe671e54ad5b22d178779bbad09e
```

After merge, local `main`, `origin/main`, and the merge commit were identical,
the worktree was clean, and the short-lived product branch was absent remotely.
The main-push CI run
[31748002783](https://github.com/mow-coding/zettel-kasten/actions/runs/31748002783)
completed successfully; its release-readiness and packaged-resource steps both
passed.

## Exact merged-main wheel

The official checker ran in a fresh detached worktree at the exact merge
commit. It built and installed a new wheel rather than reusing a PR artifact.

```text
filename: wom_kit-0.3.318-py3-none-any.whl
size: 1852110 bytes
sha256: c8da9025c6560388b86680c9df3213e273e5f76f0067c137d36eae1b45804853
package version: 0.3.318
wheel members: 190
manifested resources: 145
verified resources: 145
verified resource bytes: 588887
```

The checker passed `pip check`, both CLI versions, both MCP processes, Runtime
Skill lifecycle, onboarding preview/write, and strict Doctor. Each MCP
entrypoint exposed 121 tools through protocol `2025-03-26`; pagination was
complete and both canonical inventories were byte-identical with SHA-256:

```text
931dc2bd42037c41b3bb2bb05b04dec5b4b4c58ebf384b57deb6420ef2d8be98
```

An independent read-only wheel audit checked all 190 `RECORD` rows, duplicate
and unsafe paths, metadata, dependency declarations, and every source-to-
package-to-wheel resource byte. It also installed the candidate into a separate
Python 3.12 environment and confirmed all four entrypoint executables.

## Annotated tag and tag gate

The annotated tag object is:

```text
1d9f3c92ec47a66b6fac4d4fb156b1d696e57091
```

`v0.3.318^{commit}` resolves exactly to the product merge commit
`264d318ca29afe671e54ad5b22d178779bbad09e`. The exact tag-push CI run was
[31748632625](https://github.com/mow-coding/zettel-kasten/actions/runs/31748632625).
Its Release readiness gate job and Packaged resource synchronization step both
completed successfully. The test matrix and aggregate Required CI jobs were
skipped by the intended tag-event workflow condition; the full matrix had
already passed on PR #66.

The tag is an annotated tag and is unsigned. This matches the repository's
current release mechanism; no signed-tag claim is made.

## GitHub Release and public bytes

- Release: [WOM-kit v0.3.318](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.3.318)
- Published: `2026-08-13T22:09:01Z`
- State: public, non-draft, non-prerelease, latest
- Uploaded assets: exactly one
- Asset URL:
  [wom_kit-0.3.318-py3-none-any.whl](https://github.com/mow-coding/zettel-kasten/releases/download/v0.3.318/wom_kit-0.3.318-py3-none-any.whl)
- GitHub asset size: `1852110`
- GitHub asset digest:
  `sha256:c8da9025c6560388b86680c9df3213e273e5f76f0067c137d36eae1b45804853`

The asset was downloaded through a new unauthenticated `curl.exe` request,
without a GitHub token, cookie jar, or authorization header. Its size and
SHA-256 were exactly equal to both the checked merged-main candidate and the
GitHub asset metadata.

An independent read-only public audit made a second unauthenticated HTTP 200
download and reproduced the same size and SHA-256. It also independently
verified the latest-release state, exact one-asset inventory, tag object and
commit target, 145/145 packaged resources, `pip check`, all four entrypoints,
and the byte-identical MCP inventories.

## Fresh public installation

Only the anonymously downloaded wheel was installed into a new Python 3.12
virtual environment. Verification produced:

```text
pip check: No broken requirements found.
distribution version: 0.3.318
module version: 0.3.318
unicodedata2 distribution: 17.0.1
Unicode database: 17.0.0
resource manifest version: 0.3.318
resource manifest count: 145
archive --version: archive 0.3.318
```

The installed `archive`, `wom`, `archive-mcp`, and `wom-mcp` entrypoints all
completed their strict probes. Both MCP servers reported version `0.3.318`,
protocol `2025-03-26`, 121 tools, complete pagination, empty stderr, and the
same canonical inventory SHA shown above.

Two attestation attempts after the successful install used incorrect local
harness expressions: first an invalid resource-package target, then a quoting-
damaged resource path. They failed before producing product evidence. A
BOM-free stdin Python probe using the correct installed package resource path
then passed, as did the independent entrypoint probe. These were verification-
harness corrections, not wheel or installation failures. Similarly, the first
Release preflight stopped on PowerShell's handling of an expected 404 before
the create command ran; the API absence check was repeated explicitly and one
Release was then created.

## Honest remaining boundary

The automated Win32 canary and deterministic console tests prove WOM's console
mode, no-echo, status, rollback, and cleanup boundaries. They do not prove a
human's physical `Ctrl+V`, `Ctrl+Shift+V`, `Shift+Insert`, or right-click action
under every Windows Terminal, Console Host, or ConPTY-parent configuration.
Those gesture rows remain `not_performed`. No live authenticated Notion
operation, real credential enrollment, or beta-client acceptance is claimed by
this release record.

The product tag remains on the product merge commit. This records-only closeout
must be merged separately and must not move the release tag.
