# Letter 139 v0.4.2 implementation and verification

Date: 2026-08-21 through 2026-08-22

## User direction and sequencing

The user reversed a temporary repository-privacy change and directed that the
public WOM repository remain public. The temporary private state had not been a
product requirement; it reflected embarrassment and concern that development
might have exposed sensitive information. The user also emphasized that beta
feedback was accumulating and asked for work that was complete without
unnecessary delay or repeated loops.

The execution order was therefore kept narrow:

1. verify that the repository was again public;
2. preserve and inspect Letter 139 read-only;
3. implement only the previously chosen v0.4.2 read-only planning slice;
4. perform independent security, privacy, version-surface, full-suite, and
   installed-wheel reviews before any merge or release;
5. keep destructive Git-history rewriting outside this release unless the user
   separately authorizes and plans it.

Letter 139's preserved SHA-256 is
`9a8b10a13bcd62dc6c4aec2a5763434e102203d6db7cfe11767b04218c02ccc9`.
The private beta archive and feedback source were not modified.

## Implemented v0.4.2 boundary

v0.4.2 adds two CLI-only commands:

- `git-backup-plan`;
- `git-backup-reconcile-plan`.

They perform a bounded, content-free local Git observation and an anonymous
HTTPS exact-ref observation. They bind the symbolic branch, HEAD, index,
tracked tree, staged/unstaged/untracked state, selected bounded byte evidence,
relevant Git configuration, receipt and handoff context, and two stable remote
observations. They reject unsupported repository forms, active operations and
locks, attributes/filters, unsafe paths or index entries, remote/configuration
ambiguity, observation drift, and exceeded bounds.

Both commands remain deliberately unable to write. Every result keeps
`ready_for_write: false`, `writer_available: false`, and `would_change: []`.
They expose no `--approve` path and no MCP writer. They do not add, commit,
fetch, pull, push, merge, rebase, reset, checkout, clean, delete, create a
receipt, or confirm a provider-side backup. Letter 139's exact file selection,
commit grouping, one-writer pause, commit/push, provider re-query, and
completion receipt remain future work.

## Independent security review loop

Independent review found and drove fixes for:

- inherited Git/proxy/askpass environment and remote-helper containment;
- repository attributes that could execute filters;
- target-ref, HEAD, remote-URL, and remote-ref drift;
- process-tree termination after direct-parent exit;
- false read/action claims in output;
- pinned Git executable identity and digest;
- missing remote target refs;
- entry, byte, blob, subprocess-output, and runtime bounds;
- all Git lock and in-progress-operation markers; and
- the documented conservative `.gitattributes` compatibility boundary.

The final independent implementation review reported no P0, P1, or P2
finding. It separately documented that same-user malicious ABA races are not
made atomic, Git-transport evidence is not provider-authenticity proof,
anonymous HTTPS is the only remote observer, and no writer exists.

## Public privacy review and checker repair

The current main snapshot and v0.4.2 candidate produced no secret-scanning
alert and no public-privacy-checker finding. This is evidence for the checked
patterns and snapshots, not proof that every possible secret format or external
credential validity has been tested.

The public privacy checker itself initially had unsafe failure behavior. It
could include matched snippets in logs, follow non-plain paths, inspect only the
worktree instead of the staged Git index, miss forced-tracked sensitive or
extensionless files, miss one quoted JSON credential-key form, accept Unicode
format-control log spoofing, run Git without complete output/runtime bounds,
and finish without rechecking the index snapshot. Independent adversarial
review reproduced each gap before it was fixed.

The repaired checker:

- emits fixed code/type/count/safe-relative-path metadata only;
- scans exact regular blobs in the Git index separately from the worktree;
- scans every tracked regular file regardless of suffix, including binary/NUL
  bytes, plus sensitive untracked candidates;
- rejects symlink, junction, reparse, non-plain, changing-file, and
  changing-index states;
- applies fixed entry, file, total-byte, Git-output, and runtime limits; and
- detects the covered GitHub, OpenAI, AWS, private-key, recovery-phrase,
  credential-URL, local-URL, and local-user-path shapes without printing the
  matched value or raw exception.

The final privacy-focused and release-readiness run completed 36 tests with one
ordinary Windows file-symlink case skipped because the host lacks symlink
privilege. The real Windows junction/reparse case passed, and the standalone
candidate check returned `PRIV000`.

## Historical local-path finding and decision boundary

The public Git history contains one class of non-credential privacy metadata:
old Windows user-home path text. It is absent from the current tree. The audit
found eight related commits, seven safe public paths, and twelve unique
commit/path/direction events; it found no POSIX home-path class. No actual
credential was identified in those matches.

Because the first occurrence is in the root history, complete removal would
rewrite approximately 503 mainline commits and 382 tags, invalidate old object
identities, require force updates, and require beta clients to re-clone or
carefully re-synchronize. It also cannot recall unknown existing clones or
caches. No history rewrite was authorized or attempted in this release.

The recommended non-destructive path is to keep the repository public, retain
the strengthened release gate, and treat historical path removal as a separate
human decision with a complete client-migration plan. On 2026-08-22 KST, the
user accepted that path for v0.4.2: keep the repository public, perform no
history rewrite in this release, and retain the old-path cleanup as a future
separately approved migration rather than forgetting or declaring it fixed.

## Required CI timeout correction

Pull request #75's first Required CI run used exact candidate head
`d5db46fb7fc9c187852161504aa0381abe940243`. The release-readiness gate and
seven of the eight platform/version shards passed. Windows Python 3.12 shard
2/4 continued making successful test progress until GitHub cancelled the job
at its configured limit. The exact GitHub annotation was
`The job has exceeded the maximum execution time of 45m0s`; the unittest step
ran for 44 minutes 33 seconds and reported no test failure before cancellation.
The aggregate Required CI job failed only because that required shard was
cancelled.

A same-commit failed-job rerun was started before changing source. Independent
comparison then showed that this was not a safe timeout margin: the equivalent
v0.4.1 success consumed 44 minutes 16 seconds of a 45-minute job, and the
current cancelled run was still progressing through the process-heavy MCP
suite. Continuing to depend on runner-speed luck would make both this release
and its records-only closeout flaky. The rerun was therefore intentionally
superseded rather than presented as release evidence.

The smallest correction changes only Windows shard 2/4 from a 45-minute job
limit to 75 minutes, matching the existing long-shard headroom. It does not
remove, skip, reorder, or weaken any test and does not change product runtime
behavior. A new exact-head Required CI run remains mandatory before merge.

## Verification evidence before merge

Completed local evidence at this checkpoint includes:

- 15 core Git-planner tests and 12 CLI/release-document tests in the independent
  security review;
- 210 pytest-native Windows/index/recovery tests;
- 286 changed-surface tests;
- 162 current-version capability/document tests;
- 36 privacy/release-readiness tests;
- the CI-equivalent four-shard unittest run: 3,471 tests passed and 38
  environment-specific or explicitly optional tests skipped;
- deterministic package-resource synchronization for 158 files;
- a clean-source wheel installation check reporting package version `0.4.2`,
  four working entrypoints, two byte-identical MCP inventories of 130 tools,
  the installed Letter 140 link smoke test, fixed-closed onboarding, and strict
  Doctor success.

The draft pull request, required GitHub CI, merge, annotated tag, public GitHub
Release, anonymous wheel retrieval, public upgrade/fresh-install checks, and
cleanup are intentionally not claimed here until they actually complete.

## Files and records

The implementation changed the v0.4.2 version surfaces, CLI parser and dispatch,
new Git planning module and tests, operator/install/capability documentation,
release note and packaged resource manifest, public privacy gate and tests, and
the version-current compatibility tests found during full-suite review.

The compact architecture decision is recorded in
`wom-kit/docs/archive-infra-decision-log-2026-08-21-v042-letter139-read-only-git-backup-planning.md`.
The earlier chronological start record remains
`meeting-minutes/2026-08-21-letter139-v042-git-backup-planning-start.md`.
