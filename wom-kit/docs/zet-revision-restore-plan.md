# Canonical zet Revision Restore Plan

Status: latest-event-bound recovered-full-zet restore planning in v0.3.238

`zet-revision-restore-plan` answers a narrow recovery question: does one
complete old zet recovered from a private backup exactly match the `before`
state of a valid current revision receipt?

It never tries to reconstruct text from a hash. The old Markdown bytes must
already exist in private scratch:

```text
.wom-scratch/revisions/restores/<private>.md
```

Run:

```powershell
archive zet-revision-restore-plan <archive-root> `
  --receipt receipts/revisions/canonical/<digest>.zet-revision.json `
  --expected-receipt-sha256 <sha256> `
  --restore-proposal .wom-scratch/revisions/restores/<private>.md `
  --dry-run `
  --format json
```

Aliases are `canonical-revision-restore-plan` and `zet-restore-plan`.

## What Must Match

The planner first requires the archive-wide `zet-revision-receipt-audit` to be
healthy. This prevents a selected receipt from looking valid in isolation
while the complete revision history is branched, incomplete, drifted, or held
by an unresolved transaction lock.

It then requires:

- the exact selected immutable receipt SHA-256;
- a valid receipt schema, archive identity, digest filename, timestamp, human
  review, edge review, and abstract/body review basis;
- proof that the selected receipt is the actual newest event for the target,
  not an older receipt whose after-state bytes happen to match again;
- the current canonical zet's file, semantic, abstract, and body hashes to
  equal the receipt's complete `after` state;
- the recovered private proposal's same four hashes to equal the receipt's
  complete `before` state;
- no per-canonical revision transaction lock for the target.

The old bytes are also checked against current publication policy. Historical
membership alone does not bypass today's frontmatter schema, explicit abstract,
canonical kind, object-reference, edge, private-locator, quality, or
self-containment checks.

## Review Digest

`plan_digest` binds the full archive audit digest, selected receipt, actual
event-chain tip, current state, recovered state, fixed restore change
categories, and current policy results. If a receipt, canonical file,
recovered file, revision chain, selected tip, or local policy changes, a later
plan is different.

The JSON output may include SHA-256 values, fixed booleans and status codes,
bounded counts, and the plan digest. It does not echo the actual zet id/path,
receipt path, proposal filename, reviewer id, title, abstract/body text, custom
frontmatter value, provider URL, absolute local path, or secret.

## Honest Stop

`ready_for_human_review` is not restore approval and changes no file. A human
must still compare the current canonical zet, recovered old zet, and selected
receipt privately.

No approved restore writer exists in v0.3.238. Do not copy the recovered file
over the canonical zet by hand. A future writer must repeat the whole-history
and exact-state checks, require explicit restore and abstract/body review plus
changed-edge review, serialize with ordinary revision writes, atomically
restore exact reviewed bytes, and create an immutable restore receipt with
honest rollback and interruption recovery.

The command calls no model, provider, object store, database, credential store,
or network. It proves local evidence correspondence, not factual truth,
usefulness, backup completeness, external synchronization, legal clearance, or
model understanding.
