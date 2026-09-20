# v0.4.33 release evidence and client boundary

Date: 2026-09-20 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the implementation,
the bump and every release step, under the user's standing approval to work
through the backlog without re-asking. The scope and unit decisions are in
the [implementation record](2026-09-20-v0433-upload-exact.md), the
[decision log](../wom-kit/docs/archive-infra-decision-log-2026-09-20-v0433-upload-exact.md)
and the acceptance register (L164-02).

## User intent and execution boundary

v0.4.33 reopens `object-storage-upload` under the exact approval contract
(beta letter 164 ①③④) as the composition of the v0.4.13 preservation PUT
and the formal-adoption manifest projection under one dialog. Development
used synthetic archives and an in-memory transport only; the client's
letter was read from its feedback ledger; no client runtime, archive,
workspace, credential, provider configuration or shared PATH installation
was read or changed by this release execution, and no client identifier
appears in any repository file.

## Reviewed source and CI

- [PR #123](https://github.com/mow-coding/zettel-kasten/pull/123)
  squash-merged exact head `3a96105c` into
  `088cceae9ecf40b9a46d103c1bcefc0f75580415`. The merge commit's tree
  `e6c6c3649a3b780c5a61341139b7a5e2a071ae46` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- The [candidate run](https://github.com/mow-coding/zettel-kasten/actions/runs/35473826152)
  passed all 14 jobs (first attempt, no reruns).
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35477747654)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35477758845)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.32 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`088cceae`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after this record.

The supplement passed every check: 173 packaged resources (751048 bytes),
316 wheel members scanned (18024347 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.33; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.33` has tag object
`96a48adf7d47df59206518933038299ed53ed07c` and remote peeled target
`088cceae9ecf40b9a46d103c1bcefc0f75580415`, equal to the main head.

[WOM-kit v0.4.33](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.33)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-20T00:23:40Z (2026-09-20 09:23 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.33-py3-none-any.whl` |
| Size | 3300358 bytes |
| SHA-256 | `f08a56b3861a103b1cf1ec0cbd2a3bfb1d271669621d23a22007626baf7914cb` |
| Verified package resources | 173 |
| Verified resource bytes | 751048 |
| Scanned text-like wheel members | 316 |
| Scanned text-like bytes | 18024347 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 173 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.33` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.33")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branch `claude/v0433-upload-exact` holds no unmerged product change
(the released tree equals the branch tree) and is removed after this record
merges; the untracked supplement checker copy is deleted after the v0.4.34
release; the supplement wheel stays under the ignored `wom-kit/dist-v0433/`
directory and is never committed.

Public release, local installed verification and source tests do not set
letter 164's `resolved_in` and do not close L164-02, which needs the
client's own live upload. The combined letters 164+165 reply draft points
the client at v0.4.34 (which carries v0.4.32 and v0.4.33).
