# Activity-Group Membership Write And Recovery

`activity-group-membership-write` is the approval-gated continuation of the
read-only [Activity-Group Membership Plan](activity-group-membership-plan.md).
It adds one already-reviewed event anchor id to the exact canonical member zets
named in one private request.

It does not discover members, infer membership, remove an existing membership,
or edit a canonical file outside the request.

## Review first

Keep the reviewed request under:

```text
.wom-scratch/private/activity-groups/
```

Run the read-only plan:

```powershell
archive activity-group-membership-plan C:\path\to\archive `
  --request .wom-scratch/private/activity-groups/reviewed.json `
  --dry-run --progress --format json
```

Retain the returned `request_sha256` and `review_plan_sha256`. These hashes bind
the private request, event anchor, ordered members, and exact current and
proposed canonical bytes.

## Preview the transaction

```powershell
archive activity-group-membership-write C:\path\to\archive `
  --request .wom-scratch/private/activity-groups/reviewed.json `
  --expected-request-sha256 sha256:<request-digest> `
  --expected-review-plan-sha256 sha256:<review-plan-digest> `
  --dry-run --progress --format json
```

The preview writes nothing. It independently rebuilds the exact write
candidates and returns `write_plan_sha256`.

## Approve the write

After a human checks every requested membership:

```powershell
archive activity-group-membership-write C:\path\to\archive `
  --request .wom-scratch/private/activity-groups/reviewed.json `
  --expected-request-sha256 sha256:<request-digest> `
  --expected-review-plan-sha256 sha256:<review-plan-digest> `
  --approve `
  --reviewed-by person:<reviewer> `
  --affirm-memberships-reviewed `
  --progress --format json
```

The approval is rejected if the request, review plan, archive identity, event
anchor, member list, or any participant byte changed. The writer then repeats
the same checks after taking its exclusive archive-local lock.

The writer changes only:

```text
frontmatter.facets.activity_group
```

It preserves the body bytes, anchor bytes, other frontmatter meaning, and
`updated_at`. A scalar existing membership becomes a list only when another
event anchor must be added. An already-present membership is left unchanged.

## Transaction evidence

Before the first canonical write, WOM:

1. stores every exact before-state as a verified content-addressed object;
2. registers those objects in the local object manifest;
3. publishes a private prepared transaction journal; and
4. keeps an exclusive writer lock.

Each canonical file is written through a temporary file, flushed, and replaced
atomically. After every expected hash is verified, WOM publishes one immutable
receipt under:

```text
receipts/activity-groups/
```

The private journal and lock are removed only after the receipt verifies. A
normal runtime exception rolls all changed members back to their exact before
bytes. A process termination or machine interruption may leave the journal,
lock, and snapshots so recovery can classify what actually reached disk.

## Recovery

First confirm that the interrupted writer process is no longer running. Then
inspect one transaction:

```powershell
archive activity-group-membership-recovery-plan C:\path\to\archive `
  --expected-request-sha256 sha256:<request-digest> `
  --dry-run --format json
```

The plan compares every current participant hash with its journal-bound before
and after hashes. It selects exactly one action:

- remove an unused lock;
- remove evidence for a transaction that never changed canonical bytes;
- restore a partially applied transaction to verified before bytes;
- remove residue after a fully verified receipt;
- or stop in `manual_forensic_hold` when evidence is missing, malformed, or
  current bytes match neither approved state.

For a non-forensic action, review the returned `recovery_plan_sha256`, confirm
again that no writer is running, and execute:

```powershell
archive activity-group-membership-recover C:\path\to\archive `
  --expected-request-sha256 sha256:<request-digest> `
  --expected-recovery-plan-sha256 sha256:<recovery-plan-digest> `
  --approve `
  --reviewed-by person:<reviewer> `
  --affirm-recovery-reviewed `
  --progress --format json
```

Recovery has its own exclusive guard and repeats the plan after acquiring it.
The recovery-plan digest also binds whether the global writer lock exists and,
when present, its exact bytes. If a complete journal remains but its writer
lock is missing, recovery must claim that same global lock exclusively before
touching canonical bytes. The writer checks the recovery guard before and
after claiming its own lock, so the two paths cannot begin concurrently.
Recovery never guesses through unknown drift and never acts on
`manual_forensic_hold`.

## Privacy and bounds

Public command output contains counts, state names, blocker codes, and hashes.
It does not return request paths, zettel ids, canonical paths, titles, facet
values, bodies, reviewer ids, provider locations, or local absolute paths.

The writer and recovery path call no model, provider, network, generated index,
database, environment-variable store, or credential store. The same bounds as
the read-only plan apply: 2 MiB request, 5,000 members, 16 MiB per canonical
file, and 256 MiB total canonical bytes. Receipt and journal reads are also
bounded to 16 MiB.

## Deliberate boundary

v0.3.281 implements additions only. Removing an event membership is a distinct
semantic operation and remains unavailable. Search, title, time, proximity,
and edges remain candidate-finding aids for a human, never write authority.
