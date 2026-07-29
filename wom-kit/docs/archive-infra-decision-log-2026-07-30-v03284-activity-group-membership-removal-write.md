# Decision Log: v0.3.284 Activity-Group Membership Removal Write

Date: 2026-07-30

## Context

v0.3.280 introduced explicit read-only activity-group addition planning,
v0.3.281 added the approved addition writer and interruption recovery,
v0.3.282 introduced a separate read-only removal plan, and v0.3.283 hardened
the shared retained-journal and exact-evidence boundary.

The removal plan deliberately stopped before mutation. A removal writer must
not reuse addition approval, infer candidates, normalize malformed membership
data, or treat an already-absent membership as permission to write. It must
also coordinate with addition so two operations cannot mutate the same
logical field while retained evidence from either operation remains.

## Decision

1. Add a distinct CLI-only
   `activity-group-membership-removal-write` command and
   `event-group-membership-removal-write` alias.
2. Require exactly one of `--dry-run` or `--approve`.
3. Bind the exact private removal request SHA-256 and the exact read-only
   removal review-plan SHA-256 on both preview and approval.
4. Require an attributed safe reviewer and
   `--affirm-removals-reviewed` for approval.
5. Reopen the private request and rebuild the review plan, mutation candidates,
   and write-plan digest under the shared writer lock. Block any change instead
   of adapting the reviewed set.
6. Mutate only `ready_to_remove` participants and only
   `frontmatter.facets.activity_group`.
7. Remove only the named event anchor. Preserve other membership order and
   list representation, every other facet/frontmatter meaning, body,
   `updated_at`, BOM state, and newline convention.
8. Keep malformed or ambiguous membership shapes blocked. Do not normalize
   them.
9. Treat `already_absent` rows as satisfied but exclude them from snapshots,
   journal participants, canonical write attempts, and receipt participants.
10. Return `already_satisfied` without creating mutation artifacts when no
    `ready_to_remove` participant exists.
11. Keep one global activity-group writer lock, one recovery guard namespace,
    and one bounded fail-closed inventory across the add and removal private
    roots.
12. Keep removal request, prepared journal, immutable receipt, and recovery
    contracts separate from the existing addition contracts.
13. Preserve exact before-file snapshots in the content-addressed object store
    before publishing the prepared removal journal.
14. Publish the removal journal before the first canonical mutation and the
    immutable removal receipt after every final participant hash verifies.
15. Use the existing OS-level compare-and-swap boundary for forward mutation,
    handled runtime rollback, and approved recovery. Never overwrite a third,
    unknown state.
16. Add read-only
    `activity-group-membership-removal-recovery-plan` and separately approved
    `activity-group-membership-removal-recover`, with matching
    `event-group-*` aliases.
17. Bind recovery to the exact request digest, exact recovery-plan digest,
    retained journal/lock/receipt evidence, participant states, and verified
    snapshots. Rebuild the plan under the recovery guard.
18. Keep foreign, malformed, mismatched, changed, or ambiguous evidence in
    non-executable `manual_forensic_hold`.
19. Add public v0.1 removal receipt and transaction-journal JSON Schemas while
    preserving all existing addition public artifact schemas.
20. Advance AI command-path routing to
    `wom-kit/ai-command-path-routing/v0.6` with official removal write and
    recovery routes.
21. Add no membership inference, direct-file-edit permission, general facet
    editor, MCP writer, provider/model/network/index/database/
    credential-store dependency, automatic hard-exit resume, or removal
    revert operation.

## Rationale

Addition and removal have opposite authority. A digest and receipt proving
that an anchor was added cannot prove that a human later approved deleting it.
Separate contracts keep that distinction auditable.

At the same time, both operations change one shared canonical field. One lock
and one two-root retained-evidence inventory prevent addition and removal from
running past each other's unfinished transactions. Separate evidence plus
shared serialization preserves both safety properties.

`already_absent` is part of what the human reviewed, so it remains in the
review-plan digest. It is not a mutation, so recording it as a before-snapshot
or changed receipt participant would overstate what the transaction did.

Replanning under lock closes the gap between human-reviewed preview and write
authority. Exact snapshots and compare-and-swap then prevent stale approval,
runtime rollback, or recovery from overwriting an unknown concurrent edit.

Hard-exit recovery remains separately reviewed because durable journal
evidence describes what may have reached disk, but does not authorize an AI to
choose cleanup or rollback without a fresh human-bound recovery digest.

## Consequences

- An archive owner can execute an exact reviewed removal without directly
  editing canonical Markdown.
- Addition remains byte-for-byte and schema-compatible at its existing public
  boundary.
- Either a retained add journal or retained removal journal blocks either
  writer before and under the shared lock.
- Already-absent rows cannot inflate snapshot, journal, write-attempt, or
  receipt evidence.
- Drift between preview and lock acquisition blocks before mutation.
- Handled failures return to exact prior bytes when no unknown concurrent
  state exists.
- Hard-exit residue is classifiable and recoverable only through the dedicated
  reviewed recovery commands.
- Unknown evidence remains visible for forensic review rather than being
  deleted to unblock a new writer.
- AI runtimes gain an official route through plan, preview, approval, recovery
  planning, and recovery, but gain no independent write authority.
- Deliberate post-completion compensation remains future work and cannot be
  simulated by the interruption-recovery command.
