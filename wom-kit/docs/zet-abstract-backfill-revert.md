# zet Abstract Backfill Revert

Status: implemented as a receipt-audited approval-gated revert in v0.3.220

## Purpose

An abstract backfill is a canonical interpretation added under explicit human
authority. Removing it later is another canonical decision, not cleanup.

`zet-abstract-backfill-revert` uses the immutable v0.3.219 applied receipt to
prove whether the complete batch can be returned to its exact pre-backfill
bytes. The private proposal file is not required.

## Required Inputs

Retain these values from the successful writer result:

```text
receipt.path
receipt.sha256
```

The source receipt must remain under:

```text
receipts/revisions/abstract-backfill/<proposal-digest>.zet-abstract-backfill.json
```

## Read-Only Audit

Run dry-run first:

```text
archive zet-abstract-backfill-revert <archive-root> --receipt receipts/revisions/abstract-backfill/<digest>.zet-abstract-backfill.json --expected-receipt-sha256 <receipt.sha256> --max-items 500 --dry-run --progress --format json
```

`ready_to_revert` means WOM-kit verified:

1. the complete source receipt bytes match the expected SHA-256;
2. the receipt schema, archive id, proposal hash, plan hash, human authority,
   item count, and per-row fields are valid;
3. every target still resolves to the same canonical zet path and id;
4. every current file matches the receipt's applied `after_file_sha256`;
5. every current abstract and decoded body matches its recorded hash;
6. the first frontmatter line is exactly the deterministic `abstract:` line
   produced by the v0.3.219 writer;
7. removing only that line reconstructs the exact recorded
   `before_file_sha256`.

The audit reads canonical bytes but writes nothing. Green is reversibility
evidence, not removal authority.

## Approved Revert

A human must review removal of every abstract in the source receipt. Only then:

```text
archive zet-abstract-backfill-revert <archive-root> --receipt receipts/revisions/abstract-backfill/<digest>.zet-abstract-backfill.json --expected-receipt-sha256 <receipt.sha256> --max-items 500 --approve --reviewed-by person:<reviewer> --affirm-abstract-removal-reviewed --progress --format json
```

Exactly one of `--dry-run` and `--approve` is required. A new approved revert
also requires a safe reviewer id and the explicit removal-review affirmation.
An AI must never infer either from the source approval, a green audit, or prior
conversation.

## Mutation Contract

The only allowed action is:

```text
exact v0.3.219 applied bytes -> exact source-receipt before bytes
```

That inverse removes only the deterministic inserted `frontmatter.abstract`
line. It preserves:

- exact BOM and newline bytes;
- exact body bytes;
- every other frontmatter byte and parsed value;
- `updated_at` as-is;
- the original applied receipt.

Any later canonical edit, including an unrelated frontmatter edit, body change,
newline change, abstract change, or line relocation, blocks the whole batch. The
command does not guess which change should win.

## Transaction And Failure Rollback

The command holds bounded in-memory copies of the current applied bytes, writes
each exact reconstructed before image with atomic replacement, verifies every
target, and writes the revert receipt last.

If any item or revert-receipt operation raises an in-process error, every
attempted target is restored to its exact applied bytes and an incomplete revert
receipt is removed.

Limits remain:

```text
one canonical zet: 16 MiB
one revert batch:  256 MiB of applied canonical bytes
source receipt:    16 MiB
receipt rows:      at most 5,000
```

A short-lived lock under `.wom-scratch/abstract-backfill/` blocks another WOM
revert for the same source receipt. It does not lock an external editor.

This is not crash recovery. Forced process termination, power loss, or machine
failure can bypass in-process rollback. A leftover `.abstract-revert.lock` must
be inspected against the source receipt, deterministic revert receipt, and
current canonical hashes before manual removal.

## Revert Receipt

Success writes:

```text
receipts/revisions/abstract-backfill-reverts/<source-receipt-digest>.zet-abstract-backfill-revert.json
```

It records:

- source receipt path and exact SHA-256;
- source proposal SHA-256 and plan digest;
- attributed removal reviewer and explicit affirmation;
- private target zet ids and canonical paths;
- applied, reverted, removed-abstract, and body hashes;
- exact-before restoration and runtime rollback contracts.

It stores no body text and no abstract text. The source receipt is never deleted
or modified. Together, the two immutable receipts explain both decisions.

## Idempotency And Reapplication

On a matching re-run, WOM-kit validates the deterministic revert receipt and
every current canonical reverted/body hash plus abstract absence. A complete
match returns `already_reverted` and writes nothing.

The old applied receipt stays closed by its revert receipt. Reapplying even the
same abstract text later requires a newly reviewed proposal byte sequence with
a new proposal SHA-256 and a new applied receipt identity. Do not delete or edit
old receipts to force reuse.

## Public Output Boundary

Command output may include safe status, row indexes, counts, generation modes,
hashes, blocker codes, and the digest-only revert receipt path. It does not echo:

- source receipt path;
- zet ids or canonical paths;
- titles, bodies, or abstract text;
- reviewer value;
- absolute local paths;
- provider URLs or secret values.

Both receipts contain private archive metadata. Do not paste them into public
issues or release reports.
