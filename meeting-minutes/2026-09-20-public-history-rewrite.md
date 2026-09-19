# Public history rewrite — 2026-09-20 (approved 2026-09-19)

Date: executed 2026-09-20 02:00–02:20 KST; approved by the user on 2026-09-19.

Executing model: Claude Opus 5, solo and sequential. No client folder, archive
or ledger was read or changed; the only inputs were the public repository's
own history and two private replacement lists kept outside the repository.

## Why

On 2026-09-19 the user asked whether any private local folder name had ever
reached the public showcase repository. The answer for the current files was
no (the release readiness gate `tools/check_public_privacy.py` and the
release-docs privacy tests enforce it). The answer for the history was yes:
two commits from 2026-07-30 carried the user's Windows account folder name
inside an absolute path, and the client's workspace folder name (which
contains the client's id) appeared in a small number of files from
2026-07-30 until 2026-08-29. The user judged that a private local folder
name must not remain visible in a public place even historically, and
approved rewriting the public history.

## What was done

1. A fresh `--mirror` clone of the public repository was scanned: 12,642
   blobs and every commit message, author and committer line, for the two
   private strings in any letter case. Before the rewrite: 884 blobs and
   4 message fields matched.
2. `git filter-repo` 2.47.0 ran twice over the mirror with `--replace-text`
   and `--replace-message` (one pass for the exact strings and their path
   forms, one for the remaining case variants), replacing every occurrence
   with the placeholders `<user>` / `<client>`. Dates, authorship and the
   commit graph were kept.
3. After the rewrite the same scan found 0 matching blobs and 0 matching
   message fields.
4. Tree check: `main` and every branch head kept a byte-identical tree; 267
   refs are identical, including every tag from v0.4.14 to v0.4.31 and all
   v0.2.x / v0.3.0–v0.3.157 tags. 180 tags (v0.3.158 through v0.4.13) point
   at commits whose trees changed only by the placeholder substitution.
5. The repository ruleset `main-required-ci` (rules: deletion,
   non_fast_forward, pull_request, required_status_checks) blocks force
   pushes, so its enforcement was set to `disabled` for the duration of one
   `git push --force` of `refs/heads/*` and `refs/tags/*`, then set back to
   `active`; the rule set was verified unchanged afterwards. Pull-request
   refs (`refs/pull/*`, 121 of them) are GitHub-owned and were not pushed.
6. Post-push verification: every branch and tag on GitHub equals the
   rewritten mirror; the four GitHub Releases (v0.4.28–v0.4.31) still
   resolve their tags and assets (release assets are stored by release, not
   by commit, and their digests are unchanged).

## Commit-id mapping for the records

Every record written before this rewrite (release evidence minutes, the
acceptance register, decision logs) names pre-rewrite commit ids. They stay
as written; this table maps the ones that matter. Trees are identical in
every row.

| Ref | Before | After |
| --- | --- | --- |
| `main` (evidence merge #120) | `cea979b2` | `b97fe8ba` |
| `v0.4.31` (main `ff9fed87`, tag object `2d3e3a8c`) | `ff9fed87` / `2d3e3a8c` | `4641fd1a` / `be646f03` |
| `v0.4.30` (main `6ff9fb89`, tag object `5fd03dac`) | `6ff9fb89` / `5fd03dac` | `db0da930` / `bdda6751` |
| `v0.4.29` (main `424bfd81`, tag object `4804d74a`) | `424bfd81` / `4804d74a` | `daf0fef3` / `89814f44` |
| `v0.4.28` (main `4a78cd7c`, tag object `31b2c11f`) | `4a78cd7c` / `31b2c11f` | `0f485337` / `4a7f8687` |

The complete 902-row commit map is kept privately by the user (it is not a
repository file).

## What remains outside our control

GitHub keeps unreachable objects and the `refs/pull/*` heads until its own
garbage collection and a support request; the pre-rewrite commit ids may
therefore still resolve by direct URL for a while. The user files the
support request (text prepared separately) asking GitHub to remove cached
views and unreachable objects for this repository. Forks and clones made
before 2026-09-20 carry the old history; none are known.

## Local follow-up

Every local checkout and worktree was re-synchronised (`fetch --prune
--prune-tags --force`, `reset --hard origin/main`); the in-progress v0.4.32
branch was rebased onto the rewritten `main` with `git rebase --onto`
(commit ids changed, trees did not); the merged work branches and the
mirror are deleted after the v0.4.32 release.
