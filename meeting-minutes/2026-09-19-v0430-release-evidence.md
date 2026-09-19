# v0.4.30 release evidence and client boundary

Date: 2026-09-19 (Korea Standard Time)

Executing model: Claude Opus 5, solo and sequential for the implementation,
the bump and every release step, under the user's standing approval to work
through the backlog without re-asking. The code map, unit design and two
adversarial verifications ran as one bounded read-only Ultracode workflow
(9 agents); no workflow agent touched a release step. The scope and unit
decisions are in the
[implementation record](2026-09-19-v0430-letter-163.md), the
[decision log](../wom-kit/docs/archive-infra-decision-log-2026-09-19-v0430-letter-163.md)
and the acceptance register (L163-01).

## User intent and execution boundary

v0.4.30 answers the core of the client's 2026-09-19 final report (beta
letter 163): the `mint-zet` fidelity gate that cost the client a day, the
listing and reviewed closing of the started claims those failures left, the
audit cap, the inbox backlog on write results, and the edge/draft frictions.
The user decided that the client receives one reply after this release is
public rather than three. Development used synthetic archives and temporary
repositories only; the client's letter was read from its feedback ledger;
no client runtime, archive, workspace, credential, provider configuration or
shared PATH installation was read or changed by this release execution, and
no client identifier appears in any repository file.

## Reviewed source and CI

- [PR #119](https://github.com/mow-coding/zettel-kasten/pull/119)
  squash-merged exact head `67242e37` into
  `6ff9fb89433ba9ef280c32a71e076a7024058914`. The merge commit's tree
  `722648ef67ccc3f999c52936024271ea4eb79df0` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- Two test-only correction commits preceded the green run: `acea5dd1`
  replaced a Windows-user-path canary in a mint test with a neutral string
  (the release readiness gate's public privacy hygiene check), and
  `b1feebcb` removed a helper block that a patch script had applied twice
  to `archive_services.py` (caught by the local full `test_cli` run and its
  duplicate-top-level-name guard). The
  [candidate run](https://github.com/mow-coding/zettel-kasten/actions/runs/35434404267)
  then failed one Windows shard twice on the Doctor operational-budget
  test (`test_v0419_doctor_fixture_contract`; it passes locally in 8 s and
  passed locally in the exact module order of that shard, 1,030 tests).
  A test-only commit `67242e37` made that assertion name the failed check
  and the timings; the run on that head passed all 14 jobs without a
  rerun, so the two failures stay recorded as an unreproduced CI-runner
  timing failure, now diagnosable if it recurs.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35438251457)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35438275947)
  passed the configured readiness gate.

## Exact-merge installation: local supplement

Following the v0.4.19 through v0.4.29 precedent, the release wheel was built
and verified from the clean exact-merge checkout (`6ff9fb89`) by an
untracked local copy of the installed-wheel checker that differs only in its
outer runtime-child limit (2,400 seconds) and the two matching ceilings;
reversing those three edits reproduces the committed checker byte for byte
(committed checker SHA-256
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`, copy
`68f796ce7b63a05c8c9c706dd9825197cae6816587830624ae39ce2bd15088b1`). The
official candidate gate passed the unmodified checker in CI. The copy is not
tracked and is deleted after this record.

The supplement passed every check: 173 packaged resources (750,971 bytes),
314 wheel members scanned (17,882,480 text-like bytes) with 0 secret-pattern
and 0 Windows user-path matches, all installed entrypoints (CLI and MCP
report 0.4.30; the two MCP inventories are byte-identical, 137 tools), the
letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed smoke programs,
the v0.4.19 real runtime journey, the runtime skill lifecycle and strict
Doctor on the checked-in fake archive; the temporary environment was removed
on exit.

## Public artifact

Annotated tag `v0.4.30` has tag object
`5fd03dac056c31606cfed47a7b7a5ff6c540bd17` and remote peeled target
`6ff9fb89433ba9ef280c32a71e076a7024058914`, equal to the main head.

[WOM-kit v0.4.30](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.30)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and size matched the GitHub asset digest and size before
publication at 2026-09-19T11:18:50Z (2026-09-19 20:18 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.30-py3-none-any.whl` |
| Size | 3,269,510 bytes |
| SHA-256 | `2fe2d46fe62d8ae0cd46dd86b75bd4fb74ce8cd0ea0df3665e424f9d70c936e1` |
| Verified package resources | 173 |
| Verified resource bytes | 750,971 |
| Scanned text-like wheel members | 314 |
| Scanned text-like bytes | 17,882,480 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest byte
for byte. A fresh venv installed the downloaded file, passed `pip check`,
verified all 173 installed resource sizes and hashes against the installed
manifest and the PEP 610 wheel hash, and returned `archive 0.4.30` in a new
process. A separate fresh venv installed the exact public URL with its
SHA-256 fragment under pip's isolated configuration and passed the same
checks; PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.30")` returned
`exact_public_release_wheel_verified` from `public_github_release`; the
local-file venv reported
`running_distribution_not_from_exact_public_release_wheel`.

## Cleanup and remaining work

The work branches `claude/v0430-letter-163` and `claude/v0430-letter-163-wip`
hold no unmerged product change (the released tree equals the branch tree);
they, the v0.4.28/v0.4.29 work branches and their worktrees, and the
superseded evidence PR #118 (folded into this record's PR) are removed after
this record merges; the untracked supplement checker copy is deleted; the
supplement wheels stay under the ignored `wom-kit/dist-v04xx/` directories
and are never committed.

Public release, local installed verification and source tests do not set
letter 163's `resolved_in` and do not close L163-01, which needs the
client's own `mint-zet`, `exact-approval-claims` and
`exact-approval-claim-finalize` runs. The reply draft now points the client
at v0.4.30 (which carries v0.4.28 and v0.4.29), gives the three commands
that close the 27 started claims, and asks for the index-rebuild sequence.
v0.4.31 (the letter's remainder) is designed; its decision log records what
the verifiers refuted.
