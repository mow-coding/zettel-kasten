# v0.4.29 release evidence and client boundary

Date: 2026-09-19 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the implementation,
the bump and every release step, under the user's standing approval to work
through the backlog without re-asking. The design map and adversarial
verifiers ran as one bounded read-only Ultracode workflow; no workflow agent
touched a release step. The scope and unit decisions are in the
[implementation record](2026-09-19-v0429-object-storage-offload.md), the
[decision log](../wom-kit/docs/archive-infra-decision-log-2026-09-19-v0428-v0429-object-restore-offload.md)
and the acceptance register (OB-02).

## User intent and execution boundary

v0.4.29 is the second half of the object-storage offload feature planned by
the 2026-09-04 decision log for v0.4.23: the way out
(`object-storage-offload`, OB-02), shipped one release after the way back so
that the first public offload is reversible. Development used synthetic
archives and temporary repositories only; no client runtime, archive,
workspace, feedback ledger, credential, provider configuration or shared PATH
installation was read or changed by this release execution.

## Reviewed source and CI

- [PR #117](https://github.com/mow-coding/zettel-kasten/pull/117)
  squash-merged exact head `8f6b42fe` into
  `424bfd81328b245459ee1551f26528d778a7bf56`. The merge commit's tree
  `7a09f4050722466c261e62cb6bdf6b7bc9aba58e` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- The first candidate run
  ([35419886259](https://github.com/mow-coding/zettel-kasten/actions/runs/35419886259),
  head `4ea49246`) failed one Ubuntu shard on one assertion: the POSIX
  runners add `object_storage_offload_platform_unsupported` to every blocked
  offload plan and `test_unreadable_fidelity_receipt_blocks_the_whole_plan`
  pinned the exact reason list. Correction commit `8f6b42fe` changed that
  test only; the rerun passed all 14 jobs.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35424949799)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35424981091)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.28 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`424bfd81`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after the v0.4.30 record.

The supplement passed every check: 171 packaged resources (740,946 bytes),
311 wheel members scanned (17,787,309 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.29; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.29` has tag object
`4804d74ac88464e4f53e709b98416dc76225c75e` and remote peeled target
`424bfd81328b245459ee1551f26528d778a7bf56`, equal to the main head.

[WOM-kit v0.4.29](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.29)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-19T06:20:22Z (2026-09-19 15:20 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.29-py3-none-any.whl` |
| Size | 3,246,524 bytes |
| SHA-256 | `679123d06ed671c6c04e3f7ec94da65351ad36a8cd75ad997a67c0f9e0d33bbe` |
| Verified package resources | 171 |
| Verified resource bytes | 740,946 |
| Scanned text-like wheel members | 311 |
| Scanned text-like bytes | 17,787,309 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 171 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.29` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.29")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branches `claude/v0429-object-storage-offload` and
`claude/v0429-object-storage-offload-wip` and their worktree hold no unmerged
product change (the released tree equals the branch tree) and are removed
after this record merges; the supplement wheel stays under the ignored
`wom-kit/dist-v0429/` directory and is never committed.

Public release, local installed verification and source tests do not set any
feedback letter's `resolved_in` and do not close OB-02, which needs the
client's own offload run after a restore on the same archive. v0.4.30 (beta
letter 163 core) is the next candidate, [PR #119](https://github.com/mow-coding/zettel-kasten/pull/119);
by the user's decision the client receives one reply after v0.4.30 is public.
