# Decision Log — Repository Closeout Discipline

Date: 2026-08-26
Status: accepted

## Context

Merged WOM release work left multiple task worktrees and local and remote
branches behind. Reporting their status without removing completed artifacts
did not satisfy the operator's repeated cleanup requirement.

## Decisions

1. Repository closeout is part of release completion. A completed task must
   verify the PR and release, remove its task worktree and local branch, remove
   its merged remote branch, and re-check the primary checkout.
2. GitHub deletes merged head branches automatically. A manual verification
   remains required because local worktrees and branches are outside that
   setting.
3. Dirty or patch-unique task state is never discarded merely to make a folder
   list look clean. It is first classified and stored in a verified local-only
   recovery bundle. The bundle is not published.
4. Cleanup targets only exact verified development and task-temporary paths.
   A similarly named client archive is outside scope unless the user separately
   authorizes changes to it.
5. Closeout evidence must show the final counts for worktrees, local branches,
   remote branches, open PRs, and primary `main` alignment. A status-only audit
   is not completion evidence.

## Consequences

- Finished release work no longer leaves visible `zettel-kasten-*` folders in
  the shared development directory.
- Unique abandoned work remains recoverable without keeping active-looking
  branches and worktrees.
- Future release reports must distinguish an observed cleanup candidate from
  an artifact that was actually removed and independently rechecked.
