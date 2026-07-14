# Canonical zet Revision Receipt Audit

Status: archive-wide read-only receipt and lock audit in v0.3.236

`zet-revision-receipt-audit` answers a narrow question after ordinary
canonical corrections: do the retained receipts form one continuous history
to each current zet, and does any private transaction lock still need human
attention?

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

Every valid `receipts/revisions/canonical/*.zet-revision.json` receipt has a
before state and an after state. The audit groups receipts by their private
canonical identity and walks backward from the current canonical file hash.

A healthy group has:

- one current receipt whose complete after state matches the current zet;
- zero or more superseded receipts connected through exact before/after file,
  semantic, abstract, and body hashes;
- no duplicate or branched before/after file hash;
- strictly increasing revision timestamps;
- one stable zet id and canonical path inside the private evidence.

Historical receipts are not required to match today's file directly. They are
valid when they sit on the one chain leading to the current receipt.

## Lock States

The audit reads the text-free private per-canonical lock and reports one of
these content-free states:

- `completed_lock_leftover`: a matching immutable receipt exists; inspect the
  stale lock before any later cleanup;
- `recoverable_missing_receipt`: the canonical candidate is already present
  but its receipt is missing; rerun the exact original approved
  `zet-revision-write` command to finish only the receipt;
- `prewrite_lock_leftover`: the canonical zet still matches its before hash;
  keep the lock for review because no automatic cleanup is implemented;
- `ambiguous_lock`: current bytes match neither bound state or the lock and
  receipt disagree;
- `invalid_lock`: the text-free evidence cannot satisfy the revision receipt
  contract;
- `unsupported_lock`: the filename is not the v0.3.235 per-canonical shape.

The audit never deletes a lock. A lock is crash evidence, not disposable
temporary clutter until its state is understood.

## Scale And Privacy

The algorithm is
`O(receipt_files + revision_chains + lock_files)`. It opens each receipt and
lock once and each current canonical target at most once per private identity.
It does not rescan all zets for every receipt.

Output may include fixed status codes, counts, SHA-only receipt/write/lock
handles, and `audit_digest`. It does not echo zet ids or paths, proposal
filenames, reviewer ids, titles, abstract or body text, custom frontmatter
values, provider URLs, absolute paths, or secrets. It calls no model, provider,
object store, database, credential store, or network.

## Honest Stop

A green audit proves bounded local consistency for the receipt files, current
canonical hashes, and recognized locks that were scanned. It does not prove
that a correction is factually true, that no external editor can race WOM,
that backups exist, or that old content can be recreated from hashes.

Canonical revert is not implemented by this command. The v0.3.235 receipt
deliberately stores no old body text, so a future revert must require separately
recovered, privately reviewed full-zet bytes that match the recorded before
hashes. MCP exposes no duplicate receipt-audit or revision-write tool.
