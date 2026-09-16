# v0.4.20 release evidence and client boundary

Date: 2026-09-16 (Korea Standard Time)

Executing model: Claude Opus 5 at effort high, solo (no agent fan-out), under
the user's standing approval to continue the v0.4.20 to v0.4.24 train and
its releases without re-asking.

## User intent and execution boundary

The user asked to finish the planned v0.4.20 work without stopping: the
bounded units after the Codex handoff, the version bump, and one public
release, while preserving the unfinished later-train work. Development used
synthetic archives, temporary repositories and local bare remotes only; no
client runtime, archive, feedback ledger, credential, provider configuration
or shared PATH installation was read or changed by this release execution.

## Reviewed source and CI

- [PR #99](https://github.com/mow-coding/zettel-kasten/pull/99) squash-merged
  exact head `b423d6bc8ab19b0ef194332b75eafd00d5d15e39` into
  `25a46efb3ad7884494bbe845f194d9f4d2c4b111`. The merge commit's tree
  `398ed9ba2ba8a745403364644a832f069ca05739` is identical to the branch
  head's tree, so the CI-verified source and the released source are the
  same bytes.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35027328853)
  passed all 14 jobs on that head: Ubuntu Python 3.10/3.12 and Windows
  Python 3.12 shards, Doctor count/mixed scale, link-index scale, installed
  public workflow, release readiness and the required aggregate. Two shards
  (Ubuntu py3.12 shard 2, Windows shard 3) passed on a rerun of the failed
  jobs at the same commit after environment flakes recorded in the
  implementation record; both tests pass locally and had passed on the two
  previous runs of the same code.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35038893896)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35041343868)
  passed the configured readiness gate. The push policy skips the other jobs.

The candidate's own installed-wheel gate found and blocked a real v0.4.20
defect before merge (plans without canonical zettel targets could not be
approved); the correction and its evidence are in the implementation record.

## Exact-merge installation: local supplement

The committed installed-wheel checker gives the real runtime journey a
1,200-second aggregate budget. On this machine the journey exceeds that
budget in every run (the update stage alone takes about 300 to 460 seconds
here against 169 seconds on the CI runner), exactly as recorded for
v0.4.19. The official candidate gate passed the unmodified checker on the
released tree in CI (run 35027328853, job "Installed public entrypoints and
workflow gate", 12 minutes 37 seconds).

Following the v0.4.19 precedent, the release wheel was built and verified
from the clean exact-merge checkout by a separately named local copy of the
checker that differs only in its outer runtime-child limit (2,400 seconds)
and the two matching ceilings; a byte comparison after reversing those three
edits reproduces the committed checker exactly. No product validator,
scenario, repair-child limit, Doctor limit or CI configuration changed, and
the copy is not tracked. It passed every check: 169 packaged resources,
303 wheel members scanned with 0 secret-pattern and 0 Windows user-path
matches, all installed entrypoints, the letter-140, v0.4.9, v0.4.10,
v0.4.11 and v0.4.14 installed smoke programs (including the locator apply
that the candidate gate had caught), the v0.4.19 runtime journey, the
runtime skill lifecycle and strict Doctor on the checked-in fake archive.

Selected runtime observations (seconds, local supplement):

| Observation | Seconds |
| --- | ---: |
| Initial update | 458.437 |
| Healthy no-op | 139.250 |
| Repair before forced interruption | 289.250 |
| Fresh-process original repair resume | 461.312 |
| Independent repaired-runtime no-op | 136.391 |
| Doctor first status | 0.110 |
| Doctor largest progress gap | 5.125 |
| Doctor terminal result | 29.563 |

The committed checker source SHA-256 was
`5d4132b404013eaf305c5dd29ad0fe4e5b4a8b1231d8a3d236d9bf74325a950d`;
runtime journey source SHA-256 was
`5fe6e39dcb3187cd75b42fb4d1a5c02a4aadbf779fbebff0434746d0091db6f9`.

## Public artifact

Annotated tag `v0.4.20` has tag object
`b65628d7de13fe90163da87103398706104247d1` and remote peeled target
`25a46efb3ad7884494bbe845f194d9f4d2c4b111`, equal to the main head.

[WOM-kit v0.4.20](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.20)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and the GitHub asset digest and size matched before
publication at 2026-09-16T00:46:02Z; the release is neither draft nor
prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.20-py3-none-any.whl` |
| Size | 3,150,282 bytes |
| SHA-256 | `42d6553f1f49ef2cdc03a0990974c4c00ad9a3a629123e888cb5b6e4a293d9e8` |
| Verified package resources | 169 |
| Verified resource bytes | 719,966 |
| Scanned text-like wheel members | 303 |
| Scanned text-like bytes | 17,308,568 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API (no token) reported one asset with that
size and digest, and an unauthenticated download reproduced the digest
byte for byte. A fresh venv installed the downloaded file, passed
`pip check`, verified all 169 installed resource sizes and hashes and the
PEP 610 wheel hash, and returned `archive 0.4.20` in a new process. A
separate fresh venv installed the exact public URL with its SHA-256
fragment under pip's isolated configuration and passed the same checks;
PEP 610 retained the exact public URL and digest. In that venv the
installed `bootstrap_wheel_for_target("v0.4.20")` returned
`exact_public_release_wheel_verified` from `public_github_release` with the
wheel name and digest and no URL echo, without any project or credential
access; the local-file venv honestly reported
`running_distribution_not_from_exact_public_release_wheel`. This closes the
real public bootstrap seam, not a client runtime update or private-data
recovery.

## Cleanup and remaining work

The work-session worktree and branch are preserved until this evidence
record merges; they hold no unmerged product change (the released tree
equals the branch tree). The untracked local supplement checker copy is
deleted after this record. `wom-kit/dist` is ignored and holds the uploaded
wheel bytes.

Public release, local installed verification and source tests do not set
any feedback letter's `resolved_in`. The client AI must use the exact
public bootstrap and project launcher, run one reviewed project update,
re-run `mint-zet --dry-run` on the drafts that v0.4.18 left unmintable, and
provide the actual receipt. No counts, IDs or JSON preparation are delegated
to the human as manual work.

Still open after this release: the 21 pending writer-session paths, the
intake-chain approval batching planned for v0.4.21 (letter 160), the
deterministic diagnosis of the two CI flakes recorded in the implementation
record, and duration-weighted CI shard balancing.
