# zet Abstract Receipt Lifecycle Audit

Current v0.4.0 boundary: this audit remains read-only. It may classify
historical evidence but grants no write, revert, cleanup, or recovery authority;
all three executor approvals fail with
`compound_exact_human_approval_binding_required` before private target read or
mutation.

Status: implemented as an archive-wide read-only audit in v0.3.221

## Purpose

Single-receipt writer and revert commands prove one lifecycle when the caller
already knows its receipt. Long-lived archives need a bounded way to find
forgotten, damaged, orphaned, diverged, or interrupted abstract revision state.

`zet-abstract-backfill-receipt-audit` validates the whole supported receipt and
transaction-lock surface without returning private content.

## Command

```text
archive zet-abstract-backfill-receipt-audit <archive-root> --dry-run --max-receipts 5000 --max-locks 5000 --max-problems 100 --progress --format json
```

`--dry-run` is required. Supported limits are:

```text
total apply plus revert receipts: 1 to 5,000
recognized transaction locks:     1 to 5,000
returned problem records:          1 to 500
```

If a receipt or lock count exceeds its bound, the audit blocks rather than
claiming complete coverage.

## Closed Receipt Lifecycles

Every v0.3.219 applied receipt must be in exactly one supported state.

### Applied And Current

```text
valid applied receipt
+ current canonical after-file/body/abstract hashes
+ no deterministic revert receipt
```

### Reverted And Current

```text
valid applied receipt
+ valid deterministic revert receipt bound to that source receipt SHA/path
+ current canonical before-file/body hashes
+ abstract absent
```

The command validates private schema, archive, authority, item, and target
metadata internally, including that the applied receipt filename digest matches
its recorded proposal SHA-256. It never echoes those values. Malformed or
renamed applied evidence, current-state divergence, an invalid expected revert,
or a revert receipt with no valid source receipt blocks the audit.

## Lock Classification

The audit recognizes only these private scratch lock names:

```text
.<proposal-digest>.write.lock
.<source-receipt-digest>.abstract-revert.lock
```

It reads the filename shape, never the lock file content.

| State | Meaning | Result |
|---|---|---|
| matching completed receipt exists | operation evidence is durable but temporary lock cleanup did not finish | `attention_required` warning |
| matching completed receipt is absent | process may have stopped before durable completion | unresolved-transaction blocker |
| symlink or escaped lock | unsupported trust boundary | blocker |

The command never deletes a lock. Confirm that no process is running, then use
the single-receipt audit and current hashes before any manual cleanup.

## Transaction Journal Classification

Since v0.3.265, the audit also recognizes the paired private journal names:

```text
.<proposal-digest>.write.transaction.json
.<source-receipt-digest>.abstract-revert.transaction.json
```

It validates at most `--max-locks` journals independently of the same limit on
locks. Every valid journal is bound to the archive, operation basis, final
receipt path, reviewer authority, and a bounded participant list. Current
canonical hashes classify it as `prepared`, `partially_applied`,
`fully_applied_receipt_missing`, or `divergent`. `stale_completed` is a warning
only when the journal's final receipt and complete receipt lifecycle verify;
the other states and invalid journals block. The command never resumes,
finalizes, rolls back, deletes, or repairs a journal.

## Bounded Output

Returning one healthy JSON row per receipt would recreate an AI token problem.
The audit therefore:

- scans every receipt, recognized lock, and transaction journal inside the
  requested bounds;
- counts `applied_verified` and `reverted_verified` lifecycles;
- commits all outcomes to one `audit_digest`;
- returns only bounded problem/warning rows;
- marks `problems_truncated` when the problem list is shorter than the count.

A problem row may contain kind, sorted index, state, SHA-256 digest, and blocker
codes. It contains no private path or content. The digest proves which audit
outcome set produced the summary; it is not a signature or remote backup proof.

Since v0.3.266, the result also carries an independently bounded
`transaction_journal_cases` list for the read-only recovery planner. Each case
adds only the transaction basis SHA-256, final receipt verification state, and
expected lock state to the existing operation/state/count/fixed-code surface.
The list has its own returned/truncated summary fields, so receipt or lock
problem rows cannot silently consume the recovery case budget.

## Read And Write Boundary

The command may read:

- private applied and revert receipt metadata;
- private transaction-journal metadata, including zet ids, canonical paths, and
  reviewer authority;
- selected canonical bytes needed for file/body/abstract hash validation;
- lock filenames.

It does not read lock content, proposal files, objets, credentials, environment
secrets, provider state, or external databases. It calls no model or provider.

It writes or deletes nothing. In particular, it does not:

- repair a canonical zet;
- create, edit, or delete a receipt;
- remove a lock;
- remove or rewrite a transaction journal;
- recreate a proposal;
- decide that an abstract is semantically good.

## Result Meaning

`healthy` means every supported receipt lifecycle and recognized lock was
completely checked inside the bounds, with no blocker or warning.

`attention_required` with `ok: true` means receipt lifecycles are valid but
completed-operation lock residue needs inspection.

`attention_required` with `ok: false` means evidence/current state is invalid,
or a lock has no matching completion evidence. Do not delete evidence to make
the result green.

This remains local consistency evidence. It does not prove abstract truth or
quality, safe concurrent external editing, successful remote backup, or
forced-termination recovery.

Use
`archive zet-abstract-backfill-recovery-plan <archive-root> --dry-run` to
translate retained journal evidence into a fixed human-reviewable next-step
recommendation. That separate command is also read-only and does not grant
recovery write authority.
