# Canonical zet Exact-Byte Restore Write

Status: v0.4.0 dry-run-only exact-byte restore planning; historical receipts remain readable

`zet-revision-restore-write` does not recreate missing words from hashes. Its
dry-run verifies complete old zet bytes that were separately recovered into
private scratch and accepted by `zet-revision-restore-plan`. The historical
writer changes canonical bytes, receipt history, and lock state as one compound
effect. v0.4.0 has no exact-human binding for that complete effect set, so its
approve path is intentionally closed.

## Three Steps

First run the read-only plan and privately review the current zet, recovered
old zet, and selected immutable receipt together:

```powershell
archive zet-revision-restore-plan <archive-root> `
  --receipt receipts/revisions/canonical/<digest>.zet-revision.json `
  --expected-receipt-sha256 <sha256> `
  --restore-proposal .wom-scratch/revisions/restores/<private>.md `
  --dry-run --format json
```

Then preview the exact write. Copy the current file hash, recovered file and
semantic hashes, and restore-plan digest from the plan result:

```powershell
archive zet-revision-restore-write <archive-root> `
  --receipt receipts/revisions/canonical/<digest>.zet-revision.json `
  --expected-receipt-sha256 <sha256> `
  --restore-proposal .wom-scratch/revisions/restores/<private>.md `
  --expected-current-sha256 <sha256> `
  --expected-restore-proposal-sha256 <sha256> `
  --expected-restore-proposal-semantic-sha256 <sha256> `
  --expected-restore-plan-digest <sha256> `
  --revision-at <timezone-aware-event-time> `
  --dry-run --format json
```

Do not rerun it as an approved write. Any `--approve` request stops before
private target read or mutation with:

```text
compound_exact_human_approval_binding_required
```

Aliases `canonical-revision-restore-write` and `zet-restore-write` have the
same gate. Reviewer and affirmation flags cannot bypass it.

## Historical Exact-Byte Contract

Existing v0.3 receipts describe a writer that used the same private
per-canonical lock as ordinary
`zet-revision-write`. Immediately before mutation it repeats the complete
history, source receipt, current state, recovered proposal, policy, event-time,
and digest checks.

The canonical file is replaced atomically with the proposal bytes exactly as
reviewed. WOM does not reserialize YAML or alter BOM, newlines, field order,
body text, frontmatter values, or the recovered historical `updated_at`. The
new restore event time lives in its immutable receipt instead.

The restore receipt uses a separate schema and action but the same
`receipts/revisions/canonical/` event directory. Its before/after file,
semantic, abstract, and body hashes join the ordinary and restore events into
one chronological chain. It also supplies reviewed abstract/body evidence to
`abstract-freshness` without storing either text.

v0.4.0 does not enter that writer, replace a canonical zet, create a lock, or
append a restore receipt.

## Historical Failure And Restart Evidence

Handled runtime failure restores the exact previous canonical bytes, removes
any partial restore receipt, and removes the transaction lock when rollback
succeeds.

A forced process stop may leave the private lock. Rerun the exact approved
command; do not delete or edit the lock manually. A matching rerun can:

- resume when the canonical zet still has its prewrite bytes;
- create only the missing receipt when the exact restored bytes are present;
- remove a completed lock after both canonical bytes and receipt verify.

A mismatched lock, source receipt, proposal, policy, event time, reviewer,
affirmation, or digest blocks without guessing.

## Honest Boundary

A v0.4.0 result proves only that the exact restore effect was planned without
writing and cannot report `applied`. Historical `applied` receipts remain
auditable evidence of their recorded local event, not authority for replay.
The command calls no model, provider, object store, database, credential store,
or network, and MCP exposes no restore writer duplicate.
