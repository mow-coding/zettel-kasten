# Restore Proposal From A Preserved Before-Snapshot

Status: approval-gated private proposal materialization in v0.3.249

`zet-revision-restore-proposal-from-snapshot` closes the local gap between a
v0.2 canonical revision receipt and the existing human-reviewed restore
workflow. It copies the receipt's verified prior zet bytes into private restore
scratch without changing canonical memory.

Start with a no-write preview:

```powershell
archive zet-revision-restore-proposal-from-snapshot <archive-root> `
  --receipt receipts/revisions/canonical/<digest>.zet-revision.json `
  --expected-receipt-sha256 <sha256> `
  --dry-run `
  --format json
```

If the result is green, approve only the unchanged plan:

```powershell
archive zet-revision-restore-proposal-from-snapshot <archive-root> `
  --receipt receipts/revisions/canonical/<digest>.zet-revision.json `
  --expected-receipt-sha256 <sha256> `
  --expected-plan-digest <sha256> `
  --approve `
  --format json
```

The alias is `zet-restore-proposal-from-snapshot`.

## Required Evidence

The command requires:

- a healthy complete canonical revision receipt audit;
- an immutable ordinary revision receipt using
  `wom-kit/zet-revision-receipt/v0.2`;
- the exact expected receipt SHA-256;
- a valid `before_snapshot` bound to the receipt's complete `before` file
  hash;
- exact local snapshot bytes at the content-addressed object path;
- a matching local object-manifest record; and
- on approval, the exact unchanged materialization `plan_digest`.

Legacy v0.1 receipts remain valid history, but they cannot use this command
because they never promised that prior bytes were preserved.

## Copy Boundary

The destination is derived from the snapshot hash:

```text
.wom-scratch/revisions/restores/<sha256>.before-snapshot.md
```

The file is an independent copy. It is never a hard link to the immutable
object, so reviewing or editing the proposal cannot alter preserved history.
An existing destination must already contain the exact bytes and must have a
different storage identity from the object. Any other collision blocks and is
never overwritten.

The output may echo this content-addressed relative path, hashes, counts, and
fixed status codes. It does not echo the receipt path, canonical path, zet id,
reviewer, title, abstract/body text, custom frontmatter values, provider URL,
absolute local path, or secret.

## What It Does Not Approve

`materialized` means only that a reviewable private copy exists. It does not
mean that the old state is true, preferred, current, reviewed, or approved for
canonical installation.

Next, inspect the private proposal and current canonical zet together. Then run
`zet-revision-restore-plan --dry-run` with the returned proposal path. Only the
separate `zet-revision-restore-write` preview, explicit human review
affirmations, and final approval may change canonical memory.

The command writes no receipt because the proposal is a reproducible private
working file whose source remains the immutable v0.2 receipt and snapshot. It
still appears in `ai-artifact-inventory` as
`zet_revision_restore_proposal`, so a later AI session does not mistake it for
an ordinary working note or forget that a restore review is pending. It
does not call a model, provider, remote object store, database, credential
store, or network, and it does not claim remote backup completeness.
