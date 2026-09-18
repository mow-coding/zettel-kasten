# v0.4.25 release evidence and client boundary

Date: 2026-09-18 (Korea Standard Time)

Executing model: Claude Opus 5 (the session was switched from Claude Fable
5.1 after the Fable limit was reached during the first diagnostic workflow),
solo and sequential for the reproduction, the hotfix, the bump and every
release step, under the user's standing approval to run the release train
without re-asking. The user's direction: the client's update still did not
work after v0.4.24; fix it. The diagnosis and unit decisions are in the
[hotfix record](2026-09-18-v0425-archive-root-update-hotfix.md), the
[decision-log amendment](../wom-kit/docs/archive-infra-decision-log-2026-09-18-v0425-archive-root-update-hotfix.md)
and the acceptance register (UF-02).

## User intent and execution boundary

v0.4.25 fixes the project update started from the archive root: recorded
`parent_of_archive/.zettel-kasten/...` mirror, pin and receipt locations are
now resolved onto the project root by every consumer, so the post-approval
snapshot guard passes and `--resume` reopens the stuck transaction; and a
failure the service raises before any result carries its fixed `cause_code`
and journal `cause_stage`. Development used synthetic archives, temporary
repositories and local bare remotes only; no client runtime, archive,
feedback ledger, credential, provider configuration or shared PATH
installation was read or changed by this release execution.

## Reviewed source and CI

- [PR #110](https://github.com/mow-coding/zettel-kasten/pull/110)
  squash-merged exact head `25023622` into
  `815819d7b96bed67a02cb617e29dfc71f4997a2e`. The merge commit's tree
  `ca87d42b766a8349c6023595d2d56fc8844555e0` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35292231008):
  13 of 14 jobs passed on the first run; Windows shard 3/4 failed on one
  test unrelated to the hotfix
  (`test_git_backup_writer.test_pre_staged_later_group_is_preserved_by_first_exact_commit`,
  `git_backup_exact_add_failed` on the loaded runner at minute 40), which
  passes locally three times in a row on the hotfix tree; the failed shard
  was rerun at the same commit and passed. Recorded as the third CI flake
  beside the two from v0.4.21.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35299472580)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35299495813)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.24 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`815819d7`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI (run
35292231008, "Installed public entrypoints and workflow gate"). The copy is
not tracked and is deleted after this record.

The supplement passed every check: 169 packaged resources (733,571 bytes),
307 wheel members scanned (17,567,007 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.25; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.25` has tag object
`5146410f3b854c6ab497a07644ec7275185deec2` and remote peeled target
`815819d7b96bed67a02cb617e29dfc71f4997a2e`, equal to the main head.

[WOM-kit v0.4.25](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.25)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-18T02:51:07Z (2026-09-18 11:51 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.25-py3-none-any.whl` |
| Size | 3,200,734 bytes |
| SHA-256 | `3fb76fb590b94a891136e126e6ac536300cab9370dba9eb95794a40bd8d82256` |
| Verified package resources | 169 |
| Verified resource bytes | 733,571 |
| Scanned text-like wheel members | 307 |
| Scanned text-like bytes | 17,567,007 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 169 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.25` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.25")` returned
`exact_public_release_wheel_verified` from `public_github_release` with the
wheel name and digest, without any project or credential access; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Public wheel against the letter-161 state

The anonymously downloaded public wheel, installed into a fresh venv, was run
through the client's exact recovery sequence on the synthetic fixture that
reproduces letter 161 (pin v0.4.18; a v0.4.21 transaction created from the
archive root by the public v0.4.21 wheel, `lock_backlinked`, lock present,
claim `started`), from the archive root:
`--resume --abandon-started-approval --affirm-external-writers-quiescent`
returned `ok: true`, `preapproval_scaffold_cancelled` in one run (77 s);
`--target v0.4.25 --dry-run` returned `ready_for_approval`; `--approve`
showed one native dialog and returned `updated_restart_required` with the
pin at `v0.4.25` and no transaction directory left. Synthetic fixture only;
it proves the public artifact against that state, not the client's result.

## Cleanup and remaining work

The work branch `claude/v0425-archive-root-update-hotfix` and its worktree
hold no unmerged product change (the released tree equals the branch tree)
and are removed after this record merges; the untracked supplement checker
copy is deleted after this record; the supplement wheel stays under the
ignored `wom-kit/dist-v0425/` directory and is never committed.

Public release, local installed verification and source tests do not set
any feedback letter's `resolved_in`. Letter 161 ③ and ⑤ and the 2026-09-18
report close only when the client, from the same archive root and with this
bootstrap, runs `--resume --abandon-started-approval` to
`preapproval_scaffold_cancelled` and then one reviewed update to v0.4.25
that reaches `updated_restart_required` with the launcher reporting the new
pin in a new process. Deferred to a later release: the labelled public
`files_written` form, the pre-dialog `failed_rollback_incomplete` text
blocker, and a `--resume --dry-run` read-only preview.
