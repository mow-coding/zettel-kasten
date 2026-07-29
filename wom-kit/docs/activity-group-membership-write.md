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

Since v0.3.283, a new add cannot begin while any retained or reserved
activity-group transaction journal exists as a direct child of either private
request root:

```text
.wom-scratch/private/activity-groups/
.wom-scratch/private/activity-group-removals/
```

The first bounded scan happens before the shared writer lock is attempted.
The writer repeats the same scan after it owns that lock and before it writes
a snapshot or canonical byte. This isolates an unfinished addition from a new
addition and reserves the same serialization boundary for the future removal
writer. Journal contents are not needed for this blocker and are not returned.

The scan and private evidence writes do not rely on a pathname that was checked
only once. WOM binds every directory component from the resolved archive root
to the private leaf. POSIX keeps an `O_DIRECTORY | O_NOFOLLOW` descriptor chain
and performs child operations relative to the bound parent. Windows keeps
non-delete-shared handles for every ancestor, opens reparse points themselves,
and checks the opened identities. The writer creates its lock and journal
beneath that held private-root binding and creates the receipt beneath a
separately held receipt-parent binding.

Before the first canonical write, WOM:

1. stores every exact before-state as a verified content-addressed object;
2. registers those objects in the local object manifest;
3. publishes a private prepared transaction journal; and
4. keeps an exclusive writer lock.

Each canonical file is committed by an OS-level compare-and-swap rather than a
separate check followed by an unconditional replacement. WOM atomically
preserves whichever bytes occupy the canonical name at the swap instant,
installs the reviewed candidate, and verifies both sides before deleting the
captured prior copy:

- POSIX uses a same-parent `renameat2(RENAME_EXCHANGE)` or
  `renameatx_np(RENAME_SWAP)` beneath the held directory descriptor.
- Windows uses `ReplaceFileW` and a deterministic same-parent backup.

If the captured bytes are not the exact reviewed before-state, WOM restores or
retains those unknown bytes and refuses instead of overwriting them. Runtime
rollback and approved recovery use the same rule in reverse: exact before is a
no-op, exact after may be restored to before, and any unknown state remains
untouched. A hard exit can leave a deterministic complementary swap/backup
entry; it is cleaned only when its bytes and the canonical bytes form the
known before/after pair. Unsupported POSIX exchange primitives fail closed
before the canonical name is changed; a prepared private sibling may remain
when the kernel or filesystem rejects an exchange despite exposing the libc
symbol.

After every expected hash is verified, WOM publishes one immutable receipt
under:

```text
receipts/activity-groups/
```

The private journal and lock are removed only after the receipt verifies. A
normal runtime exception rolls all changed members back to their exact before
bytes. A process termination or machine interruption may leave the journal,
lock, and snapshots so recovery can classify what actually reached disk.

Evidence cleanup is identity- and byte-bound. On POSIX, WOM atomically captures
the current pathname in a fresh quarantine under the globally scanned private
activity-group transaction root, keeps its descriptor open, then repeats the
full read/hash and size/mtime/ctime/identity checks immediately before
deleting that captured entry. The quarantine name uses the retained-journal
suffix: a hard exit after capture is therefore visible to the next inventory
and blocks further work instead of leaving hidden canonical/receipt residue. A
different file that appears under the original name is not deleted; an
observed mismatch is restored without overwrite when possible or retained for
review. A cross-filesystem archive submount fails before source movement. On
Windows WOM verifies and marks the opened READ+DELETE handle itself for
deletion.

POSIX has no portable hash-conditional unlink and cannot revoke an
uncooperative same-UID process's already-open writable descriptor. The
algorithm protects against pathname replacement and detects in-place changes
observed before its final unlink, but external editors must remain quiescent
during approved evidence cleanup.

Completion and rollback remove the exact lock first, revalidate the receipt
state and canonical participants, prove that the transaction's own journal is
the only retained transaction, remove that exact journal last, and require a
clean final inventory. If foreign evidence appears after the receipt commit,
or exact lock/journal cleanup or its revalidation fails, the committed
canonical bytes and receipt remain valid but the writer returns
`applied_evidence_conflict`, not a false clean success.

The immutable receipt is not accepted merely because its request digest and
current memberships look plausible. v0.3.283 compares all fields shared with
the retained journal exactly, including archive/request/review/write bindings,
anchor, reviewer affirmation, deterministic receipt path, privacy contract,
and every ordered participant with its canonical path, before/after hashes,
and before-snapshot record. New private write locks use internal schema v0.2
and commit to a SHA-256 of the full receipt/journal semantic projection,
including anchor, ordered participants, reviewer affirmation, before/after
evidence, receipt location, and privacy contract. When only completed lock
residue remains, the receipt is recomputed and rebound to that commitment. A
legacy v0.1 lock remains compatible when its full journal is present, but v0.1
lock-only completion requires `manual_forensic_hold`. A mismatch is unknown
evidence, not successful completion.

A verified v0.2 completed lock-only residue is automatically cleaned only on
Windows, whose held receipt handle excludes write/delete sharing during lock
cleanup and revalidation. On POSIX the absent journal would leave no full
semantic evidence if the receipt pathname changed after lock deletion, so this
state deliberately remains `manual_forensic_hold`.

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
The guard and any missing-writer-lock recovery claim are created and removed
through one archive-root-to-private-leaf binding held for the entire recovery
attempt.
The recovery-plan digest also binds whether the global writer lock exists and,
when present, its exact bytes. For a completed transaction it additionally
binds the immutable receipt's raw SHA-256 and the exact receipt-to-journal or
receipt-to-lock transaction-binding SHA-256. The executor re-reads and verifies
those values after acquiring its guard and immediately before cleanup. If a
complete journal remains but its writer lock is missing, recovery must claim
that same global lock exclusively before touching canonical bytes. The writer
checks the recovery guard before and after claiming its own lock, so the two
paths cannot begin concurrently. Recovery never guesses through unknown
drift, never cleans evidence that changed after review, and never acts on
`manual_forensic_hold`.

The executor revalidates after removing the exact lock in every recovery state,
including `lock_only_before_journal`. When a journal is present, it reclassifies
all participants while that journal still exists and deletes the journal only
after the verified before/completed state remains stable and no foreign
transaction is present. Immediately before a success result it runs the common
cleanup verifier once more with both lock and journal required to be absent.
A newly appeared receipt, lock, or reserved journal therefore produces
`failed_recovery_evidence_retained`, not a successful cleanup claim.

## Privacy and bounds

Public command output contains counts, state names, blocker codes, and hashes.
It does not return request paths, zettel ids, canonical paths, titles, facet
values, bodies, reviewer ids, provider locations, or local absolute paths.

The writer and recovery path call no model, provider, network, generated index,
database, environment-variable store, or credential store. The same bounds as
the read-only plan apply: 2 MiB request, 5,000 members, 16 MiB per canonical
file, and 256 MiB total canonical bytes. Receipt and journal reads are also
bounded to 16 MiB. Retained-journal discovery examines at most 5,000 direct
directory entries across the two private roots, never recurses, and fails
closed when a root is unsafe or the scan cannot complete. Its public result is
limited to fixed blocker codes, counts, and hashes; it echoes no private
journal filename or content.

## Deliberate boundary

v0.3.281 implements additions only. v0.3.282 adds a distinct read-only
[Activity-Group Membership Removal Plan](activity-group-membership-removal-plan.md),
and v0.3.283 hardens the existing add/recovery transaction boundary without
adding a command, public artifact-schema version, MCP method, or AI-routing
version. The private write-lock shape advances to v0.2 for full transaction
commitment; legacy v0.1 handling is restricted as described above.
Removal writing remains unavailable and is deferred to v0.3.284. Search,
title, time, proximity, and edges remain candidate-finding aids for a human,
never write authority.
