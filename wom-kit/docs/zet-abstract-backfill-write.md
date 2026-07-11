# zet Abstract Backfill Write

Status: implemented as an approval-gated transactional write in v0.3.219

## Purpose

`zet-abstract-backfill-plan` proves that proposed first-read text is structurally
safe and bound to exact current canonical bytes. It does not decide that the
text is true or grant permission to change canonical knowledge.

`zet-abstract-backfill-write` is the separate human-authority boundary. It can
add reviewed `frontmatter.abstract` values only after the proposal has been
inspected and explicitly approved.

## Required Flow

1. Read only a selected missing-abstract canonical zet.
2. Prepare the private proposal under `.wom-scratch/abstract-backfill/`.
3. Run `zet-abstract-backfill-plan --dry-run`.
4. Retain `proposal.sha256` and inspect every proposed abstract as a human.
5. Preview the writer with that exact proposal hash.
6. Approve only after all rows have been reviewed.

Preview:

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<private>.jsonl --expected-proposal-sha256 <proposal.sha256> --max-items 500 --dry-run --progress --format json
```

Approved write:

```text
archive zet-abstract-backfill-write <archive-root> --proposal .wom-scratch/abstract-backfill/<private>.jsonl --expected-proposal-sha256 <proposal.sha256> --max-items 500 --approve --reviewed-by person:<reviewer> --affirm-abstracts-reviewed --progress --format json
```

Exactly one of `--dry-run` and `--approve` is required. A new approved write
also requires a safe reviewer id and the explicit review affirmation. An AI
must never infer either one from a green plan or from prior conversation.

## Revalidation

Before a new mutation, WOM-kit:

1. hashes the complete private proposal and matches the caller's expected hash;
2. reruns the v0.3.218 planner;
3. rereads and rehashes the proposal;
4. resolves every target by zet id and confirms canonical path/status;
5. matches every current file against its expected exact-byte SHA-256;
6. reconstructs the one-field candidate and matches the plan fingerprints;
7. rechecks each exact source byte sequence immediately before its write.

Any mismatch blocks the entire batch before a canonical write.

## Mutation Contract

The only allowed semantic change is:

```text
missing frontmatter.abstract -> reviewed frontmatter.abstract
```

The writer preserves:

- a UTF-8 BOM when present;
- LF or CRLF style;
- exact body bytes;
- every other parsed frontmatter field and value;
- `updated_at` as-is.

It does not call a model/provider, write an objet, update an external database,
or build a map/index.

## Transaction And Rollback

The writer snapshots exact source bytes in memory, applies candidates with
atomic file replacement, verifies every result, and writes the batch receipt
last. If any item or receipt operation raises an in-process error, it restores
every attempted canonical target byte-for-byte and removes an incomplete
receipt.

Safety limits are:

```text
one canonical zet: 16 MiB
one write batch:   256 MiB of source canonical bytes
proposal:          64 MiB, 1 MiB per line, at most 5,000 rows
```

A private short-lived proposal lock blocks another WOM writer using the same
proposal during the transaction. It is advisory and does not lock external
editors.

This is an in-process transaction, not a durable filesystem transaction.
Forced process termination, power loss, or machine failure can interrupt after
a canonical replacement and before receipt/cleanup. v0.3.219 deliberately
writes no body-bearing crash-recovery journal. If a `.write.lock` remains after
a crash, do not delete it blindly: inspect the proposal hash, target file
hashes, and deterministic receipt first.

## Receipt

Success writes one deterministic private archive receipt:

```text
receipts/revisions/abstract-backfill/<proposal-digest>.zet-abstract-backfill.json
```

The receipt records:

- proposal SHA-256 and plan digest;
- attributed reviewer and explicit affirmation;
- private target zet ids and canonical paths;
- per-row before-file, after-file, body, and abstract SHA-256;
- the one-field mutation and runtime rollback contract.

It stores no body text and no abstract text. The receipt is durable private
metadata and may follow the private archive's metadata backup policy. The
proposal remains disposable private scratch and must not enter the public
repository.

## Idempotency

The receipt path is derived from the complete proposal digest. On a matching
re-run, WOM-kit validates the receipt and every current canonical after-hash,
abstract hash, and body hash. A complete match returns `already_applied` and
writes nothing. Divergence blocks; it is not silently repaired or overwritten.

Since v0.3.220, the applied receipt can enter the separate
[`zet Abstract Backfill Revert`](zet-abstract-backfill-revert.md). That command
can remove only this exact batch when every canonical file still matches the
recorded applied state and deterministic line removal restores every before
hash. It preserves this source receipt and writes a separate inverse receipt.

## Public Output Boundary

Command output may include row indexes, counts, generation modes, hashes,
blocker codes, and the digest-only receipt path. It does not echo:

- proposal filename;
- zet ids or canonical paths;
- titles, bodies, or abstract text;
- reviewer value;
- absolute local paths;
- provider URLs or secret values.

The receipt is more detailed because it lives inside the private archive. Do
not paste it into a public issue or release report.
