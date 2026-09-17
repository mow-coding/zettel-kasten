# v0.4.21 release evidence and client boundary

Date: 2026-09-17 (Korea Standard Time)

Executing models: Claude Opus 5 at effort high, solo, for the units, the bump
and every release step; Claude Fable 5.1 (the user switched the session to
Fable 5.1 with Ultracode for a few hours) for the pre-merge review and its
corrections, using one bounded read-only review workflow (9 agents) and no
fan-out for any release step. All under the user's standing approval to
continue the v0.4.20 to v0.4.24 train and its releases without re-asking.

## User intent and execution boundary

The user asked to continue the train past v0.4.20 without stopping. v0.4.21
ships the LR-01 units (the eight writers that beta letters 157-160 reported
as regressions, reopened through operation-specific exact human approval, and
the one-approval `source-intake-chain`), the version bump, and the pre-merge
review corrections. LR-06 session integration and the older audit rows
LR-02 through LR-05 and LR-07 carry to v0.4.22 and later; that scope decision
is recorded in the acceptance register and the implementation record.
Development used synthetic archives, temporary repositories and local bare
remotes only; no client runtime, archive, feedback ledger, credential,
provider configuration or shared PATH installation was read or changed by
this release execution.

## Reviewed source and CI

- [PR #101](https://github.com/mow-coding/zettel-kasten/pull/101)
  squash-merged exact head `116eeef2` into
  `705360341001e26c453cf00fdc0151f6343bd6d4`. The merge commit's tree
  `ff9c970815ae9477e4b316114b1fb48262b9c6f8` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35140251745)
  passed all 14 jobs on that head with no rerun: Ubuntu Python 3.10/3.12 and
  Windows Python 3.12 shards, Doctor count/mixed scale, link-index scale,
  installed public workflow, release readiness and the required aggregate.
  Two earlier candidate runs on this branch found two stale test pins that
  the unit cohorts had not covered (`test_mcp_server` revision-plan status,
  `test_notion_property_backfill_cli` inventory counts; corrected in
  `fa1fa2f5`) and one Windows `test_git_backup_writer` runner flake (passed
  on a rerun of the failed job at the same commit; the test passes locally
  three times and its code is unchanged since v0.4.20).
- A bounded adversarial review of the release diff before merge confirmed
  six defects, all corrected in `459ba86c` before the final candidate run:
  the batch `identity_after_own_write` rule is now proven by the item
  writer's own fresh read against the digest of the bytes the batch wrote,
  the intake chain lists the capture step's durable writes when the capture
  reports failure and writes no chain receipt when nothing was written, and
  the packaged Runtime Skill operator contract plus the revision, discard
  and batch guides no longer describe the reopened writers as fixed closed.
  Evidence is in the implementation record.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35149815020)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35149879222)
  passed the configured readiness gate. The push policy skips the other
  jobs.

## Exact-merge installation: local supplement

The committed installed-wheel checker gives the real runtime journey a
1,200-second aggregate budget. On this machine the journey exceeds that
budget in every run (the update stage alone took 289 seconds here), exactly
as recorded for v0.4.19 and v0.4.20. The official candidate gate passed the
unmodified checker on the released tree in CI (run 35140251745, job
"Installed public entrypoints and workflow gate").

Following the v0.4.19 and v0.4.20 precedent, the release wheel was built and
verified from the clean exact-merge checkout (`70536034`) by a separately
named local copy of the checker that differs only in its outer runtime-child
limit (2,400 seconds) and the two matching ceilings; a byte comparison after
reversing those three edits reproduces the committed checker exactly. No
product validator, scenario, repair-child limit, Doctor limit or CI
configuration changed, and the copy is not tracked. It passed every check:
169 packaged resources (725,428 bytes), 304 wheel members scanned with 0
secret-pattern and 0 Windows user-path matches, all four installed
entrypoints, the letter-140, v0.4.9, v0.4.10, v0.4.11 and v0.4.14 installed
smoke programs, the v0.4.19 runtime journey, the runtime skill lifecycle and
strict Doctor on the checked-in fake archive.

Selected runtime observations (seconds, local supplement):

| Observation | Seconds |
| --- | ---: |
| Initial update | 288.094 |
| Healthy no-op | 92.062 |
| Repair before forced interruption | 181.672 |
| Fresh-process original repair resume | 277.109 |
| Independent repaired-runtime no-op | 87.594 |
| Doctor first status | 0.109 |
| Doctor largest progress gap | 5.156 |
| Doctor terminal result | 19.921 |

The committed checker source SHA-256 was
`c1c907bb4fed5a4d22585439892ad44f61b50dae2e56593d11122b2e351fa381`;
runtime journey source SHA-256 was
`5fe6e39dcb3187cd75b42fb4d1a5c02a4aadbf779fbebff0434746d0091db6f9`.

## Public artifact

Annotated tag `v0.4.21` has tag object
`a51ad79a75d6cdee2131a01093f1a4f81d7c4afe` and remote peeled target
`705360341001e26c453cf00fdc0151f6343bd6d4`, equal to the main head.

[WOM-kit v0.4.21](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.21)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and the GitHub asset digest and size matched before
publication at 2026-09-16T21:22:03Z (2026-09-17 06:22 KST); the release is
neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.21-py3-none-any.whl` |
| Size | 3,177,823 bytes |
| SHA-256 | `73f13ff73ca983b5ac196ca5d8f01b818c739becc1b1fc7eb09e8c79f46527db` |
| Verified package resources | 169 |
| Verified resource bytes | 725,428 |
| Scanned text-like wheel members | 304 |
| Scanned text-like bytes | 17,461,687 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest
byte for byte. A fresh venv installed the downloaded file, passed
`pip check`, verified all 169 installed resource sizes and hashes and the
PEP 610 wheel hash, and returned `archive 0.4.21` in a new process. A
separate fresh venv installed the exact public URL with its SHA-256
fragment under pip's isolated configuration and passed the same checks;
PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.21")` returned
`exact_public_release_wheel_verified` from `public_github_release` with the
wheel name and digest, without any project or credential access; the
local-file venv honestly reported
`running_distribution_not_from_exact_public_release_wheel`. This closes the
real public bootstrap seam, not a client runtime update or private-data
recovery.

## Cleanup and remaining work

The work-session worktree and branch are preserved until this evidence
record merges; they hold no unmerged product change (the released tree
equals the branch tree). The untracked local supplement checker copies are
deleted after this record.

Correction recorded after publication: the wheel from the pre-release
supplement run on `0d795a0c` (`wom-kit/dist-v0421/`, SHA-256 `b29c0ac9…`,
not the published bytes) was swept into commit `459ba86c` by a broad
`git add -A wom-kit` and is therefore part of the released tree and the
`v0.4.21` tag. It is a build artifact of public source only (the public
privacy hygiene gate and the wheel's own secret/user-path scans passed), it
is not packaged into any wheel, and it is not the published artifact. The
tag and history are not rewritten; the file is removed by a follow-up commit
and `dist-*/` is ignored from now on. The published wheel's provenance
above (built from the exact-merge checkout, digest `73f13ff7…`) is
unaffected.

Public release, local installed verification and source tests do not set
any feedback letter's `resolved_in`. The client AI must use the exact
public bootstrap and project launcher, run one reviewed project update,
and then run the reopened commands on the client's own archive: for the
regressions of letters 157-160 that means `discard-draft`, the
`zettel-edge`/`mint-zet`/`retire-draft` batches, `revert-batch` and
`zet-revision-write` with `--dry-run` first and `--approve --reviewed-by`
second, and for letter 160 ⑦ one `source-intake-chain` run in place of the
three-step chain, each with its actual receipt. No counts, IDs or JSON
preparation are delegated to a person. Carried to v0.4.22 and later: LR-06
session integration of the 30 pending writer paths, LR-02 through LR-05,
LR-07, a byte-hash fidelity mode for binary evidence originals (letter 160
②), and letter 160 ④ (unreproduced).
