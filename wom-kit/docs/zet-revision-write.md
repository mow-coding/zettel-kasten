# Canonical zet Revision Write

Status: approval-gated single-zet write in v0.3.235

`zet-revision-write` is the second half of WOM's ordinary canonical correction
workflow. It accepts only a private proposal that already passed
`zet-revision-plan`, builds the exact writer-produced candidate in a separate
dry-run, and replaces the canonical zet only after explicit human approval.

The command does not decide whether a correction is true. It proves that the
bytes being written still match the proposal and both review steps that the
operator approved.

## Step 1: Review The Proposal

Run the read-only plan first:

```powershell
archive zet-revision-plan <archive-root> `
  --zettel-id <safe-id> `
  --proposal .wom-scratch/revisions/<private-name>.md `
  --dry-run `
  --format json
```

Keep these four returned values:

```text
canonical.sha256
proposal.sha256
proposal.semantic_sha256
plan_digest
```

Review the complete private proposal and its current canonical zet together.
The plan is not approval and writes nothing.

## Step 2: Preview The Exact Write

Pass all four values into the writer's dry-run:

```powershell
archive zet-revision-write <archive-root> `
  --zettel-id <safe-id> `
  --proposal .wom-scratch/revisions/<private-name>.md `
  --expected-canonical-sha256 <canonical.sha256> `
  --expected-proposal-sha256 <proposal.sha256> `
  --expected-proposal-semantic-sha256 <proposal.semantic.sha256> `
  --expected-plan-digest <plan_digest> `
  --dry-run `
  --format json
```

When `--revision-at` is omitted, dry-run creates one timezone-aware UTC value.
Keep both:

```text
revision_at
write_plan.actual_digest
```

The writer candidate is deterministic for those inputs. It uses the reviewed
proposal content, serializes frontmatter in WOM's standard YAML form, sets
`updated_at` to `revision_at`, and normalizes the body to one final newline.
Dry-run returns only hashes and change categories. It writes no candidate,
canonical file, receipt, lock, provider state, objet, or database row.

## Step 3: Approve The Bound Write

Reuse the same values and add the write-plan digest, reviewer, and review
affirmations:

```powershell
archive zet-revision-write <archive-root> `
  --zettel-id <safe-id> `
  --proposal .wom-scratch/revisions/<private-name>.md `
  --expected-canonical-sha256 <canonical.sha256> `
  --expected-proposal-sha256 <proposal.sha256> `
  --expected-proposal-semantic-sha256 <proposal.semantic.sha256> `
  --expected-plan-digest <plan_digest> `
  --revision-at <revision_at> `
  --expected-write-plan-digest <write_plan.actual_digest> `
  --approve `
  --reviewed-by <safe-actor-id> `
  --affirm-revision-reviewed `
  --affirm-abstract-body-pair-reviewed `
  --format json
```

If `change_summary.edges_changed` is true, approval also requires:

```text
--affirm-edge-changes-reviewed
```

Any changed canonical byte, proposal byte, proposal meaning, timestamp,
candidate, or plan digest blocks the write. Generate a new read-only plan
instead of reusing stale approval.

## Write And Receipt Boundary

Approval:

- uses one private lock shared by every revision plan for the same canonical
  zet, so distinct plans cannot race through the write section;
- writes one canonical zet through atomic replacement;
- verifies the replacement bytes immediately;
- creates one new immutable receipt under
  `receipts/revisions/canonical/<write-plan-digest>.zet-revision.json`;
- stores reviewer id, canonical identity/path, timestamps, fixed change
  categories, and before/after hashes in the private receipt;
- stores no title, abstract text, body text, or custom frontmatter value in the
  receipt;
- records the reviewed abstract/body hash pair so `abstract-freshness` can
  recognize the revised zet as fresh;
- calls no model, provider, object store, database, credential store, or
  network.

CLI output does not echo the zet id, canonical path, proposal filename,
reviewer id, title, abstract, body, custom frontmatter value, provider URL,
absolute path, or secret. The digest-only receipt path is safe to return.

## Failure And Interruption Safety

An ordinary runtime failure after canonical replacement restores the exact
previous canonical bytes, removes a partial receipt, and removes the temporary
private write lock. If the process is interrupted after the atomic replacement
but before receipt creation, the private lock retains text-free before/after
hashes and review bindings. Rerunning the exact approved command recognizes the
already-written candidate and finishes the receipt without writing the
canonical zet again.

The write lock is keyed to canonical identity rather than one proposal. A
second plan for the same zet therefore stops while the first transaction is in
progress, even when the proposals and write-plan digests differ.

An unexpected lock or mismatched state is never deleted automatically. It
blocks and stays available for human inspection.

## Honest Stop

`applied` proves that the reviewed, SHA-bound local proposal was installed and
receipted. It does not prove factual truth, completeness, usefulness, legal or
copyright clearance, external synchronization, backup completion, or model
understanding. MCP exposes the read-only `zet_revision_plan` tool but no
revision write tool; canonical mutation remains an explicit local CLI approval.
