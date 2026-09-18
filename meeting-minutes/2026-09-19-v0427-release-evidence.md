# v0.4.27 release evidence and client boundary

Date: 2026-09-19 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the implementation,
the bump and every release step, under the user's standing approval to keep
working from the client's replies without re-asking. The scope and unit
decisions are in the
[implementation record](2026-09-18-v0427-client-followups.md) and the
acceptance register (CF-01).

## User intent and execution boundary

v0.4.27 answers the five message and input requests of the client's
2026-09-18 v0.4.25 success report: usage refusals of
`project-version-update` carry a fixed cause, a file-installed bootstrap is
pointed at the public URL, a refused permission grant reports the refused
position and the grantable names, intake plans accept a UTF-8 byte-order
mark, and the discard previews expose `plan_sha256` at the top level.
Development used synthetic fixtures only; the client report was read, and
no client runtime, archive, workspace, feedback ledger, credential, provider
configuration or shared PATH installation was read or changed by this
release execution.

## Reviewed source and CI

- [PR #114](https://github.com/mow-coding/zettel-kasten/pull/114)
  squash-merged exact head `3a158935` into
  `d39df7b07256aeea919028c4b92a0fe21de6cff9`. The merge commit's tree
  `5fce6a5a61bcf436e6bcfd4ebea5c54d522f0149` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35370352423)
  passed all 14 jobs on the first run with no rerun and no correction
  commit.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35379386266)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35379412158)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.26 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`d39df7b0`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after this record.

The supplement passed every check: 169 packaged resources (731,573 bytes),
307 wheel members scanned (17,569,486 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.27; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.27` has tag object
`3e679c6e0cf7f9b25c6ff806f55ef8d9b84d3398` and remote peeled target
`d39df7b07256aeea919028c4b92a0fe21de6cff9`, equal to the main head.

[WOM-kit v0.4.27](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.27)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-18T18:41:09Z (2026-09-19 03:41 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.27-py3-none-any.whl` |
| Size | 3,201,581 bytes |
| SHA-256 | `8abc91c8d3d5ca50a787b2e476b82206a908fa2eda7fb9aa407fc18328a25096` |
| Verified package resources | 169 |
| Verified resource bytes | 731,573 |
| Scanned text-like wheel members | 307 |
| Scanned text-like bytes | 17,569,486 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 169 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.27` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.27")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branch `claude/v0427-client-followups` and its worktree hold no
unmerged product change (the released tree equals the branch tree) and are
removed after this record merges; the untracked supplement checker copy is
deleted after this record; the supplement wheel stays under the ignored
`wom-kit/dist-v0427/` directory and is never committed.

Public release, local installed verification and source tests do not set
any feedback letter's `resolved_in`. CF-01 and UF-03 close only on the
client's own runs. The reply draft to the client now points at v0.4.27 with
the corrected approve command (the quiescence flag), answers each item of
the v0.4.25 report, and asks for the exact sequence behind the
index-rebuild block before that is changed. Recurring CI flake recorded for
a later fix: Windows shard 3/4
`test_git_backup_writer.test_pre_staged_later_group_is_preserved_by_first_exact_commit`.
