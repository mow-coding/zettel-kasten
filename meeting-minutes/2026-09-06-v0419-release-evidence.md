# v0.4.19 release evidence and client boundary

Date: 2026-09-06 (Korea Standard Time)

## User intent and execution boundary

The user asked to continue the approved recovery and operations train, not to
restart the plan or report command implementation as completed client recovery.
Finish one release's validation, public artifact and cleanup while preserving
unfinished work on the next version. Development uses synthetic archives only;
no client runtime, archive, feedback ledger, credential, provider or shared PATH
installation is changed by this release execution.

## Reviewed source and CI

- [PR #97](https://github.com/mow-coding/zettel-kasten/pull/97) merged exact head
  `344c37746ff3c3a11656bea75272ea03bb2dc2ef` into
  `591bb3ce131d32d89c3e9e269da581e9c3aec5a8`.
- The merge parents are the expected previous main
  `95e3a8b3a95b5ea3492d97dc56abd4fffe03dfb5` and the reviewed head.
  Candidate and merge share tree `2a9da0e328c65f9bcffe5f8e6c435940e423401b`.
- [Candidate CI](https://github.com/mow-coding/zettel-kasten/actions/runs/33980988848)
  passed all 14 jobs: Ubuntu Python 3.10/3.12 and Windows Python 3.12 shards,
  Doctor count/mixed scale, link-index scale, installed public workflow,
  release readiness and required aggregate.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/33984355557)
  and [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/33987538175)
  passed the configured readiness gate. The push policy skips the other jobs;
  these are not additional full-matrix runs.

## Exact-merge installation: failed observation and successful supplement

The clean exact-merge checkout used the committed installed-wheel checker.
The first local run exceeded its 1,200-second aggregate runtime-child budget
after reaching original repair resume. It remains `ok: false`, `harness_timeout`,
with product completion unknown. Its retained evidence SHA-256 is
`82eac18c085f8c4030a32d792284e089ad86803aff5d29ab11da8412fa77740f`.

The successful prefix included real update, healthy no-op, subsequent preview,
source/ref drift rejection, candidate preparation, forced interruption and
pre-switch preservation. Original resume started at 1,084.655 seconds, leaving
about 115 seconds. The same reviewed tree's hosted resume took about 189 seconds;
repeating the unchanged local envelope would not provide the missing tail.

Independent review approved a separately labeled local supplement: the full
unmodified checker ran with only its outer runtime-child limit changed to
2,400 seconds and its matching cumulative phase-observation ceiling. No product
validator, scenario, repair-child limit, Doctor limit, first-status/heartbeat
condition or required CI configuration changed. The original failed JSON was
not overwritten, and the released source contains no budget override.

The supplement completed in 1,854.782 seconds on CPython 3.12.10. It passed all
installed entrypoint and recovery checks, including real locked dependencies,
same-version no-download/no-approval behavior, source/ref drift refusal, actual
candidate repair, forced process loss, same-approval identifier-free resume,
independent repair revalidation and new-process launcher/Doctor checks.

Selected runtime observations (seconds):

| Observation | Seconds |
| --- | ---: |
| Initial update | 467.218 |
| Healthy no-op | 132.984 |
| Repair before forced interruption | 279.812 |
| Fresh-process original repair resume | 418.391 |
| Independent repaired-runtime no-op | 119.375 |
| Doctor first status | 0.157 |
| Doctor largest progress gap | 5.187 |
| Doctor terminal result | 19.250 |

This is a successful separate local supplement, not a retrospective pass of
the original local 1,200-second run. The official candidate gate passed without
this override. The installed synthetic workflow uses explicit test-only native
decisions and ephemeral authentication, not client credentials or provider data.

The exact checker source SHA-256 was
`0cd442f0cc42c5f871f94430319cafeb2cb22a5b45528a4ecd4d195f0abd16bc`;
runtime journey source SHA-256 was
`0a20be7fd7bfb1178e9f05c0ae5acfaa93b36049df2309867289480513bc2756`.

## Public artifact

Annotated tag `v0.4.19` has tag object
`1b0417057215eb3c7f30870e31a7cd1fdaf50a4a` and remote peeled target
`591bb3ce131d32d89c3e9e269da581e9c3aec5a8`.

[WOM-kit v0.4.19](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.19)
was uploaded as a draft with the tracked release notes and exactly one wheel.
The local digest and GitHub asset digest/size matched before publication at
2026-09-05T19:35:15Z; the release is neither draft nor prerelease.

| Artifact evidence | Value |
| --- | --- |
| Wheel | `wom_kit-0.4.19-py3-none-any.whl` |
| Size | 2,913,602 bytes |
| SHA-256 | `b23453975c3b235f02cdcf76017dd5846b506d49faf232ccc6b05ef30c1b017f` |
| Verified package resources | 169 |
| Verified resource bytes | 722,459 |
| Scanned text-like wheel members | 256 |
| Scanned text-like bytes | 16,305,264 |
| Secret-pattern matches | 0 |
| Windows user-path matches | 0 |

The anonymous public release API and unauthenticated wheel download succeeded;
downloaded bytes reproduced that digest. An external fresh venv installed the
downloaded wheel, passed `pip check`, verified all 169 installed resource sizes
and hashes and PEP 610 wheel hash, and returned `archive 0.4.19` in a new process.
That local-file installation proves artifact bytes, not the exact public URL
origin needed by project update. A separate fresh venv therefore installed the
exact public URL with its SHA-256 fragment, with pip's isolated configuration.
It passed dependencies, new-process version and all installed resource checks;
PEP 610 retained the exact public URL and digest. The actual installed
`bootstrap_wheel_for_target("v0.4.19")` accepted that origin and digest without
any project or credential access. This closes the real public bootstrap seam,
not a client runtime update or private-data recovery.

## Cleanup and remaining work

The completed implementation branch/worktree was removed after exact ancestry,
clean status and remote deletion checks. Its 171 ignored files were classified
generated bytecode/test caches; no unknown files were deleted. All source is
preserved in main and the remote. Unfinished v0.4.20 remains in its dedicated
worktree and is not an unnecessary or releasable artifact.

The release-evidence PR and its own cleanup are still in progress at this
record. Client execution is independently pending.
Public release, local installed verification and source tests do not set any
feedback letter's `resolved_in`. The client AI must use the exact public
bootstrap and project launcher, execute approved recovery, independently verify
it and provide the actual receipt. No counts, IDs or JSON preparation are
delegated to the human as manual work.
