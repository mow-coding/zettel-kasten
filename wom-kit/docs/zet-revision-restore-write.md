# Canonical zet Exact-Byte Restore Write

Status: approval-gated exact-byte canonical restore in v0.3.239

`zet-revision-restore-write` completes one evidence-backed recovery loop. It
does not recreate missing words from hashes. It installs only complete old zet
bytes that were separately recovered into private scratch and accepted by
`zet-revision-restore-plan`.

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

Only after private human review, rerun the unchanged command with the returned
`write_plan.actual_digest`:

```powershell
archive zet-revision-restore-write <archive-root> `
  <the-same-bound-inputs-and-revision-at> `
  --expected-write-plan-digest <sha256> `
  --approve `
  --reviewed-by person:<reviewer> `
  --affirm-restore-reviewed `
  --affirm-abstract-body-pair-reviewed `
  --format json
```

Add `--affirm-edge-changes-reviewed` when the plan says edges changed. Aliases
are `canonical-revision-restore-write` and `zet-restore-write`.

## Exact-Byte Contract

The approved writer uses the same private per-canonical lock as ordinary
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

## Failure And Restart

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

`applied` proves exact reviewed local replacement and a continuous local
receipt history. It does not prove factual truth, backup completeness,
external synchronization, legal clearance, or model understanding. The
command calls no model, provider, object store, database, credential store, or
network, and MCP exposes no restore writer duplicate.
