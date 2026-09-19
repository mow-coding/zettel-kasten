# v0.4.28 release evidence and client boundary

Date: 2026-09-19 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the implementation,
the bump and every release step, under the user's standing approval to
work through the backlog without re-asking ("밀린거 작업 다 알아서 처리하고
있어라"). The read-only design map was produced by a bounded Ultracode
workflow (9 agents); no workflow agent touched a release step. The scope
and unit decisions are in the
[implementation record](2026-09-19-v0428-object-storage-restore.md), the
[decision log](../wom-kit/docs/archive-infra-decision-log-2026-09-19-v0428-v0429-object-restore-offload.md)
and the acceptance register (OB-01, OB-03).

## User intent and execution boundary

v0.4.28 is the first half of the object-storage offload feature that the
2026-09-04 decision log planned for v0.4.23 and that the user had asked
for long before ("이거 진작에 됐어야 하는건데"): the way back
(`object-storage-restore`, OB-01 and OB-03) ships first so that the way
out (`object-storage-offload`, OB-02, v0.4.29) is reversible from its first
public build. Development used synthetic archives and temporary
repositories only; no client runtime, archive, workspace, feedback ledger,
credential, provider configuration or shared PATH installation was read or
changed by this release execution. The client's letter 163 was read after
the candidate was opened and is answered by v0.4.30, not by this release.

## Reviewed source and CI

- [PR #116](https://github.com/mow-coding/zettel-kasten/pull/116)
  squash-merged exact head `6ccaefc2` into
  `4a78cd7c09159e711f7f555990bf29a45fe83d72`. The merge commit's tree
  `7c41d2c4b39f2bfd37a5aec37409b94d2c372879` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- The first candidate run
  ([35413749223](https://github.com/mow-coding/zettel-kasten/actions/runs/35413749223),
  head `579ccde6`) failed on the two Ubuntu shard-1 jobs: eleven CLI test
  fakes did not accept the new `timeout=` keyword of the live opener, the
  startup progress-command pin lacked the two new command names, and two
  count pins (approval-available commands 57, pending coverage rows 30)
  were stale. Correction commit `6ccaefc2` fixed the tests and the
  `cli_entry` list only; the
  [second run](https://github.com/mow-coding/zettel-kasten/actions/runs/35415313051)
  passed all 14 jobs with no rerun.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35419737605)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35419766785)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.27 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`4a78cd7c`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after this record.

The supplement passed every check: 170 packaged resources (737,067 bytes),
309 wheel members scanned (17,677,339 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.28; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.28` has tag object
`31b2c11f5e2314a76a92186f9fc19240035787d1` and remote peeled target
`4a78cd7c09159e711f7f555990bf29a45fe83d72`, equal to the main head.

[WOM-kit v0.4.28](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.28)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-19T04:17:42Z (2026-09-19 13:17 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.28-py3-none-any.whl` |
| Size | 3,223,547 bytes |
| SHA-256 | `50777719c2cdf9d81980de32aaad28a6c02ca6c0ebc945da2c9f82a51df4b8a6` |
| Verified package resources | 170 |
| Verified resource bytes | 737,067 |
| Scanned text-like wheel members | 309 |
| Scanned text-like bytes | 17,677,339 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 170 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.28` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.28")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branch `claude/v0428-object-storage-restore` and its worktree hold
no unmerged product change (the released tree equals the branch tree) and
are removed after this record merges; the untracked supplement checker copy
is deleted after this record; the supplement wheel stays under the ignored
`wom-kit/dist-v0428/` directory and is never committed.

Public release, local installed verification and source tests do not set
any feedback letter's `resolved_in` and do not close OB-01 or OB-03, which
need the client's own `--verify-only` and restore runs. OB-02 (the offload
writer) is the v0.4.29 candidate already under review as
[PR #117](https://github.com/mow-coding/zettel-kasten/pull/117); the client
will be told to run a restore before the first offload on the same archive.
The reply draft to the client is refreshed to v0.4.28 (restore section) and
gains the letter-163 answers.
