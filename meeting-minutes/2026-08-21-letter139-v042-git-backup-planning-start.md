# Letter 139 v0.4.2 Git backup planning start

Date: 2026-08-21

## User intent and operating pressure

The user asked to keep the public repository public after reconsidering a
temporary privacy change. The reason for the temporary change was caution and
embarrassment rather than a product requirement: the user wanted confidence
that development had not accidentally published sensitive archive information.
The public/private decision therefore remains separate from the product rule
that archive bodies, private filenames, local paths, remote locators, and
credentials must not leak.

The user also emphasized that beta feedback is accumulating and asked for work
that is both complete and efficient. The resulting sequencing decision is:

1. close Letter 140 as the public v0.4.1 release, including release verification
   and cleanup;
2. immediately continue with Letter 139 as the v0.4.2 Git-backup planning track;
3. do not mix either release with the independent Letter 138 worktree.

v0.4.1 and its release-verification record were merged before this v0.4.2
worktree was created from the resulting `origin/main`.

## Preserved feedback evidence

The Letter 139 source was inspected read-only. Its exact SHA-256 is
`9a8b10a13bcd62dc6c4aec2a5763434e102203d6db7cfe11767b04218c02ccc9`.
No beta archive file was modified.

The letter reports one long-lived canonical archive worktree used by multiple
AI sessions. At the observation point it had two local-only commits and 5,609
uncommitted changes: 3,344 tracked changes and 2,265 untracked entries. These
numbers are historical operator evidence, not a state rechecked by this public
implementation worktree.

The requested product path is not a generic `git push`. It is a chain of:

1. inspect the real local Git state and exact configured-remote ref;
2. classify changes using WOM evidence without exposing content or private
   paths;
3. bind the exact local state, observed remote state, warnings, handoff evidence, and
   proposed effect set into a digest;
4. require one writer and an explicit human pause/review boundary;
5. commit only an approved file set;
6. push without automatic pull, merge, rebase, reset, force-push, or deletion;
7. re-query the provider through an authenticated adapter and write a completion
   receipt only if its exact ref points to the exact commit.

## v0.4.2 authority boundary

The earlier Letter 140 planning record already fixed v0.4.2 to the first safe
slice: read-only `git-backup-plan` and `git-backup-reconcile-plan` surfaces.
That boundary is retained.

v0.4.2 may contact the configured Git remote read-only to inspect the exact
target ref. It may inspect local Git metadata and hash the exact bytes of
changed regular files. It must cap all scans and subprocess output, suppress
prompts and raw Git errors, disable hooks and replacement objects, reject
unsafe repository indirection, and return only content-free change references,
counts, digests, fixed status codes, and fixed next actions.

v0.4.2 must not:

- add, commit, push, fetch, pull, merge, rebase, reset, checkout, clean, delete,
  or write a receipt;
- treat a cached remote-tracking ref or a successful subprocess exit as current
  provider proof;
- infer review or completion from a filename or modification time;
- echo a changed path, archive body, remote URL, credential, Git error, author,
  commit message, or private receipt path;
- convert unknown provenance, an unfinished transaction, a stale handoff, an
  unmerged index, a moving worktree, or a moving remote ref into `ready`;
- claim that Letter 139's commit/push/completion-receipt writer exists.

The future writer remains a later release decision. It must bind the unchanged
read-only plan and reconcile digests to an authenticated exact-human approval,
hold one archive-wide writer lock, revalidate immediately before each effect,
and provider-confirm the final ref before it can emit a completion receipt.

## Standards and implementation direction

The implementation follows Git's documented stable machine surfaces:

- NUL-delimited porcelain status for paths;
- explicit symbolic branch and exact commit-object queries;
- `rev-list --left-right --count` for divergence counts;
- `ls-remote --refs --exit-code` for the current Git-transport remote ref,
  without treating that observation as provider-confirmed completion;
- the repository-declared object format rather than assuming SHA-1.

The existing WOM project-update Git runner provides the starting security
boundary: inherited `GIT_*` redirection is removed, optional locks and terminal
prompts are disabled, hooks and replacement objects are disabled, output and
time are capped, and local repository metadata is required to be conventional,
real, and archive-contained. The Git-backup planner will reuse or tighten these
primitives rather than introduce a second permissive subprocess path.

## Verification loop

Implementation is complete only after focused adversarial tests cover at least:

- clean, ahead, behind, diverged, unborn, detached, shallow, bare, linked
  worktree, submodule, conflicted, staged, unstaged, untracked, ignored, rename,
  deletion, unusual filename, symlink/reparse, and changing-state cases;
- remote missing, target ref missing, timeout, authentication/network refusal,
  changed remote ref, unsafe transport/config, and raw-error redaction;
- deterministic digest and opaque-reference behavior;
- stale expected-plan and dimension-specific read-only reconciliation;
- zero writes locally and remotely;
- deliberate CLI-only exposure with no MCP or approval surface, packaged
  resources, privacy guards, full test suite, wheel install, public-release
  download, and fresh/upgrade verification.

Independent review must happen before release. A finding sends the plan back to
implementation and focused tests; it does not get waived for schedule pressure.
