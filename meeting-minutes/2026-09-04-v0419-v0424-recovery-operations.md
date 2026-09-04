# v0.4.19-v0.4.24 Recovery And Operations Work Record

Date: 2026-09-04

Status: accepted execution plan; implementation begins with v0.4.19. A public
release does not by itself close any client report.

## Context and user intent

Repeated beta feedback showed a gap between a command appearing available and
the same command working in the client runtime. It also exposed long silent
diagnostics, unclear batch targets, mixed work from several AI applications,
credentials that could not be reused safely, incomplete Notion recovery,
incomplete object-storage proof, and cleanup workflows that could not finish.
The user asked that these problems be completed as operating workflows instead
of accumulating more diagnostic-only commands.

The user also corrected the human boundary. A person must not count archive
rows, copy identifiers, construct JSON, compare hashes, choose checkpoints, or
decide where a resume starts. WOM performs those mechanical checks. The person
decides only the meaningful action: beginning or handing off work, entering a
secret in a native secure form, approving a comprehensible batch, deciding a
relationship, or resolving genuinely ambiguous evidence.

## Release train decision

The work is split into six independently complete releases:

1. v0.4.19 makes project update, runtime inspection, capability reporting,
   Doctor output, and Windows child-process behavior tell the same truth.
2. v0.4.20 binds new writes to an opaque client-app, named-workstream, and
   work-session chain while retaining one archive-wide writer lock.
3. v0.4.21 provides local-only paged target previews and completes supported
   title and remint reconciliation.
4. v0.4.22 introduces the scoped Windows credential broker and completes the
   evidence-built Notion recovery workflow.
5. v0.4.23 proves complete R2 bytes, safely offloads eligible local objects,
   and automatically rehydrates them when requested.
6. v0.4.24 completes relation decisions, session-scoped artifact and Git
   handling, legacy responsibility assignment, and evidence-backed feedback
   closeout.

Each release is integrated and applied in order. Later domain code may be
prepared on isolated branches, but an incomplete external service cannot hold
back a completed earlier safety result.

## Safety and privacy boundary

- Development takes place only in dedicated worktrees rooted at the public
  development repository.
- The beta client's archive, runtime, credentials, providers, and feedback
  ledger remain read-only to the development team.
- Public fixtures are synthetic. Human-readable labels, target titles,
  filenames, provider identifiers, and absolute paths do not enter public
  manifests, logs, receipts, errors, or binding records.
- A release can be described as release-addressed only after its reviewed
  public wheel is published and independently installed. A client problem is
  resolved only after the client launcher executes it and returns a durable
  receipt plus independent verification.
- Repository closeout is part of every release: the feature and evidence PRs
  are merged, branches and task worktrees are removed, and the primary checkout
  is rechecked against the remote.

## v0.4.19 implementation split

Three bounded branches were created from the same clean `origin/main`:

- runtime observation and project-update revalidation truth;
- one capability-availability decision shared by user-facing surfaces; and
- noninteractive Windows child-process hiding plus Doctor scan/progress work.

The integration branch owns the release documentation, package metadata,
cross-domain verification, independent review, PR, tag, wheel, publication,
and cleanup. The canonical checkout remains clean during implementation.

## Verification loop

For every release the team records the current remote state, runs focused and
full tests, exercises interruption/resume/rollback and drift, runs public
privacy and package-resource gates, obtains an independent review, verifies
the exact merged commit and annotated tag, downloads the public wheel without
credentials, installs it in a new process, and finally removes task-owned
branches and worktrees. Counts or provider facts that drift are recomputed by
WOM and stop only the affected operation before human approval.

