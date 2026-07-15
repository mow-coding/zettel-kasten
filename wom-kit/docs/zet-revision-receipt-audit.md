# Canonical zet Revision Receipt Audit

Status: chronological revision event-chain and prior-byte audit in v0.3.248

`zet-revision-receipt-audit` answers a narrow question after ordinary
canonical corrections or exact restores: do the retained receipts form one continuous history
to each current zet, and does any private transaction lock still need human
attention?

For each new v0.2 ordinary revision receipt, it also asks whether the exact
prior canonical bytes still exist in the local content-addressed object store
and have one matching manifest record. Legacy v0.1 receipts remain valid
hash-only history and are counted separately.

Run:

```powershell
archive zet-revision-receipt-audit <archive-root> `
  --dry-run `
  --max-receipts 5000 `
  --max-locks 5000 `
  --max-problems 100 `
  --progress `
  --format json
```

Aliases are `revision-receipt-audit` and `canonical-revision-audit`.

## Receipt Chain

Every valid ordinary revision or exact-restore receipt under
`receipts/revisions/canonical/*.zet-revision.json` has a before state, an after
state, and one normalized event timestamp. The audit
groups receipts by their private canonical identity, orders each group by
event time, and then checks every adjacent transition.

A healthy group has:

- one newest receipt whose complete after state matches the current zet;
- zero or more older receipts connected through exact adjacent before/after
  file, semantic, abstract, and body hashes;
- unique, strictly increasing revision event timestamps;
- no branch/replay transition or partial state-evidence gap;
- one stable zet id and canonical path inside the private evidence.

Every v0.2 ordinary revision event additionally has:

- a `before_snapshot.object_id` equal to its `before.file_sha256`;
- an exact regular file under `objects/sha256/` with that digest and byte size;
- one matching local record in `objects/manifests/files.jsonl`.

Historical receipts are not required to match today's file directly. File and
semantic hashes may repeat when the chronological transitions remain exact.
For example, `A -> B -> A` is a valid evidence-complete restore shape, not a
cycle by itself. An older receipt whose after-state happens to match today's
bytes again is still not the latest event.

## Lock States

The audit reads the text-free private per-canonical lock and reports one of
these content-free states:

- `completed_lock_leftover`: a matching immutable receipt exists; inspect the
  stale lock before any later cleanup;
- `recoverable_missing_receipt`: the canonical candidate is already present
  but its receipt is missing; rerun the exact original approved
  ordinary `zet-revision-write` or restore `zet-revision-restore-write`
  command to finish only the receipt;
- `prewrite_lock_leftover`: the canonical zet still matches its before hash;
  rerun the exact original approved ordinary-revision or restore command so it
  can revalidate and resume; the audit itself never cleans the lock;
- `ambiguous_lock`: current bytes match neither bound state or the lock and
  receipt disagree;
- `invalid_lock`: the text-free evidence cannot satisfy the revision receipt
  contract;
- `unsupported_lock`: the filename is not the v0.3.235 per-canonical shape.

The audit never deletes a lock. A lock is crash evidence, not disposable
temporary clutter until its state is understood.

## Scale And Privacy

The algorithm is
`O(manifest_records + receipt_files log receipt_files + revision_chains + lock_files + unique_before_snapshot_bytes)`.
Each private identity's events must be ordered by time. It opens the object
manifest at most once, hashes each unique snapshot/state at most once, opens
each receipt and lock once, and reads each current canonical target at most
once per private identity. It does not rescan all zets for every receipt, and
it remains far from a per-receipt whole-archive or quadratic pass.

Output may include fixed status codes, counts, SHA-only receipt/write/lock
handles, and `audit_digest`. It does not echo zet ids or paths, proposal
filenames, reviewer ids, titles, abstract or body text, custom frontmatter
values, provider URLs, absolute paths, or secrets. Snapshot bytes are read only
for local hash verification and never echoed. It calls no model, provider,
remote object store, database, credential store, or network.

## Honest Stop

A green audit proves bounded local consistency for receipt files, current
canonical hashes, recognized locks, and the local prior-byte snapshots required
by v0.2 ordinary receipts. It does not prove that a correction is factually
true, that no external editor can race WOM, or that a remote backup exists.

Canonical restore is not performed by this read-only command. v0.1 receipts
still require separately recovered bytes. New v0.2 receipts preserve those
bytes as local objets, but the v0.3.248 restore planner still accepts a complete
privately reviewed scratch proposal and binds it to the selected receipt's
before hashes. The selected receipt must be the actual newest event. The
separately approved CLI-only `zet-revision-restore-write` can install the exact
reviewed bytes and append one restore event. MCP exposes no duplicate
receipt-audit or revision/restore write tool.
