# v0.4.23 release evidence and client boundary

Date: 2026-09-18 (Korea Standard Time)

Executing model: Claude Fable 5.1, solo and sequential for every unit, the
bump and every release step (no agent fan-out), under the user's standing
approval to run the v0.4.20 to v0.4.24 train and its releases without
re-asking. The user's direction for this release was to finish the work
carried from v0.4.21 before the combined client reply; the scope and unit
decisions are in the
[implementation record](2026-09-17-v0423-carried-work-implementation.md)
and the acceptance register.

## User intent and execution boundary

v0.4.23 ships the carried rows: a binary original as the fidelity source of a
summary or derivative draft (beta letter 160 ②), `create-draft` bound to a
claimed work session (LR-06a, the first native writer), the letter 160 ④
reproduction (not confirmed, no code change) and the revalidation of LR-02
through LR-05 and LR-07 against their existing domain cohorts. The session
permission modes the user decided on (manual, limited, allow-all per work
session) are the first unit of v0.4.24, not part of this release.
Development used synthetic archives, temporary repositories and local bare
remotes only; no client runtime, archive, feedback ledger, credential,
provider configuration or shared PATH installation was read or changed by
this release execution.

## Reviewed source and CI

- [PR #105](https://github.com/mow-coding/zettel-kasten/pull/105)
  squash-merged exact head `e5a9e822` into
  `ad0738f397f0b9d0e7313d64745d4e95123531f3`. The merge commit's tree
  `b7853ec3f67ad359a7d9d8e1239eebebbe57a4bd` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35232797958)
  passed all 14 jobs on that head with no rerun. The first candidate run on
  this branch found that the CI runner loads `wom-kit/tests` as bare modules,
  so the new fidelity test's `import tests.<module>` failed there while the
  local cohort (run with the tests package on the path) had passed; the
  import was changed to the bare module name every other test uses
  (`080c95ae`). The runs on the earlier heads were cancelled by the
  workflow's cancel-in-progress policy when the correction and the merge of
  main were pushed.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35243294661)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35243336611)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.22 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`ad0738f3`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`). The
official candidate gate passed the unmodified checker in CI (run
35232797958, "Installed public entrypoints and workflow gate"). The copy is
not tracked and is deleted after this record.

The supplement passed every check: 169 packaged resources (733,244 bytes),
305 wheel members scanned (17,518,157 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints, the letter-140,
v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs, the v0.4.19
real runtime journey, the runtime skill lifecycle and strict Doctor on the
checked-in fake archive; the temporary environment was removed on exit.

## Public artifact

Annotated tag `v0.4.23` has tag object
`6ddd58209269e116402ee410c6180355f2f87c5f` and remote peeled target
`ad0738f397f0b9d0e7313d64745d4e95123531f3`, equal to the main head.

[WOM-kit v0.4.23](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.23)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-17T16:16:35Z (2026-09-18 01:16 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.23-py3-none-any.whl` |
| Size | 3,189,008 bytes |
| SHA-256 | `f90e72402b5dfac51658ed332308b18e43a10a78349a3cca71f0f820580d818c` |
| Verified package resources | 169 |
| Verified resource bytes | 733,244 |
| Scanned text-like wheel members | 305 |
| Scanned text-like bytes | 17,518,157 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 169 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.23` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.23")` returned
`exact_public_release_wheel_verified` from `public_github_release` with the
wheel name and digest, without any project or credential access; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branch `claude/v0423-carried-work` and its worktree hold no
unmerged product change (the released tree equals the branch tree) and are
removed after this record merges; the untracked supplement checker copy is
deleted after this record; the supplement wheel stays under the ignored
`wom-kit/dist-v0423/` directory and is never committed.

Public release, local installed verification and source tests do not set
any feedback letter's `resolved_in`. Letter 160 ② closes only when the
client creates one summary or derivative draft over a real binary original
on v0.4.23; letter 160 ④ stays unreproduced until the client's next
occurrence reports its printed reason codes; the session-bound `create-draft`
is verified on the client side only by a run with the client's own
registered app, task route and claimed session. Carried to v0.4.24: the
session permission modes (unit 1), session integration of the 29 remaining
pending writer paths, and MCP exposure of the create-draft session refs.
