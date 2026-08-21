# Git Backup Plan And Reconciliation Plan

Status: v0.4.2 read-only planning boundary

This guide explains the two v0.4.2 Git backup planning commands in plain
language. They help an operator understand a large, mixed local Git state
before deciding how to group, review, commit, and push it. They do not make
that decision and they do not perform the backup.

## The Short Version

Run `git-backup-plan` to take a bounded, privacy-preserving observation of one
Git worktree and its exact target branch. Run `git-backup-reconcile-plan` to
repeat that observation and compare the current state with a previously
reviewed plan digest.

Both commands are intentionally read-only:

| Surface | What v0.4.2 does | What v0.4.2 does not do |
| --- | --- | --- |
| Local Git | inspect HEAD, index, worktree, configuration state, and bounded file evidence | add, restore, reset, checkout, commit, merge, rebase, delete, or create a branch |
| Remote Git | query one exact branch ref through a bounded non-interactive Git transport | fetch, pull, push, create/delete a ref, or change remote configuration |
| Archive | read bounded metadata and evidence needed to stabilize the plan | edit archive content, receipts, handoff records, locks, or configuration |
| Authority | return a deterministic content-free plan digest | approve a writer or turn an old plan into write authority |

Every result keeps these fields fixed:

```json
{
  "ready_for_write": false,
  "writer_available": false,
  "would_change": []
}
```

`inspection_complete` means only that the read-only inspection completed. It
never means that a commit exists, a push succeeded, or a remote backup was
verified.

## First Observation

Use a fresh v0.4.2 process and start with the default `origin` remote and the
branch named by symbolic HEAD:

```powershell
archive git-backup-plan <archive-root> `
  --remote origin `
  --dry-run `
  --format json
```

Use `--branch <branch-name>` only to reaffirm the currently checked-out
symbolic branch explicitly. A different branch blocks because the current
index and worktree do not represent that other branch. Do not pass a full
`refs/heads/...` ref. The command validates the branch name with Git before
using it.

The default change-count and changed-byte budgets are deliberately bounded.
An operator may lower them for a smaller review or raise them only up to the
shipped hard caps:

```powershell
archive git-backup-plan <archive-root> `
  --remote origin `
  --max-changes <count> `
  --max-changed-bytes <bytes> `
  --dry-run `
  --format json
```

Exceeding a bound blocks the plan. It does not silently truncate a plan and
present the partial result as complete.

## What The Plan Stabilizes

The command uses Git's machine-readable, NUL-delimited porcelain v2 status
format so record boundaries and rename pairs are not guessed from ordinary
line-oriented text. Unsupported unsafe names, including control characters,
block instead of being normalized. It binds a plan to the observed:

- symbolic target branch and exact local commit; an unborn branch is detected
  and blocked in v0.4.2;
- index, tracked tree, staged and unstaged changes, untracked items, conflicts,
  and Git-ignored exclusions;
- bounded current-file digests and exact tracked preimage evidence where the
  classification needs it;
- Git object format and relevant repository/configuration safety state;
- content-free receipt inventory and session-handoff context state; and
- one exact remote branch-ref result from `git ls-remote --refs --exit-code`.

The implementation observes the important local, evidence, handoff, and
remote inputs more than once. A change during inspection becomes a blocker
instead of producing a plan that combines different moments.

The returned `plan_sha256` binds the complete private observation. It is safe
to compare as an opaque digest, but it is not an approval token. Changing a
file, index entry, commit, relevant Git state, evidence set, handoff state, or
remote branch result changes or invalidates the plan.

## Privacy Boundary

The JSON response is designed for an AI or operator to inspect without
publishing archive contents. It uses opaque ordinal change references rather
than returning private paths. It does not return file bodies, commit messages,
the archive identity, an absolute local path, the configured remote URL,
credentials, raw Git errors, or raw receipt/handoff contents.

Git-ignored items are reported only as bounded exclusions and aggregate
evidence. Being ignored does not prove that an item is disposable,
reconstructible, backed up elsewhere, or safe to delete.

Historical receipts and a session handoff can provide context, but v0.4.2 does
not guess provenance from arbitrary JSON fields. Neither one proves that a
current file belongs in a particular commit.

## Fail-Closed Repository Boundary

The planner blocks instead of simplifying an unsupported Git state. Examples
include:

- a detached or invalid target ref, bare or shallow repository, unsupported
  object format, or an unexpected repository/worktree layout;
- an active Git operation, Git lock, or WOM Git-backup coordination lock;
- split index, sparse checkout, partial clone, non-plain index flags, tracked
  symlinks, Git links, submodules, or paths that are not cross-platform safe;
- any repository-controlled `.gitattributes` file in the worktree, index, or
  `.git/info/attributes`, because even `git status` can invoke configured
  content filters before a plan is safe to trust;
- malformed or drifting status/index/tree data;
- a non-HTTPS, authenticated/private, ambiguous, unsafe, or multiply
  configured remote URL;
- a missing, unavailable, malformed, or changing target remote ref; and
- a count, byte, individual-file, Git-output, receipt, or path-inventory limit
  being exceeded.

A blocker is a truthful stop condition. Do not work around it with an
automatic pull, merge, rebase, reset, checkout, deletion, or forced push.
In particular, do not delete or disable a repository's `.gitattributes` to
make v0.4.2 pass. Supporting a proven inert attribute subset is future work;
this release intentionally prefers a visible stop over executing a filter.

## Remote Result Means Git Transport, Not Provider Proof

The initial v0.4.2 remote check permits only anonymous HTTPS. It disables
interactive prompting and credential-helper execution, bounds output and
runtime, and contains the transport process tree. SSH/scp-like remotes and
URLs with user information fail closed. The configured URL is used internally
and is not echoed.

An authenticated or private repository can therefore report the remote state
as unavailable in v0.4.2 even when a human can access it through another Git
client. Do not weaken the observer or place a token in the URL to work around
that boundary. Authenticated provider observation needs a future separately
designed credential-capability path.

A matching ref proves only that the Git transport returned one exact ref at
that moment. It does not prove repository visibility, account ownership,
branch protection, provider-side audit state, durability, or that a later
push completed. Those claims require a provider re-query after an explicitly
reviewed future writer.

The planner follows Git's documented plumbing and stable output contracts:

- [git-status porcelain v2 and `-z`](https://git-scm.com/docs/git-status)
- [git-ls-remote exact ref queries](https://git-scm.com/docs/git-ls-remote.html)
- [git-rev-parse repository and object-format inspection](https://git-scm.com/docs/git-rev-parse.html)
- [git-rev-list reachability comparison](https://git-scm.com/docs/git-rev-list)

## Reconcile A Reviewed Observation

After a human has reviewed the first result, repeat the same archive, remote,
branch, and bounds and bind the comparison to its digest:

```powershell
archive git-backup-reconcile-plan <archive-root> `
  --remote origin `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --dry-run `
  --format json
```

The plan digest is required. For a stronger explicit comparison, an operator
can also copy reviewed values from the first result:

```powershell
  --expected-hidden-effect-set-sha256 sha256:<64-lowercase-hex> `
  --expected-local-head-oid <40-or-64-hex-object-id> `
  --expected-remote-oid <40-or-64-hex-object-id>
```

Each optional value is checked only when supplied, and any mismatch blocks.
Do not supply `--expected-remote-oid` when the reviewed plan had no remote
object id.

The reconcile command re-runs the complete bounded observation. The exact
`repository.relation.state` values are `equal`, `local_ahead`, `remote_ahead`,
`diverged`, `remote_branch_missing`, `remote_oid_not_available_locally`, and
`not_computed`. An unavailable remote observation blocks and leaves the
relation `not_computed`. The command still does not fetch objects, choose
commit groups, write a receipt, commit, or push.

If the expected digest does not match, stop and review the new plan. Do not
replace the digest automatically and treat that as human review.

## What Remains For Letter 139

v0.4.2 addresses only the read-only planning and reconciliation foundation of
Letter 139. A complete solution still needs a separately designed and
reviewed one-writer workflow for exact file selection, commit grouping,
commit creation, push, provider re-query, durable completion evidence, and
legacy small-batch recovery. No part of this release authorizes that future
writer.
