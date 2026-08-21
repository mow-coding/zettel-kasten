# Decision Log: v0.4.2 Letter 139 Read-Only Git Backup Planning

Date: 2026-08-21

## Context

Letter 139 asks WOM to help recover a large mixed Git state into a trustworthy
remote backup. That outcome eventually involves archive-wide file selection,
human commit grouping, local Git mutation, network mutation, and provider-side
verification. Treating those stages as one convenient “backup” button would
hide several independent authority and failure boundaries.

The v0.4.1 release addressed Letter 140's narrow Zettel–Objet link apply. It
did not authorize Git commit or push. Git backup therefore proceeds as its own
release line instead of inheriting the link writer's exact-human claim.

## Decision

Release v0.4.2 with only two new CLI planning surfaces:

- `git-backup-plan` performs a bounded local Git/worktree observation and one
  exact non-interactive remote-ref query;
- `git-backup-reconcile-plan` repeats the full observation and compares it
  with an explicitly supplied prior plan digest;
- the target must be the currently checked-out symbolic branch; an explicit
  branch argument may only reaffirm it, while another branch or an unborn
  HEAD blocks because the current index/worktree is not safe authority for a
  different or not-yet-committed branch;
- both commands remain read-only and always return `ready_for_write: false`,
  `writer_available: false`, and `would_change: []`;
- neither command is exposed as an MCP writer or accepts an approval option;
- parse local changes through Git porcelain v2 with NUL termination and bind
  HEAD, index, tree, worktree, evidence, handoff context, relevant config, and
  exact remote-ref observations into one deterministic private plan digest;
- observe all important authority inputs twice and fail on drift;
- use only bounded anonymous HTTPS `git ls-remote --refs --exit-code`
  transport in a contained process tree, with interactive prompts and
  credential helpers disabled and without echoing the URL or raw errors;
- fail closed for SSH/scp-like, userinfo-bearing, private, or authenticated
  remotes; those repositories may report unavailable until a future reviewed
  credential-capability observer exists;
- describe that result as Git-transport-confirmed ref evidence, not provider-
  confirmed visibility, durability, or push completion;
- output only opaque change references, categories, counts, and digests rather
  than private paths, bodies, archive identity, remote URL, commit messages,
  receipt contents, or handoff contents;
- treat ignored items as exclusions, never as proof of safe deletion or
  recoverability;
- treat receipts and session handoff as bounded context evidence, never as
  generic file provenance or write authority; and
- block unsupported repository forms, active operations/locks, unsafe path or
  index forms, tracked symlinks/Git links/submodules, partial/sparse/split
  states, malformed remote state, drift, and exceeded resource limits.

The full operator contract is recorded in [Git Backup Plan And Reconciliation
Plan](git-backup-plan.md).

## Consequences

An operator can obtain one deterministic, privacy-preserving review basis
without changing the archive, local Git state, or remote. A changed plan must
be reviewed again; copying the new digest automatically is not human review.

v0.4.2 is only a partial response to Letter 139. It does not select exact files
for commits, create a commit, push a ref, query a provider API, publish a
completion receipt, or recover the legacy mixed state in batches. Those steps
require a future operation-specific one-writer design and a separate release
decision.

Release completion still requires the merged commit, required CI, exact tag,
public GitHub Release, exact wheel asset, anonymous asset retrieval, and fresh
isolated upgrade/install verification. This source decision is not evidence
that those release steps have happened.
