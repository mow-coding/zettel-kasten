# v0.4.34 release evidence and client boundary

Date: 2026-09-20 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the implementation,
the bump and every release step, under the user's standing approval to work
through the backlog without re-asking. The scope and unit decisions are in
the [implementation record](2026-09-20-v0434-letter-165.md), the
[decision log](../wom-kit/docs/archive-infra-decision-log-2026-09-20-v0434-letter-165.md)
and the acceptance register (L165-01).

## User intent and execution boundary

v0.4.34 answers the whole of beta letter 165: presenter-bound, time-boxed
session grants with presenter evidence in every grant claim, the legacy
identifier warning on every new-record surface, the feedback body write
under exact approval, the announced revise path and the revision-plan
warning explanations. Development used synthetic archives and the injected
dialog and key only; the client's letter was read from its feedback ledger;
no client runtime, archive, workspace, credential, provider configuration
or shared PATH installation was read or changed by this release execution,
and no client identifier appears in any repository file.

## Reviewed source and CI

- [PR #125](https://github.com/mow-coding/zettel-kasten/pull/125)
  squash-merged exact head `59839982` into
  `3b0dc70d53fa4f3b5bce30b3d92a36435d90e4d4`. The merge commit's tree
  `f572ad5516aeef767297f5c503a048a67a280e6a` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- The [candidate run](https://github.com/mow-coding/zettel-kasten/actions/runs/35478881369)
  passed all 14 jobs (first attempt, no reruns).
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35483015709)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35483021307)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.33 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`3b0dc70d`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after this record.

The supplement passed every check: 173 packaged resources (754926 bytes),
318 wheel members scanned (18106051 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.34; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.34` has tag object
`79dad935c0698830e74e8b33a17b21fa96e82eda` and remote peeled target
`3b0dc70d53fa4f3b5bce30b3d92a36435d90e4d4`, equal to the main head.

[WOM-kit v0.4.34](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.34)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-20T02:24:43Z (2026-09-20 11:24 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.34-py3-none-any.whl` |
| Size | 3323899 bytes |
| SHA-256 | `fa9f6b2cdeff88a3fb07e70fa51d4a632f7e4ba9e971ae65b5f1dcfae3f0b49e` |
| Verified package resources | 173 |
| Verified resource bytes | 754926 |
| Scanned text-like wheel members | 318 |
| Scanned text-like bytes | 18106051 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 173 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.34` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.34")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branch `claude/v0434-letter-165` holds no unmerged product change
(the released tree equals the branch tree) and is removed after this record
merges together with the v0.4.32 and v0.4.33 work branches and worktrees;
the untracked supplement checker copy is deleted; the supplement wheel stays
under the ignored `wom-kit/dist-v0434/` directory and is never committed.

Public release, local installed verification and source tests do not set
letter 165's `resolved_in` and do not close L165-01, which needs the
client's own runs (a fresh grant, a write under it, the claim's presenter
block). The combined letters 164+165 reply draft points the client at
v0.4.34, answers every item of both letters and asks four questions; the
user sends it.
