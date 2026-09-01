# Decision Log: v0.4.17 Terminal Cleanup Recovery

Date: 2026-09-01

Status: accepted implementation direction; public release evidence pending

## Context

A private read-only client report showed a systemic project-update dead end.
The dry-run could report a fresh update ready while approval rejected retained
terminal control history produced by a normal earlier cancellation. The known
gate then became a generic CLI error without a supported recovery instruction.

## Decision

Use the existing `project-version-update` command for the complete correction.
Do not add a cleanup command or ask the operator to identify private artifacts.

1. Fresh dry-run and approval use one bounded read-only transaction-namespace
   classification before native approval or domain-writer entry.
2. Exact WOM-produced terminal control history returns
   `project_version_update_terminal_cleanup_required` and routes only to
   identifier-free `project-version-update --resume`.
3. Exact completed preapproval-abort history may be compacted into canonical
   proof history under a v0.4.17 identity-bound cleanup plan and dedicated
   cleanup authority.
4. Existing authenticated approved transactions continue under their original
   claim, postimage, terminal handoff, and cleanup authority, without a second
   native decision or domain-writer replay.
5. Proof-only history grants no past-success attribution, cleanup authority,
   retry authority, or fresh write authority. New work requires a new preview
   and one new approval.
6. Partial, malformed, mixed, changing, ambiguous, linked, raced, locked, or
   unsafe residue remains
   `project_version_update_terminal_cleanup_outcome_unknown` and authorizes no
   automatic or manual cleanup.
7. Only fixed allowlisted cleanup errors may become structured public CLI
   reasons. Arbitrary exception messages remain redacted.
8. Terminal result reads must retain the complete parent namespace and exact
   file handle, require one link and supported private metadata, and reject
   Windows alternate streams before the document can carry authority.
9. An exact active transaction never excuses an unresolved sibling artifact.
   Active and sibling state are classified as one namespace, and any unknown
   member stops before recovery, approval, or the domain writer.
10. Mixed or partially completed private-control cleanup must be reported as
    such. Domain-file lists remain explicitly scoped to project-domain files;
    they must not be presented as a claim that no private control effect ran.
11. Canonical proof-only classification and cleanup execution must use the same
    held, single-link, default-stream-only reader. A proof or cleanup record with
    an alternate stream, hard-link alias, unsafe parent, or identity drift is
    unresolved evidence, never inert history or fresh-approval authority.
12. The public recovery gate may project only the fixed
    `project_version_update_terminal_handoff_invalid` reader failure into the
    structured cleanup-unknown result. It must not expose the raw exception or
    widen that allowlist to unrelated internal failures.
13. Fresh mutation and mutation-bearing resume must hold one exact project
    terminal guard from the final handoff observation through native approval,
    claim checkpoints, domain writing, terminal publication, and cleanup. A
    nested terminal writer may reuse only that state-owned lease.
14. Terminal-ready replay must hold the same guard through ready-document
    revalidation, result reauthentication, capability derivation, and cleanup.
    A pre-unlock handoff may correlate with only its exact active transaction
    or that same transaction's complete cleanup tombstone.
15. CLI operation-journal discovery must be enclosed by strict active-handoff
    snapshots. Handoff presence, state, digest, or candidate-correlation drift
    is cleanup-outcome-unknown; unrelated operation-control errors remain
    generic and private.

## Human responsibility

The person decides whether same-project writers are paused and whether to run a
fresh reviewed update after recovery. WOM verifies counts, identities, hashes,
exact artifact shape, drift, cleanup selection, checkpoints, proof retention,
and postconditions. Private transaction identifiers are never operator inputs.

## Consequences

- A normal preapproval cancellation can no longer permanently poison later
  update approval when its exact terminal evidence is intact.
- Dry-run and approval cannot disagree about cleanup readiness for the same
  unchanged namespace state.
- Recovery remains fail-closed for every state not proven to be the exact WOM
  terminal form.
- Abort-history cleanup changes private control evidence only. It does not
  change source, runtime, pin, or archive content and does not infer update
  success.
- The top-level command and human-decision counts do not increase.
- Two same-project WOM sessions cannot both cross the terminal authority
  boundary cooperatively. Losing the guard or observing different handoff
  authority stops the later invocation before it can borrow the first
  invocation's result or cleanup authority.
- v0.4.16 terminal schema identifiers and historical evidence remain readable;
  v0.4.17 adds a narrow cleanup-plan/result schema rather than rewriting prior
  records.
- Publishing or installing the release does not apply recovery to any client
  project. Client execution and durable verification remain separate.

## Rejected alternatives

- **Treat exact abort directories as ignorable forever.** This would unblock
  approval but leave unbounded private residue and would not provide an actual
  recovery mechanism.
- **Delete every old transaction directory by age or name.** A name or age is
  not cleanup authority and could destroy ambiguous recovery evidence.
- **Add a separate operator cleanup command.** It would increase command and
  decision burden and ask the person to solve machine-verifiable internals.
- **Open a new approval for recovery.** Exact preapproval-abort compaction has
  no project-domain effect; an extra native decision would misdescribe the
  operation and still would not prove artifact safety.
- **Expose the original exception.** Internal service messages may contain
  private context and are not a safe public diagnostic contract.
- **Automatically start the fresh update after cleanup.** Cleanup authority is
  not update authority. A new target requires a new preview and approval.

## Verification and release gate

Use only synthetic project fixtures. Require exact-shape and adversarial tests,
interruption/resume/idempotency tests, dry-run/approval parity, zero domain
effects during abort compaction, CLI privacy tests, full cross-platform CI,
resource synchronization, wheel verification, public privacy checks, and exact
merge/tag/release evidence. A released implementation remains unvalidated for a
client until that client separately runs recovery and the original workflow.

## Deferred proof lifecycle decision

Canonical cleanup proofs currently share the bounded transaction namespace and
are intentionally retained. The scan cap prevents unbounded work, but a long-
lived project can eventually exhaust that cap through normal proof history.
v0.4.17 does not invent deletion or age-based rotation authority during an
incident fix. A later explicit design must move verified proofs into a bounded,
checkpointed ledger or provide an equally evidence-preserving rotation policy.
Until then, reaching the cap remains a safe availability stop, not permission
for automatic or manual deletion. This debt must be closed before a stable
production contract claims indefinite project-update availability.

Longer chronology and implementation notes:
[meeting-minutes/2026-09-01-v0417-terminal-cleanup-recovery.md](meeting-minutes/2026-09-01-v0417-terminal-cleanup-recovery.md).
