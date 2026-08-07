# Artifact Lifecycle Inventory

`archive artifact-lifecycle-inventory` is the safe first answer to this
question:

```text
What temporary, unresolved, expiring, generated, or locally unmanifested
material is visible in WOM's declared lifecycle areas right now?
```

It is a read-only checkpoint. It is not a cleanup command.

## Beginner Summary

Think of this command as a stock-taking sheet for selected WOM storage areas.
It counts and classifies what is there, tells you whether every declared area
was completely checked, and points to the narrower review tool that comes
next.

It never means:

```text
listed = safe to delete
old = safe to delete
not in the manifest = orphan = safe to delete
```

Those conclusions require separate preservation evidence and human review.

## Run It

```powershell
archive artifact-lifecycle-inventory <archive-root> --dry-run --format json
```

Paths are hidden by default. For an attended local review only:

```powershell
archive artifact-lifecycle-inventory <archive-root> --dry-run --show-relative-paths --format json
```

If a declared root contains more than the default 10,000 filesystem entries,
the command blocks its completeness claim. An operator can deliberately raise
the independent per-root ceiling, up to 100,000:

```powershell
archive artifact-lifecycle-inventory <archive-root> --dry-run --max-entries-per-root 50000 --format json
```

`--max-items` controls only how many review rows are listed. It does not turn a
truncated filesystem scan into a complete one.

## Declared Scope

The command scans only fixed archive-owned lifecycle areas:

| Root or exact surface | Class | Meaning |
| --- | --- | --- |
| `.wom-scratch/` | `DISPOSABLE_AFTER_REVIEW` | Private operational or AI scratch; preservation and active-operation evidence must be reviewed first. |
| `workbench/ai-scratch/` | `DISPOSABLE_AFTER_REVIEW` | AI working files awaiting a fate decision. |
| `staging/ai/inbox/`, `staging/ai/reviewed/` | `DURABLE_UNTIL_RESOLVED` | AI intake whose lifecycle is still open. |
| `tmp/` | `DISPOSABLE_AFTER_REVIEW` | Temporary files, still requiring explicit review. |
| `staging/incoming/` | `DURABLE_UNTIL_RESOLVED` | Capture staging; use `staged-cleanup-check` before any manual removal. |
| `inbox/` | `DURABLE_UNTIL_RESOLVED` | Draft zets that remain unresolved. |
| `workpacks/` | `DURABLE_WITH_EXPIRY` | Transfer packages with active, expired, unknown, missing, or invalid expiry control metadata. |
| `objects/sha256/` | `DURABLE_ARCHIVE_RECORD` | Local content-addressed objet bytes. Bodies are not opened or hashed. |
| `objects/derived-text/sha256/` | `DURABLE_ARCHIVE_RECORD` | Local derived-text bytes; only metadata counts are collected here. |
| exact `db/archive-index.sqlite*` files | `REBUILDABLE_GENERATED` | Known generated index and sidecars. The rest of `db/` is not broadly classified. |
| in-root `objets/` marker | `EXTERNAL_LIVE_NEVER_TOUCH` | Non-canonical original storage. Only root presence is checked; children are never enumerated. |

It does not scan:

- arbitrary paths supplied by an AI,
- the whole archive,
- a sibling `<archive>-objets` store,
- GitHub, R2, S3, B2, databases, or another provider,
- secret stores, credentials, or environment values.

Therefore a clear result means only that the declared local scope was clear.
Unknown archive locations may still exist.

## Coverage Evidence

Each root reports:

- whether it exists,
- scan mode,
- entries, regular files, directories, and byte counts,
- whether the independent root ceiling was reached,
- unreadable or special entries,
- skipped symbolic links or Windows reparse points,
- entries that changed during the scan,
- whether that root's declared coverage completed.

The whole result includes `coverage.complete` and an `inventory_digest`. The
digest does not depend on whether relative paths were shown, so a private local
path review and the default content-free result can still refer to the same
inventory snapshot.

If a link, reparse point, unreadable entry, change, or limit prevents complete
inspection, the command exits blocked. It never turns skipped material into a
zero count.

## Local Object Candidates

The inventory strictly reads the bounded control manifest at
`objects/manifests/files.jsonl` and compares its unique complete object ids
with canonical local names shaped like:

```text
objects/sha256/<first-two-hex>/<64-lowercase-hex>
```

A canonical local name whose id is absent from a complete valid manifest is
reported as:

```text
unmanifested_local_object_candidate
```

That label is deliberately not `orphan`. The command does not read or hash the
bytes, check every possible provenance record, or grant deletion approval.
Malformed JSON, duplicate JSON keys, duplicate object ids, unsafe manifest
files, invalid object ids, changed descriptor/path snapshots, size/record
limits, and invalid local layouts block reconciliation.

## Workpack Retention

Top-level `workpacks/<package>/package.yml` files are bounded control metadata.
The inventory classifies their `expires_at` as:

- active,
- expired and requiring review,
- unknown,
- missing,
- invalid.

The package file is opened through a verified descriptor, reread only within a
1 MiB ceiling, and rejects duplicate YAML keys and aliases. A concurrent path
replacement or unstable metadata snapshot blocks instead of being parsed.

Expiry alone never permits deletion. Purpose, counterparty obligations,
receipts, provenance, and any applicable retention rule must still be reviewed.

## Privacy And Mutation Boundary

Ordinary artifact bodies are never read. The command may read only bounded
object-manifest rows and workpack package metadata. It calculates no content
hashes, reads no object bytes, writes no files or zets, deletes nothing, calls
no provider, and emits no absolute path.

Default review rows contain a stable `artifact_ref`, fixed root/class/state,
entry kind, byte count, timestamp, and age bucket. They do not contain the
archive-relative path, object id, workpack id, artifact body, provider value,
or secret.

## What To Do Next

Use the narrower tool that matches the finding:

- AI scratch or AI staging: `archive ai-artifact-inventory --dry-run`;
- capture staging: `archive staged-cleanup-check --dry-run` on one human-selected folder;
- in-root `objets/`: `archive doctor --strict` plus the migration in [Artifact Hygiene](artifact-hygiene.md);
- workpack expiry: attended retention and receipt review;
- unmanifested local object candidate: forensic hold and manifest-lineage repair;
- generated index: keep it unless a separate rebuild decision is made.

WOM v0.3.303 still has no systematic delete-all `gc`, provider cleanup,
external-store sweep, or automatic staged-folder deletion executor.
