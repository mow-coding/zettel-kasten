# Canonical zet Revision Restore Plan

Status: latest-event-bound recovered-full-zet restore planning in v0.3.249

Current execution boundary: v0.4.12 keeps the snapshot-proposal approval path fixed closed.

`zet-revision-restore-plan` answers a narrow recovery question: does one
complete old zet recovered from a private backup exactly match the `before`
state of a valid current revision receipt?

It never tries to reconstruct text from a hash. The old Markdown bytes must
already exist in private scratch:

```text
.wom-scratch/revisions/restores/<private>.md
```

Since v0.3.248, new ordinary v0.2 revision receipts point to an exact local
before-snapshot under `objects/sha256/`. The current
`zet-revision-restore-proposal-from-snapshot --dry-run` verifies that evidence
and derives a content-addressed private destination without writing. Its
approval branch is fixed closed in the parser, nested help, and runtime before
private receipt, snapshot, archive, or target reads, so it creates no proposal.
Historical v0.3.249 executions may have left an independently preserved private
proposal, but a dry-run digest is not authority to recreate or copy one by hand.
If no complete private proposal already exists, stop and recover the old bytes
from a trusted private backup. Legacy v0.1 receipts also depend on that separate
private backup and manual placement under private restore scratch.

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

## Human Review And Next Step

`ready_for_human_review` is not restore approval and changes no file. A human
must still compare the current canonical zet, recovered old zet, and selected
receipt privately. Do not copy the recovered file over the canonical zet by
hand.

For a v0.2 ordinary revision receipt, the recommended read-only predecessor is
[Restore Proposal From A Preserved Before-Snapshot](zet-revision-restore-proposal-from-snapshot.md).
The current command materializes nothing. Only an independently preserved
historical proposal or separately recovered complete private backup may be
reviewed by this planner; neither the dry-run result nor its digest grants write
or manual-copy authority.

Since v0.3.239, pass the exact plan evidence to the separate CLI-only
`zet-revision-restore-write --dry-run`. In v0.4.0 its approval path returns
`compound_exact_human_approval_binding_required` before private target reads or
mutation; it installs no bytes and creates no lock, snapshot, journal, or
restore receipt. Historical v0.3 receipts remain readable. See
[Canonical zet Exact-Byte Restore Write](zet-revision-restore-write.md).

The command calls no model, provider, object store, database, credential store,
or network. It proves local evidence correspondence, not factual truth,
usefulness, backup completeness, external synchronization, legal clearance, or
model understanding.
