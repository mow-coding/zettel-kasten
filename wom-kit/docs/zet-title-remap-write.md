# Approved zet Title Remap Write

Status: v0.3.276 approval-gated title-only write and recovery boundary

Use this command only after `zet-title-remap-plan` reports every row as ready
and a human has compared every proposed title with its source record.

The default `--max-items` is 5,000 for both plan and write. Keep the same
explicit value on both commands if you choose a smaller bound.

## Two-Step Command

First obtain the exact write-plan digest without changing the archive:

```powershell
archive zet-title-remap-write <archive-root> `
  --proposal .wom-scratch/title-remap/<private>.jsonl `
  --expected-proposal-sha256 sha256:<proposal-digest> `
  --expected-plan-digest sha256:<plan-digest> `
  --max-items 5000 `
  --dry-run `
  --format json
```

Review the result. If it says `ready_to_apply`, run the unchanged proposal
again with the returned `write_plan_digest`:

```powershell
archive zet-title-remap-write <archive-root> `
  --proposal .wom-scratch/title-remap/<private>.jsonl `
  --expected-proposal-sha256 sha256:<proposal-digest> `
  --expected-plan-digest sha256:<plan-digest> `
  --expected-write-plan-digest sha256:<write-plan-digest> `
  --max-items 5000 `
  --approve `
  --reviewed-by person:<reviewer-id> `
  --affirm-titles-reviewed `
  --format json
```

`--approve` is rejected unless all three digests still match, the reviewer id
is safe, and the explicit affirmation is present. The command reruns the full
plan and rereads every canonical file after taking its write lock. If the
proposal or any canonical byte changed, it writes no canonical zet.

## Exact Mutation Boundary

For each accepted row the writer:

- requires exactly one top-level YAML scalar named `title`;
- replaces only that scalar;
- preserves the UTF-8 BOM state and newline convention;
- preserves every other frontmatter value;
- preserves the complete body bytes;
- does not change `updated_at`;
- calls no provider or model.

Plain, quoted, literal-block, and folded-block YAML title scalars are accepted.
A missing, duplicate, mapping, or sequence title is blocked. The proposed
title is serialized as a quoted JSON-compatible YAML scalar, so YAML syntax in
the title cannot create a second field.

## Before-Byte Snapshots

Before the first canonical write, the command stores and verifies the complete
original bytes of every participant under:

```text
objects/sha256/<first-two-hex>/<64-hex>
```

It registers missing object records in `objects/manifests/files.jsonl` under
one manifest lock and one batch append. This avoids repeatedly rescanning and
rewriting the manifest for a large proposal.

These are local content-addressed snapshots. They are strong local recovery
evidence, but they are not proof of an independent remote backup.

## Private Receipt

The final create-new receipt is stored under:

```text
receipts/revisions/title-remap/<proposal-digest>.zet-title-remap.json
```

The receipt binds:

- proposal, plan, and write-plan digests;
- reviewer affirmation;
- private zet ids and archive-relative paths;
- before/after whole-file hashes;
- before/after title hashes;
- unchanged body hashes;
- prior-byte snapshot descriptors.

It stores no old title text, new title text, or body text. The CLI does not
echo the receipt's private ids, paths, reviewer, title hashes, or snapshot
paths. Repeating the same approved command after a verified receipt returns
`already_applied` and writes nothing.

## Failure And Interruption

A caught runtime failure restores the exact original bytes of every attempted
canonical file, removes any partial receipt, verifies the rollback, and only
then removes the matching transaction journal and lock. The result is
`failed_rolled_back` when all of that succeeds.

Before the first canonical write the command creates a private transaction
journal and a common title-remap write lock under
`.wom-scratch/title-remap/`. A process kill or power interruption can therefore
leave:

- some canonical files before and some after;
- the verified prior-byte snapshots;
- the private transaction journal;
- the write lock;
- no final receipt.

Do not delete or hand-edit those retained files. v0.3.270 can inspect them
with the read-only `zet-title-remap-receipt-audit --dry-run` command, and
v0.3.271 can map a complete retained case to one fixed read-only recovery
decision with `zet-title-remap-recovery-plan --dry-run`. v0.3.272 can
execute one reviewed safe action with `zet-title-remap-recover`; it restores
uncommitted writes only toward verified prior bytes or cleans verified
transaction residue. It does not resume, finalize, or revert a completed title
change.

On Windows the implementation uses atomic replacement and flushes file
contents. Windows does not provide the same directory `fsync` guarantee as
POSIX, so this is not a claim of power-loss-proof storage.

## Current Boundary

The v0.3.269 writer, v0.3.270 auditor, v0.3.271 recovery planner, v0.3.272
single-case executor, v0.3.273 completed-receipt revert planner, v0.3.274
approved revert writer, v0.3.275 read-only revert recovery planner, and
v0.3.276 approved revert recovery executor implement:

- read-only title proposal planning;
- approval-gated title-only batch write;
- exact prior-byte snapshots;
- private final receipts;
- ordinary-failure rollback;
- hard-exit transaction evidence;
- archive-wide completed-receipt and retained-transaction diagnosis;
- one fixed privacy-safe recovery decision per complete retained case.
- approval-gated safe-direction rollback or verified residue cleanup for one
  freshly rebound interrupted case.
- read-only exact prior-byte compensation planning for one clean completed
  receipt.

v0.3.274 additionally implements the separately reviewed, approval-gated
completed-receipt compensation:

- exact prior-byte restoration for one clean completed receipt;
- preservation of the original apply receipt;
- a separate immutable compensation receipt;
- caught-failure rollback to exact applied bytes;
- retained revert journal diagnosis after a hard exit.

v0.3.275 maps a complete retained revert transaction to one fixed read-only
decision. v0.3.276 can execute its non-forensic actions only after rebinding
the complete plan, exact case/action, fresh review, and archive quiescence.
There is still no automatic recovery direction selection or unreviewed title
mutation.

See [zet Title Remap Receipt And Interruption Audit](zet-title-remap-receipt-audit.md)
and [zet Title Remap Recover](zet-title-remap-recover.md).
For the completed-receipt review boundary, see
[zet Title Remap Completed-Receipt Revert Plan](zet-title-remap-revert-plan.md)
and [Approved zet Title Remap Revert](zet-title-remap-revert.md), then use the
[zet Title Remap Revert Recovery Plan](zet-title-remap-revert-recovery-plan.md)
and [zet Title Remap Revert Recover](zet-title-remap-revert-recover.md) only
for retained hard-exit revert evidence.
