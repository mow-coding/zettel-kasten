# v0.4.24 release evidence and client boundary

Date: 2026-09-18 (Korea Standard Time)

Executing model: Claude Fable 5.1, solo and sequential for every unit, the
bump and every release step (the only agent use was one bounded read-only
code map before the design), under the user's standing approval to run the
v0.4.20 to v0.4.24 train and its releases without re-asking. The user's
direction for this release was to ship the session permission modes he
decided on and only then send the combined client reply ("v0.4.24까지 하고
회신을 하자"); the design and unit decisions are in the
[implementation record](2026-09-18-v0424-session-permission-modes-implementation.md),
the
[decision-log amendment](../wom-kit/docs/archive-infra-decision-log-2026-09-18-v0424-session-permission-modes.md)
and the acceptance register (SP-01).

## User intent and execution boundary

v0.4.24 ships per-work-session permission modes — `manual`, `limited`,
`allow_all` — granted by one exact human decision on the claimed session
(`work-session --action set-permission-mode --approve`). A write the mode
permits opens no native dialog but still publishes its own one-use claim
bound to its exact plan and target digests; the claim records
`interactive_intent.mechanism = work_session_permission_mode`, results carry
`approval_mechanism` and `live_dialog_shown`, and the five-key receipt
reference is unchanged. Project updates, remote providers, the session
lifecycle, repairs, overrides and credential writes always ask; pause,
complete, handoff, accept and recover clear the grant; a grant revoked before
claim publication fails closed. Development used synthetic archives,
temporary repositories and local bare remotes only; no client runtime,
archive, feedback ledger, credential, provider configuration or shared PATH
installation was read or changed by this release execution.

## Reviewed source and CI

- [PR #108](https://github.com/mow-coding/zettel-kasten/pull/108)
  squash-merged exact head `83c1a733` into
  `17ab3940981d50b6d205018c6bf33a2123c5a4b5`. The merge commit's tree
  `101762e7bcebf72e03b3e8da81121792e2f6ab6f` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35263914446)
  passed all 14 jobs on that head on the first run, with no rerun and no
  correction commit. Before the candidate, the local session, approval-broker
  and recent exact-approval cohort (1,039 tests) found one stale pin, the
  broker-core signature list, which gained the new `session_permission`
  parameter; the bump cohort found the pins the sweep cannot reach (Korean
  previous-baseline line, the runtime-status f-string, the MCP and resource
  canonical digests in two tests), all recorded in the implementation
  record.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35273477792)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35273513189)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.23 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`17ab3940`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI (run
35263914446, "Installed public entrypoints and workflow gate"). The copy is
not tracked and is deleted after this record.

The supplement passed every check: 169 packaged resources (733,826 bytes),
307 wheel members scanned (17,561,888 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.24; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.24` has tag object
`ec34ed9cdf345f80e6116a90f399a1747634986f` and remote peeled target
`17ab3940981d50b6d205018c6bf33a2123c5a4b5`, equal to the main head.

[WOM-kit v0.4.24](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.24)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-17T21:24:37Z (2026-09-18 06:24 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.24-py3-none-any.whl` |
| Size | 3,199,441 bytes |
| SHA-256 | `44f964abc601f2d858e84586f112f4d65f1ab58dd3a88f708b8f8c89b23367b0` |
| Verified package resources | 169 |
| Verified resource bytes | 733,826 |
| Scanned text-like wheel members | 307 |
| Scanned text-like bytes | 17,561,888 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 169 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.24` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.24")` returned
`exact_public_release_wheel_verified` from `public_github_release` with the
wheel name and digest, without any project or credential access; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branch `claude/v0424-session-permission-modes` and its worktree
hold no unmerged product change (the released tree equals the branch tree)
and are removed after this record merges; the untracked supplement checker
copy is deleted after this record; the supplement wheel stays under the
ignored `wom-kit/dist-v0424/` directory and is never committed.

Public release, local installed verification and source tests do not set
any feedback letter's `resolved_in`. Letter 161 request 6 (session-scope
pre-approval) closes only when the client grants a mode on its own claimed
session and observes a permitted write run without a dialog while its
receipt still names a claim; letter 160's popup count closes only against
the client's own measurement on v0.4.24. The user's open question — whether
project updates and credential writes should also skip under `allow_all` —
stays answered by the recorded default (they always ask) until he decides
otherwise. Carried to v0.4.25 and later: session integration of the 29
remaining pending writer paths, MCP exposure of the create-draft session
refs, a per-command runtime mode report in `capabilities --machine`, and the
combined reply to letters 157 through 162, which the user sends himself
from the prepared draft.
