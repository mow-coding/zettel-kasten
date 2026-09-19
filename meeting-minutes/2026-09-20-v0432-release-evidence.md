# v0.4.32 release evidence and client boundary

Date: 2026-09-20 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the implementation,
the bump and every release step, under the user's standing approval to work
through the backlog without re-asking. The scope and unit decisions are in
the [implementation record](2026-09-19-v0432-letter-164.md), the
[decision log](../wom-kit/docs/archive-infra-decision-log-2026-09-19-v0432-letter-164.md)
and the acceptance register (L164-01).

## User intent and execution boundary

v0.4.32 answers the four bounded read-side findings of beta letter 164
(the byte-stream finalize scanner, the update snapshot's probe failure
kinds, the content-free Git backup attention and the permission-mode
preview) and states the closed `object-storage-upload` boundary the client
asked for. Development used synthetic archives and temporary repositories
only; the client's letter was read from its feedback ledger; no client
runtime, archive, workspace, credential, provider configuration or shared
PATH installation was read or changed by this release execution, and no
client identifier appears in any repository file.

## Reviewed source and CI

- [PR #122](https://github.com/mow-coding/zettel-kasten/pull/122)
  squash-merged exact head `d82fd5ed` into
  `3ee73588ea497f3b4fb33c209d50261abdfdbfe5`. The merge commit's tree
  `9997148a7ffb9f184ebfe3a53da1440fe7bd3357` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- The [candidate run](https://github.com/mow-coding/zettel-kasten/actions/runs/35462514932)
  passed all 14 jobs (first attempt, no reruns).
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35468091368)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35468111840)
  passed the configured readiness gate.
- This is the first release after the approved rewrite of the public
  history (recorded in the
  [history-rewrite minutes](2026-09-20-public-history-rewrite.md)); the
  commit ids in this record are post-rewrite ids.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.31 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`3ee73588`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after this record.

The supplement passed every check: 173 packaged resources (751611 bytes),
315 wheel members scanned (17933510 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.32; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.32` has tag object
`d122801e12716a3fc72fe53440184f8b182282a2` and remote peeled target
`3ee73588ea497f3b4fb33c209d50261abdfdbfe5`, equal to the main head.

[WOM-kit v0.4.32](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.32)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-19T21:06:25Z (2026-09-20 06:06 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.32-py3-none-any.whl` |
| Size | 3283246 bytes |
| SHA-256 | `272211f9ce1264fb711bbf96cd0ba92d518534438d2f4224fd128f42c37a7503` |
| Verified package resources | 173 |
| Verified resource bytes | 751611 |
| Scanned text-like wheel members | 315 |
| Scanned text-like bytes | 17933510 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 173 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.32` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.32")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branch `claude/v0432-letter-164` holds no unmerged product change
(the released tree equals the branch tree) and is removed after this record
merges together with the earlier v0.4.28–v0.4.31 work branches and
worktrees; the untracked supplement checker copy is deleted; the supplement
wheel stays under the ignored `wom-kit/dist-v0432/` directory and is never
committed.

Public release, local installed verification and source tests do not set
letter 164's `resolved_in` and do not close L164-01, which needs the
client's own runs. The letter-164 reply draft points the client at v0.4.32
(which carries v0.4.31), answers the nine findings, names the existing
one-approval commit+push route and asks three questions; v0.4.33 (the
upload writer under exact approval) is designed next.
