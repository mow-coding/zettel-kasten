# v0.4.31 release evidence and client boundary

Date: 2026-09-19 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the implementation,
the bump and every release step, under the user's standing approval to work
through the backlog without re-asking. The scope and unit decisions are in
the [implementation record](2026-09-19-v0431-letter-163-remainder.md), the
[decision log](../wom-kit/docs/archive-infra-decision-log-2026-09-19-v0431-letter-163-remainder.md)
and the acceptance register (L163-02).

## User intent and execution boundary

v0.4.31 finishes the letter-163 items that survived adversarial review
(create-draft hints, gating edge-target warnings, warning explanations, the
preflight cause family with the existing-transaction shape, and the index
pre-announce). Development used synthetic archives and temporary
repositories only; no client runtime, archive, workspace, credential,
provider configuration or shared PATH installation was read or changed by
this release execution, and no client identifier appears in any repository
file.

## Reviewed source and CI

- [PR #121](https://github.com/mow-coding/zettel-kasten/pull/121)
  squash-merged exact head `8f7d19f5` into
  `ff9fed875ed09b3cc40a8cda1effce6b66af918d`. The merge commit's tree
  `4e0ff69c874ab39e11c8dae7d8d0cfb62512b465` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- One correction commit preceded the green run: `8f7d19f5` removed two
  duplicate definitions of `archive_index_precheck` that a patch script
  had applied three times to `archive_services.py` (caught by the local full
  `test_cli` run and its duplicate-top-level-name guard; the release's
  patch-script rule now checks for a prior application first). The
  [candidate run](https://github.com/mow-coding/zettel-kasten/actions/runs/35444413930)
  on that head passed all 14 jobs on its first attempt.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35448077596)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35448108388)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.30 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`ff9fed87`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after this record.

The supplement passed every check: 173 packaged resources (750323 bytes),
314 wheel members scanned (17902564 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.31; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.31` has tag object
`2d3e3a8ce95440ed264fce3b4099dc967dff47e9` and remote peeled target
`ff9fed875ed09b3cc40a8cda1effce6b66af918d`, equal to the main head.

[WOM-kit v0.4.31](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.31)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-19T14:38:26Z (2026-09-19 23:38 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.31-py3-none-any.whl` |
| Size | 3274545 bytes |
| SHA-256 | `7a3e2e76ed03253e996dfa455f657a62f18651a31a403be054dc98c1f628decb` |
| Verified package resources | 173 |
| Verified resource bytes | 750323 |
| Scanned text-like wheel members | 314 |
| Scanned text-like bytes | 17902564 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 173 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.31` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.31")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branch `claude/v0431-letter-163-remainder` holds no unmerged
product change (the released tree equals the branch tree) and is removed
after this record merges; the untracked supplement checker copy is deleted;
the supplement wheel stays under the ignored `wom-kit/dist-v0431/` directory
and is never committed.

Public release, local installed verification and source tests do not set
letter 163's `resolved_in` and do not close L163-02, which needs the
client's own runs. v0.4.32 (the first half of beta letter 164) is
implemented and bumped on its own branch and follows this record; the
client receives one reply after v0.4.32 is public, per the user's
one-reply practice.
