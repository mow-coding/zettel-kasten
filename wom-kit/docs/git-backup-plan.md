# Git Backup Plan And Reconciliation Plan

Status: v0.4.3 exact commit/push writer implementation candidate

This guide explains the existing Git backup command family. `git-backup-plan`
remains read-only. `git-backup-reconcile-plan` can remain read-only, validate a
private exact selection, apply it after native approval, or resume the same
authenticated started approval after an interruption.

## The Short Version

Run `git-backup-plan` to take a bounded, privacy-preserving observation of one
Git worktree and its exact target branch. Run `git-backup-reconcile-plan
--dry-run` to repeat that observation. Supplying a private selection manifest
lets the same command validate exact commit groups. `--approve` performs the
selected commits and one non-force push only after a native digest-bound human
decision. `--resume-approval-id` resumes the same manifest and started claim;
it never creates a second approval.

The modes have deliberately different authority:

| Surface | Read-only plan/reconcile | Exact approved apply |
| --- | --- | --- |
| Local Git | inspect HEAD, index, worktree, configuration state, and bounded file evidence | isolated-index proof, exact `git add -- <paths>`, literal `git commit --only`, and post-commit verification |
| Remote Git | query one exact branch ref | reuse an existing non-interactive credential helper, perform one ordinary fast-forward push, then requery the approved URL and exact ref |
| Archive | read bounded metadata and evidence | write local-only private bundle/checkpoint state and content-free completion receipts |
| Authority | return deterministic content-free commitments | require one native exact-human approval bound to the complete manifest SHA-256 |

The plain v0.4.2-compatible plan/reconcile result still keeps these fields
fixed:

```json
{
  "ready_for_write": false,
  "writer_available": false,
  "would_change": []
}
```

`inspection_complete` still means only that the read-only inspection completed.
Only a successful exact-apply result plus its durable domain receipt reports
that the selected commits exist and the exact remote ref was requeried at the
terminal commit.

## First Observation

Use a fresh v0.4.2 process and start with the default `origin` remote and the
branch named by symbolic HEAD:

```powershell
archive git-backup-plan <archive-root> `
  --remote origin `
  --progress `
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

`--progress` emits a content-free first status immediately and a heartbeat at
most every 10 seconds while work continues. Progress goes to stderr, so the
final JSON on stdout remains machine-readable.

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
that boundary.

For the v0.4.3 exact writer, use `--credential-mode stored`. This permits only
an already configured non-interactive credential helper; WOM does not ask for,
print, or place a token in the URL. The approved configured HTTPS URL is kept
private, bound into the manifest source, checked again after approval, used as
the exact push destination, and queried again after push.

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

## Build The Private Exact Selection

The public plan deliberately returns ordinal `change_ref` values instead of
paths. A private operator-owned JSON file must classify every observed
`change_ref` exactly once:

```json
{
  "schema": "wom-kit/git-backup-selection/v1",
  "expected_plan_sha256": "sha256:<64-lowercase-hex>",
  "groups": [
    {
      "group_id": "group:reviewed-1",
      "change_refs": ["change:000001", "change:000002"],
      "commit_subject": "Back up reviewed archive changes"
    }
  ]
}
```

No reference may be omitted, duplicated, or assigned to two groups. Group ids,
subjects, and references are strictly bounded. Paths and commit subjects are
never returned in public output.

Windows accepts at most 32,767 UTF-16 command-line characters. WOM reserves
over 8 KiB for the pinned executable, archive root, safety flags, and message
path, and caps each group's literal path argv at 24 KiB. It checks both UTF-8
path bytes and Windows-quoted characters before approval. A large selection,
including 8,000 or more changes, is valid when it is split into multiple
explicit groups and every reference remains classified; one oversized group
fails closed.

Validate the selection without writing:

```powershell
archive git-backup-reconcile-plan <archive-root> `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --selection-manifest <private-selection.json> `
  --credential-mode stored `
  --dry-run `
  --progress `
  --format json
```

The result returns the exact manifest and component SHA-256 values, group and
classified-change counts, and no private paths or messages.

## Apply And Resume

After reviewing that exact manifest, apply it through the same command family:

```powershell
archive git-backup-reconcile-plan <archive-root> `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --selection-manifest <private-selection.json> `
  --credential-mode stored `
  --approve `
  --reviewed-by person:<safe-operator-claim> `
  --progress `
  --format json
```

The writer then follows one fixed sequence:

1. show one native approval bound to the exact manifest SHA-256;
2. authenticate and durably start the one-use approval claim;
3. acquire the archive-wide exact-operation writer lock;
4. re-read the private selection and freshly re-observe every bound target;
5. prove the selected tree in an isolated index, then run only exact
   `git add -- <paths>` and literal bounded `git commit --only` operations;
6. verify every commit parent, message, changed path set, and selected blob;
7. requery the exact remote ref, make one ordinary non-force push, then requery
   it again and require its object id to equal the terminal local commit; and
8. finalize the common receipt plus a content-free Git completion receipt.

The writer never runs pull, fetch, merge, rebase, reset, clean, delete, or a
force push. Pre-existing staged entries outside the current group are
preserved. A remote advance blocks the push instead of being overwritten.

If an interruption leaves the authenticated claim `started`, use the exact
manifest SHA-256 and approval id reported by reconciliation evidence:

```powershell
archive git-backup-reconcile-plan <archive-root> `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --expected-manifest-sha256 sha256:<64-lowercase-hex> `
  --resume-approval-id approval_<32-lowercase-hex> `
  --reviewed-by person:<same-safe-operator-claim> `
  --progress `
  --format json
```

Resume reauthenticates the same claim and exact checkpoint. It reconciles an
exactly staged group, an already-created verified commit, or a push whose
result was lost but whose exact remote ref now matches. Drift, a different
manifest, a missing checkpoint, a remote race, or a terminal/replayed claim
blocks. There is no automatic push rollback; the completion receipt is local
until a later backup includes it.

## Letter 139 Boundary

The v0.4.3 candidate closes the exact selection, commit grouping, local commit,
authenticated non-force push, exact ref requery, interruption resume, and
durable completion-evidence path. It does not claim Git hosting account
ownership, branch-protection policy, provider audit-log coverage, or automatic
remote rollback. Those are separate provider-policy concerns, not evidence
silently inferred from a successful Git transport.
