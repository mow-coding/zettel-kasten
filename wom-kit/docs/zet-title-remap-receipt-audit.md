# zet Title Remap Receipt And Interruption Audit

Status: v0.3.270 read-only archive-wide title-remap evidence audit

Use this command after a completed `zet-title-remap-write`, after an
unexpected process exit, or before planning any manual recovery:

```powershell
archive zet-title-remap-receipt-audit <archive-root> `
  --dry-run `
  --format json
```

The alias is:

```powershell
archive title-remap-receipt-audit <archive-root> --dry-run --format json
```

`--dry-run` is mandatory. The command never cleans up, resumes, rolls back,
finalizes, or reverts a title change.

## What It Reads

The audit performs bounded reads of:

- title-remap receipts under `receipts/revisions/title-remap/`;
- retained transaction journals under `.wom-scratch/title-remap/`;
- the one common title-remap write lock, if present;
- the current canonical bytes of receipt or journal participants;
- the exact prior-byte objects and their manifest records.

Defaults and hard ceilings are 5,000 receipts, 100 journals, and 100 returned
problem rows. `--max-problems` may be raised only to 500. A count over its
ceiling or an out-of-range option blocks the audit instead of silently
truncating evidence.

## Completed Receipt Verification

Each recognized receipt must pass all of these checks:

- a strict runtime field allowlist and duplicate-JSON-key rejection;
- safe non-symlink containment inside the archive;
- archive identity, filename, and proposal-digest binding;
- exact current after-file, after-title, and unchanged-body hashes;
- exact prior-byte snapshot object and manifest evidence.

A healthy completed receipt is counted as `receipt_verified`. A malformed,
misbound, drifted, or snapshot-invalid receipt is counted as
`receipt_invalid_or_divergent` and makes the command exit non-zero.

## Retained Transaction States

A valid retained journal is compared with every participant's current whole
file hash:

- `prepared`: every participant still matches its before hash;
- `partially_applied`: some match before and some match after;
- `fully_applied_receipt_missing`: every participant matches after, but no
  independently verified final receipt exists;
- `divergent`: at least one participant is missing, has the wrong identity, or
  matches neither recorded hash;
- `stale_completed`: every participant is covered by an independently verified
  final receipt, but the journal remains.

The common write lock must bind exactly one valid retained journal. A journal
without its matching lock, an orphan or malformed lock, an invalid journal, or
multiple journals that cannot all be represented by the one common lock
requires attention. Even `stale_completed` residue is reported; the audit does
not delete it.

## Privacy Boundary

The JSON result contains counts, fixed status or issue codes, bounded problem
rows, and a SHA-256 case handle for each retained journal. It does not echo:

- old or new title text, title hashes, or title lengths;
- zet ids or canonical paths;
- receipt, journal, lock, proposal, or snapshot paths;
- reviewer ids or proposal SHA-256 values;
- provider values or absolute local paths.

The command calls no provider or model, reads no secret store or environment
value, and has no MCP method.

## Interpreting The Exit Code

- Exit `0` with `status: healthy`: all recognized completed receipts verify
  and no retained transaction residue exists.
- Exit `0` with `status: attention_required`: only verified completed residue,
  such as a matching stale journal and lock, remains. Preserve it.
- Exit `1`: at least one receipt, journal, snapshot, lock, bound, or scan limit
  is unsafe, invalid, interrupted, or divergent.

In every case, check `write_boundary`: all values remain false.

## What To Do With Attention

Preserve every receipt, journal, lock, canonical participant, and prior-byte
snapshot. Do not hand-edit or delete transaction evidence. v0.3.270 provides
diagnosis only. Automatic recovery, approved single-case recovery, cleanup,
and approved revert from a completed title-remap receipt remain later release
work.

See:

- [Reviewed zet Title Remap Plan](zet-title-remap-plan.md)
- [Approved zet Title Remap Write](zet-title-remap-write.md)
