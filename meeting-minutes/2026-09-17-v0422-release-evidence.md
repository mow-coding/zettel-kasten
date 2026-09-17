# v0.4.22 release evidence and client boundary

Date: 2026-09-17 (Korea Standard Time)

Executing model: Claude Fable 5.1, solo and sequential for every code change,
fixture, verification and release step; one bounded read-only diagnostic
workflow (8 reader agents) was used only for the diagnosis of beta letters 161
and 162. All under the user's standing approval to run the v0.4.20 to v0.4.24
train and its releases without re-asking; the scope decision to ship the
update-failure repair alone, ahead of the carried rows, is recorded in the
[hotfix record](2026-09-17-v0422-update-failure-hotfix.md) and the acceptance
register.

## User intent and execution boundary

Beta letters 161 and 162 reported that the client's reviewed
`project-version-update` to v0.4.21 failed after the native approval with no
cause, left the claim `started` with the lock and reservation in place, and
that `--resume` failed in preflight. v0.4.22 makes that failure name its gate
and stage, adds `--resume --abandon-started-approval` so a claim left started
with nothing written can be closed and the reservation released by the
ordinary claimless cancellation, and corrects the `version` Git probe budget
report, the `operation-control` archive-root lookup and the `upgrade-check`
scope notice. Development used synthetic archives, temporary repositories and
local bare remotes only; no client runtime, archive, feedback ledger,
credential, provider configuration or shared PATH installation was read or
changed by this release execution. The refusing gate of the client's own run
is not known from the v0.4.21 diagnostics; the client's next run reports it.

## Reviewed source and CI

- [PR #104](https://github.com/mow-coding/zettel-kasten/pull/104)
  squash-merged exact head `b6d3bb7e` into
  `4a4b18500dd83fc30f278606b9393ead8629d85a`. The merge commit's tree
  `a0072bf42fe4905b819986dadb70eaa996abf61a` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35211328726)
  passed all 14 jobs on that head. Two earlier candidate runs found, on the
  Ubuntu shards, that the merged-stream CLI test runner parses stdout and
  stderr as one JSON document (the new `upgrade-check` scope notice is
  printed only when stderr is a terminal, `cd1d7464`) and that the v0.4.20
  cause-allowlist test expected an in-family but unlisted token to be
  dropped (the v0.4.22 contract carries fixed tokens of the project-update
  and approval families, all literal in source; the test's unlisted case
  uses an out-of-family token, `cd1d7464`); the second run was cut on
  Windows shard 4/4 at its 45-minute budget with no failing test while every
  Windows shard ran 6-10% slower than on the v0.4.21 candidate (40.7 minutes
  on the same shard), so that budget is 60 minutes from this release
  (`61ec60d8`, pin `b6d3bb7e`). The earlier runs were cancelled by the
  workflow's cancel-in-progress policy when the corrections were pushed.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35219631410)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35219690851)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

The committed installed-wheel checker gives the real runtime journey a
1,200-second aggregate budget that this machine cannot meet (recorded for
v0.4.19 through v0.4.21). Following that precedent, the release wheel was
built and verified from the clean exact-merge checkout (`4a4b1850`) by an
untracked local copy of the checker that differs only in its outer
runtime-child limit (2,400 seconds) and the two matching ceilings; reversing
those three edits reproduces the committed checker byte for byte (committed
checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`). The
official candidate gate passed the unmodified checker in CI (run
35211328726, "Installed public entrypoints and workflow gate"). The copy is
not tracked and is deleted after this record.

The supplement passed every check: 169 packaged resources (726,762 bytes),
304 wheel members scanned (17,483,309 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints, the letter-140,
v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs, the v0.4.19
real runtime journey (candidate repair and process-loss resume,
identifier-free resume without rebuild, source and ref drift blocked before
approval, no-op without candidate download or approval), the runtime skill
lifecycle and strict Doctor on the checked-in fake archive; the temporary
environment was removed on exit.

## Public artifact

Annotated tag `v0.4.22` has tag object
`157ddbf5ca88c09146c9c2f678c7b960d9e54eaa` and remote peeled target
`4a4b18500dd83fc30f278606b9393ead8629d85a`, equal to the main head.

[WOM-kit v0.4.22](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.22)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-17T12:40:00Z (21:40 KST); the release is neither
draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.22-py3-none-any.whl` |
| Size | 3,182,642 bytes |
| SHA-256 | `2c6ac4ac9f7d87e73987a40b9344731dd2e19e02bbd9019b692846da63d875d6` |
| Verified package resources | 169 |
| Verified resource bytes | 726,762 |
| Scanned text-like wheel members | 304 |
| Scanned text-like bytes | 17,483,309 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 169 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.22` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.22")` returned
`exact_public_release_wheel_verified` from `public_github_release` with the
wheel name and digest, without any project or credential access; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`. This closes the
real public bootstrap seam, not a client runtime update or private-data
recovery.

## Cleanup and remaining work

The hotfix branch `claude/v0422-update-failure-hotfix` holds no unmerged
product change (the released tree equals the branch tree) and is deleted
after this record merges; the untracked supplement checker copy is deleted
after this record; the supplement wheel stays under the ignored
`wom-kit/dist-v0422/` directory and is never committed.

Public release, local installed verification and source tests do not set
any feedback letter's `resolved_in`. For letters 161 and 162 the client AI
must install the v0.4.22 bootstrap wheel and, from the project root, run
`project-version-update <project-root> --resume --abandon-started-approval
--affirm-external-writers-quiescent` and then the plain `--resume` with the
bootstrap `archive` (the older project launcher does not know the flag) to
release the reservation, then one reviewed `--dry-run` and `--approve`; if
that run fails again, its `cause_code`, `cause_stage` and journal stage are
the evidence the next letter should carry. The carried rows (LR-06 session
integration, LR-02 through LR-05, LR-07, letter 160 ② and ④) are in the
v0.4.23 candidate, [PR #105](https://github.com/mow-coding/zettel-kasten/pull/105).
