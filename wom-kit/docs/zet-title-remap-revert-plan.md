# zet Title Remap Completed-Receipt Revert Plan

Status: v0.3.273 read-only completed-title compensation planning

## Command

```powershell
archive zet-title-remap-revert-plan <archive-root> `
  --receipt receipts/revisions/title-remap/<digest>.zet-title-remap.json `
  --expected-receipt-sha256 sha256:<reviewed-receipt-digest> `
  --max-items 500 `
  --dry-run `
  --format json
```

Alias:

```powershell
archive title-remap-revert-plan <archive-root> ... --dry-run
```

`--dry-run` is mandatory. This command writes and deletes nothing.

## What The Plan Proves

The selected immutable source receipt must still be the exact file reviewed by
the operator. The command then:

1. runs the complete bounded title receipt, transaction-journal, and common-lock
   audit;
2. requires that audit to be healthy, complete, and free of retained
   transaction residue;
3. requires every current canonical participant to match the source receipt's
   recorded applied whole-file, title, and body hashes;
4. re-verifies every content-addressed prior-byte snapshot and its object
   manifest record;
5. parses both current and prior bytes privately and proves the transition was
   title-only: applying the current title to the prior bytes recreates the
   current bytes exactly;
6. binds the source receipt, current applied state, prior-byte targets, complete
   history-audit digest, and future revert-receipt location into one
   `plan_digest`.

The exact-transition check means a future compensation may restore only the
complete prior bytes already preserved before the original write. It may not
construct a new approximation of the old file.

## Why This Is A Compensation

The original title-remap receipt remains immutable. A future approved revert
must append a separate revert receipt that points back to the original
receipt. It must not delete or rewrite history.

This follows the same narrow principle as `git revert`: record a new operation
that reverses an earlier committed change while preserving the earlier record.
It also follows the compensating-transaction rule that current state must be
rechecked before undoing work, because blindly restoring an old value could
overwrite a later concurrent edit.

Primary references:

- https://git-scm.com/docs/git-revert.html
- https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction

## Privacy Boundary

The plan returns the source receipt SHA-256, the complete audit digest, one
plan digest, counts, and fixed content-free status codes. It does not echo:

- old or new title text, hashes, or lengths;
- zet ids or canonical paths;
- source proposal SHA-256 or reviewer id;
- receipt, snapshot, journal, lock, provider, or absolute local paths;
- canonical body text.

No provider or model is called. The command has no MCP method.

## Current Write Boundary

v0.3.273 does not implement the approved revert writer. A ready plan is review
evidence, not write authority. Do not copy the snapshot over a canonical zet by
hand.

A later writer must rerun the complete plan, bind the unchanged source-receipt
SHA-256 and plan digest, serialize with the title writer, require explicit
human review and archive quiescence, publish a crash-recovery journal before
the first canonical write, restore only verified prior bytes, preserve the
source receipt, and create a new immutable text-free revert receipt.

See also:

- [Approved zet Title Remap Write](zet-title-remap-write.md)
- [zet Title Remap Receipt And Interruption Audit](zet-title-remap-receipt-audit.md)
- [zet Title Remap Recover](zet-title-remap-recover.md)
