# Archive Infra Decision Log - v0.3.265 Abstract Batch Journal

Date: 2026-07-27

Status: accepted for v0.3.265 implementation and release-candidate review

## Context

The quarantined v0.3.257 work checkpoint identified two different interruption
failures:

1. one canonical zet could be torn by an interrupted in-place write;
2. a multi-zet abstract batch could stop between participants with no durable
   record of its intended before/after states.

v0.3.264 closed the first failure for canonical writes generally. It explicitly
left the second open. The v0.3.265 task is to close only the missing-evidence
layer for abstract backfill apply and revert, without quietly claiming automatic
recovery.

## Failure Reproduction

Before this decision, apply and revert created a one-line lock, changed canonical
files sequentially, and wrote one receipt only after the whole batch completed.
An ordinary Python exception entered the in-memory rollback, but a process kill
did not. Killing the process after the first write in a two-item batch left:

- one canonical participant at its after state;
- one participant at its before state;
- no final receipt;
- a lock whose contents the public audit intentionally did not read;
- no record binding the batch's participants or intended hashes.

The operator could detect that something stopped, but could not distinguish
before, partial, fully written without receipt, or later external divergence.

## Decision

### 1. Ship an evidence rung before a recovery rung

v0.3.265 creates a durable, private, schema-validated transaction journal before
the first canonical mutation in approved abstract apply and revert. It does not
add an automatic resume, receipt finalizer, or hard-exit rollback.

Recovery changes canonical state and therefore needs a later decision covering
authority, current-state revalidation, receipt semantics, idempotency, and
operator approval. Evidence can be shipped and tested independently.

### 2. Derive state from immutable intent plus current participant hashes

The journal stays in `status: prepared`; it is not rewritten after each item.
Progress is inferred by comparing each current canonical file SHA-256 with the
journal's before and after SHA-256:

- all before -> `prepared`;
- a mixture of before and after -> `partially_applied`;
- all after and no receipt -> `fully_applied_receipt_missing`;
- missing or neither hash -> `divergent`;
- final receipt present -> `stale_completed`.

Avoiding per-item journal rewrites removes a second progress file that could
itself be torn or lag behind the canonical write. The participant hashes are the
state.

### 3. Bind the entire transaction before publishing it

The journal binds the archive id, operation, proposal or source-receipt digest,
deterministic final receipt path, plan digest, reviewer, affirmation, ordered
participant ids/paths, and every before/after/body/abstract digest. Its filename
must agree with its operation and basis digest.

The reader rejects duplicate JSON keys, schema failure, a wrong self-digest,
archive mismatch, operation/basis/filename mismatch, wrong final receipt pairing,
non-canonical or unsafe paths, duplicate participants, non-contiguous row
indexes, and identical before/after hashes.

The self-digest is corruption evidence, not authentication. A person who can
rewrite private archive files can recompute it.

### 4. Keep private values private

Recovery needs participant ids and paths and the reviewer/affirmation basis, so
the journal cannot be a public receipt. It lives beside the proposal lock under
`.wom-scratch/abstract-backfill/`.

It stores no body or abstract text. The archive-wide audit may read the private
metadata and canonical bytes, but its output is limited to operation, state,
counts, sorted indexes, and fixed issue codes. It does not echo journal or
receipt paths, participant ids/paths, reviewer, proposal filename, abstract/body
text, journal digest, or absolute paths.

Apply proposals may live in nested directories below
`.wom-scratch/abstract-backfill/`. The lock and journal nevertheless live in one
shared digest namespace at the abstract-backfill root: the deterministic receipt
is keyed by proposal SHA, so its concurrency brake and evidence must be keyed the
same way rather than by proposal filename. Otherwise two byte-identical proposal
copies in different directories could run concurrently; the loser of the shared
receipt-creation race would enter rollback and could undo the winner's completed
canonical batch. The audit still enumerates recognized locks and journals
recursively with archive-relative POSIX ordering so nested residue from older
lock behavior or a pre-release candidate is not silently missed.

### 5. Preserve evidence unless the end state is verified safe

The operation order is:

1. validate and materialize the entire batch;
2. create the existing lock;
3. create and durably publish the journal;
4. mutate and verify every participant;
5. create and verify the immutable final receipt;
6. remove the journal and flush its directory where supported;
7. remove the lock.

On a caught runtime failure, the journal is removed only after every attempted
participant is verified restored and any partial receipt is removed. The lock is
removed only after the journal is gone. An incomplete rollback retains both.

A stop between lock and journal has not changed a canonical file, so the older
unresolved-lock diagnosis is sufficient for that safe pre-mutation gap.

### 6. Extend, rather than rewrite, historical receipt validation

Apply and revert receipts already carried the explicit field
`crash_recovery_journal_written`, historically fixed to `false`. New receipts set
it to `true`. The v0.1 schemas accept both boolean values so v0.3.265 continues to
verify historical receipts without modifying them.

The separate transaction-journal schema carries the new detailed contract.

### 7. Keep the operating-system durability boundary honest

The journal uses `write_json_new_file`, which flushes file data and the parent
directory on POSIX. Windows cannot open a directory for `fsync`; there it is an
atomic create-new file but not a guaranteed power-loss-durable directory entry.
The release therefore claims process-kill evidence on Windows, not sudden-power-
loss durability.

## Alternatives Rejected

### Reuse the one-line lock as the journal

Rejected. The public audit intentionally does not read lock content, and the
lock lacks participants, intended hashes, receipt binding, reviewer authority,
schema validation, and a bounded privacy contract.

### Write progress after every participant

Rejected for this rung. It creates ordering questions between canonical and
progress writes and a mutable evidence file that can lag or tear. Current
participant hashes already distinguish all four incomplete states needed for
the next decision.

### Automatically continue when a journal is found

Rejected. A partially applied batch may have been followed by a human or external
editor change. Even an all-after state still needs an authority decision about
creating the missing immutable receipt. Detection does not grant write authority.

### Automatically delete a prepared journal

Rejected. Prepared proves that no participant moved only after reading every
current hash. The read-only audit may report that fact, but evidence cleanup is a
write and is deliberately not smuggled into an audit command.

### Put text in the journal for self-contained recovery

Rejected. The existing deterministic candidate construction and hashes are
enough for state diagnosis, while body/abstract text would create a second
private content store and a larger leak surface. A later recovery design must
decide whether it re-derives bytes from the still-private proposal/source
receipt or needs another sealed artifact.

## Verification Contract

- Journal creation failure occurs before any canonical write.
- Byte-identical proposals in different nested paths contend on the same
  proposal-digest lock and the blocked operation attempts no canonical write.
- A real child process `os._exit` after the first apply mutation leaves one
  before and one after participant, journal plus lock, and a partial apply audit.
- The same real hard-exit test exists for revert.
- Complete in-process rollback removes journal and lock; incomplete apply and
  revert rollbacks retain both and remain diagnosable.
- Successful apply/revert write and verify the final receipt before journal
  cleanup, record `crash_recovery_journal_written: true`, and leave no journal.
- Prepared, partial, all-after-without-receipt, divergent, and completed-residue
  classifications are covered for apply and revert.
- Invalid filename, wrong receipt binding, equal before/after hashes, private
  output suppression, and historical receipt validation are covered.

## Consequences And Next Decision

An abstract batch can still stop halfway, but the archive no longer loses the
transaction's intended state. The operator can distinguish a safe not-started
batch, a true partial batch, a completed mutation missing its receipt, and an
externally diverged participant without opening private text in public output.

The next release may design automatic recovery on top of this evidence. It must
choose, separately for each state, whether to resume forward, restore backward,
finalize a receipt, or require manual intervention. This decision does not grant
that authority.

Locks are basis-scoped, not participant-scoped. v0.3.265 closes the concrete
same-proposal-copy bypass by putting identical proposal SHAs in one namespace,
but two different proposals or source receipts whose participant sets overlap
are not globally serialized. Designing a global or ordered per-participant lock
without deadlocks, stale-lock expansion, or cross-command surprises is separate
concurrency work. The current immediate hash checks and journals detect many
such races; they do not make that broader race impossible.

The approved title-remap write remains blocked on its own receipt/revert/privacy
decision and is not implemented by this release.

## Independent Review Correction

The first independent adversarial review returned NO-GO with three release
blockers. All three were valid:

1. packaged operator guidance still described the v0.3.219 no-journal boundary;
2. docs claimed completed-residue coverage that did not exist for apply/revert;
3. rollback initialized receipt removal as successful even when an external
   writer had created the deterministic receipt and no unlink was attempted.

The correction makes removal evidence observational: after any owned-file
cleanup attempt, the command checks whether the final receipt still exists.
Canonical restoration with an external receipt still present is an incomplete
rollback, so journal plus lock remain. Journal creation failure also releases
the lock it just created, and public `written_before_first_canonical_write`
becomes tri-state (`true` only for a journal written by this run, otherwise
`null`).

The audit now marks journal or lock residue completed only when the complete
matching receipt lifecycle already verified. File existence alone is
insufficient, so an empty, malformed, or state-diverged receipt cannot downgrade
the residue to a warning. Apply and revert completed-residue regressions and an
invalid-receipt counterexample enforce this boundary.

The operator README, write/revert/audit guides, packaged runtime contract,
upgrade guides, capability matrix, and release note now state the journal,
privacy, downgrade, external-editor, and cross-basis limits explicitly. A
documentation regression checks the source and packaged runtime twins.
