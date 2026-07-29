# Activity-Group Membership Removal Write And Recovery

Status: v0.3.284 approval-gated explicit removal and interruption recovery

`activity-group-membership-removal-write` is the CLI-only continuation of the
read-only
[Activity-Group Membership Removal Plan](activity-group-membership-removal-plan.md).
It removes one already-reviewed event anchor from only the exact canonical
member zets named in one private request.

This is a separate operation from
[`activity-group-membership-write`](activity-group-membership-write.md).
Approval to add a membership is never authority to remove one, and a removal
receipt is never interpreted as an addition receipt.

## Review First

Keep the reviewed request under:

```text
.wom-scratch/private/activity-group-removals/
```

Run the read-only removal plan:

```powershell
archive activity-group-membership-removal-plan C:\path\to\archive `
  --request .wom-scratch/private/activity-group-removals/reviewed.json `
  --dry-run --progress --format json
```

Review every `ready_to_remove`, `already_absent`, and `blocked` row. Retain the
returned `request.sha256` and `review_plan_sha256`. Those values bind the exact
private request bytes, event anchor, ordered members, current canonical hashes,
and proposed hashes.

The planner and writer do not discover candidates. Search, title, date, time
proximity, nearby files, edges, and the generated index may help a human find
material, but they never grant removal authority.

## Preview The Removal Transaction

```powershell
archive activity-group-membership-removal-write C:\path\to\archive `
  --request .wom-scratch/private/activity-group-removals/reviewed.json `
  --expected-request-sha256 sha256:<request-digest> `
  --expected-review-plan-sha256 sha256:<review-plan-digest> `
  --dry-run --progress --format json
```

Alias:

```text
event-group-membership-removal-write
```

Exactly one of `--dry-run` and `--approve` is required. The preview writes
nothing. It reconstructs the exact mutation set and returns
`write_plan_sha256`.

## Approve The Removal

After a human verifies every requested removal and every already-absent row:

```powershell
archive activity-group-membership-removal-write C:\path\to\archive `
  --request .wom-scratch/private/activity-group-removals/reviewed.json `
  --expected-request-sha256 sha256:<request-digest> `
  --expected-review-plan-sha256 sha256:<review-plan-digest> `
  --approve `
  --reviewed-by person:<reviewer> `
  --affirm-removals-reviewed `
  --progress --format json
```

Approval requires:

- the exact raw private request SHA-256;
- the exact read-only removal review-plan SHA-256;
- a safe attributed human reviewer id; and
- the explicit `--affirm-removals-reviewed` affirmation.

A reviewer id or affirmation used without `--approve` is rejected. Changed
request bytes, request order, archive identity, anchor bytes, participant
bytes, row state, or candidate bytes invalidate the reviewed digests.

## Exact Mutation Boundary

The writer changes only:

```text
frontmatter.facets.activity_group
```

For each `ready_to_remove` row, it removes only the exact named event anchor.
It preserves:

- every other membership id and its order;
- scalar versus list shape for the remaining value;
- every other facet and frontmatter meaning;
- the event-anchor file;
- `updated_at`;
- body bytes;
- UTF-8 BOM state; and
- newline convention.

Malformed, duplicate, empty, mixed, unsafe, mapping, or null membership shapes
remain blocked. The writer does not normalize them.

An `already_absent` row is an idempotently satisfied review row, not a
mutation candidate. It is excluded from:

- prior-byte snapshots;
- transaction-journal participant items;
- canonical write attempts; and
- removal-receipt participant items.

If every requested member is already absent, the result is
`already_satisfied` and no lock, snapshot, journal, canonical mutation, or
receipt is created.

## Separate Evidence, Shared Serialization

Removal uses its own public artifact contracts:

```text
wom-kit/activity-group-membership-removal-write/v0.1
wom-kit/activity-group-membership-removal-transaction-journal/v0.1
wom-kit/activity-group-membership-removal-receipt/v0.1
wom-kit/activity-group-membership-removal-recovery-plan/v0.1
wom-kit/activity-group-membership-removal-recover/v0.1
```

Its request and prepared journal live under the private removal root:

```text
.wom-scratch/private/activity-group-removals/
```

Its immutable receipts live under:

```text
receipts/activity-group-removals/
```

Addition continues to use its existing request, journal, and receipt roots and
v0.1 public schemas unchanged.

The two operations deliberately share one global activity-group writer lock,
one recovery guard namespace, and one bounded transaction-evidence inventory.
Before a write attempts that lock, and again after it owns the lock, WOM scans
the direct children of both roots:

```text
.wom-scratch/private/activity-groups/
.wom-scratch/private/activity-group-removals/
```

Any retained add or removal journal blocks either new writer. The combined
scan examines at most 5,000 direct entries, never recurses, does not open a
journal merely to discover it, and fails closed when a root is unsafe or the
inventory cannot complete. Public output does not echo private journal
filenames or content.

## Revalidation Under Lock

After acquiring the shared writer lock and confirming the two-root inventory
is clean, WOM reopens the exact private request and rebuilds:

1. the removal review plan;
2. the mutation candidates; and
3. the write-plan digest.

All three bindings must match the reviewed pre-lock values. An
`already_absent -> ready_to_remove`, `ready_to_remove -> already_absent`, or
any other participant drift therefore blocks before snapshots or canonical
mutation. WOM does not silently shrink or expand the reviewed write set.

## Snapshots, Journal, Compare-And-Swap, And Receipt

Before the first canonical mutation, WOM:

1. stores each exact `ready_to_remove` before-state as a verified
   content-addressed object;
2. records the object in the local manifest;
3. publishes the private prepared removal journal; and
4. retains the shared exclusive writer lock.

Each canonical participant is replaced through the same OS-level
compare-and-swap boundary used by membership addition:

- POSIX uses an atomic same-parent sibling exchange where supported;
- Windows uses `ReplaceFileW` with a deterministic same-parent backup.

The captured current bytes must equal the reviewed before-state, and the
installed bytes must equal the reviewed after-state. Unknown concurrent bytes
are restored or retained rather than overwritten. Unsupported atomic exchange
fails closed before the canonical name is changed.

After every final participant hash verifies, WOM publishes one immutable
removal receipt last. Normal completion removes the exact writer lock first,
revalidates the receipt and participant state, proves the prepared removal
journal is the sole remaining transaction evidence, removes that journal last,
and verifies that the shared inventory is clean.

If canonical bytes and the receipt are valid but evidence cleanup or final
inventory revalidation fails, the result is `applied_evidence_conflict`.
Valid applied truth remains on disk together with the evidence needed for
recovery; the command does not falsely report a clean success.

## Runtime Failure And Hard-Exit Boundary

A handled execution failure removes any receipt created by that attempt and
restores every attempted participant to its exact verified before bytes using
the same compare-and-swap rule in reverse. Unknown concurrent bytes are never
overwritten. A fully verified rollback removes its exact lock and journal.

A process kill, power loss, or other hard exit may leave the lock, removal
journal, snapshots, receipt, or deterministic compare-and-swap residue. Those
artifacts are recovery evidence. Do not delete or edit them by hand.

## Read-Only Recovery Plan

First confirm that the interrupted writer is no longer running:

```powershell
archive activity-group-membership-removal-recovery-plan C:\path\to\archive `
  --expected-request-sha256 sha256:<request-digest> `
  --dry-run --format json
```

Alias:

```text
event-group-membership-removal-recovery-plan
```

`--dry-run` is mandatory. The plan binds the exact retained evidence,
participant before/after states, snapshots, lock, journal, receipt when
present, and the fixed recovery action into `recovery_plan_sha256`.

Safe classifications may select:

- `cleanup_unstarted_removal_lock`;
- `cleanup_unstarted_removal_transaction_evidence`;
- `rollback_uncommitted_membership_removals_to_before`; or
- `cleanup_verified_completed_removal_evidence`.

Missing, malformed, foreign, mismatched, changed, or ambiguous evidence
selects non-executable `manual_forensic_hold`.

## Approve Recovery

For a non-forensic action, review the exact plan and execute:

```powershell
archive activity-group-membership-removal-recover C:\path\to\archive `
  --expected-request-sha256 sha256:<request-digest> `
  --expected-recovery-plan-sha256 sha256:<recovery-plan-digest> `
  --approve `
  --reviewed-by person:<reviewer> `
  --affirm-recovery-reviewed `
  --progress --format json
```

Alias:

```text
event-group-membership-removal-recover
```

Recovery acquires the shared recovery guard, rebuilds the exact plan under that
guard, and performs only the reviewed fixed action. If a complete journal
exists without the writer lock, recovery must also claim that global lock
before touching canonical bytes.

Rollback restores only a verified after-state to its exact content-addressed
before snapshot. Already-restored before-state is a no-op. Any third state is
left untouched for forensic review.

Evidence cleanup is exact-byte and identity bound. Recovery deletes no lock,
journal, guard, receipt, snapshot, or swap residue merely because its filename
looks plausible. Evidence that changed after the reviewed plan is retained.

## Privacy And Bounds

Public output may contain counts, row indexes, fixed status/blocker codes, and
digests. It does not return request paths, zettel ids, canonical paths, titles,
facet values, bodies, reviewer ids, provider locations, secrets, or absolute
local paths.

The write and recovery paths call no model, provider, network, generated index,
database, environment-variable secret store, or credential store. The
existing bounds remain:

- request file: 2 MiB;
- explicit members: 5,000;
- one canonical file: 16 MiB;
- total canonical bytes: 256 MiB;
- receipt and journal reads: 16 MiB each; and
- transaction-evidence discovery: 5,000 direct entries across both roots.

## Deliberate Boundary

v0.3.284 implements only exact, human-selected removal through the CLI:

- no membership inference;
- no general facet editor;
- no direct canonical edit permission;
- no MCP removal writer;
- no provider, model, network, index, or database authority;
- no automatic resume; and
- no removal revert operation.

A later compensation or revert feature must define its own review, evidence,
receipt, and interruption-recovery contract. The v0.3.284 recovery command
only completes or rolls back an interrupted v0.3.284 removal transaction.
