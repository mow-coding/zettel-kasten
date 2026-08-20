# Canonical zet Revision Write

Status: v0.4.0 dry-run-only revision effect planning; v0.3 receipts remain readable

`zet-revision-write` accepts only a private proposal that already passed
`zet-revision-plan` and builds the exact writer-produced candidate in a
separate dry-run. Its historical writer changes canonical bytes, private
snapshot/manifest state, lock state, and receipt history as one compound
effect. v0.4.0 has no exact-human binding for that complete effect set, so the
approve path is intentionally closed.

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
Dry-run returns only hashes, change categories, and the content-addressed
before-snapshot descriptor. It writes no candidate, canonical file, receipt,
lock, provider state, objet, manifest record, or database row.

## Step 3: Approval Is Closed In v0.4.0

Do not replay the preview as an approved write. Any `--approve` request returns
the fixed content-free blocker below before private target read or mutation:

```text
compound_exact_human_approval_binding_required
```

The dry-run is still useful for human review and future binding design, but it
grants no authority. No reviewer flags or stale v0.3 receipt can bypass this
gate.

## Historical v0.3 Receipt Boundary

Existing v0.3 revision receipts describe a writer that:

- uses one private lock shared by every revision plan for the same canonical
  zet, so distinct plans cannot race through the write section;
- binds the exact prior file hash to a text-free `before_snapshot` descriptor
  in that lock;
- writes or verifies the exact prior bytes under ignored
  `objects/sha256/<prefix>/<sha256>` without overwriting an existing object;
- registers or verifies the matching local record in
  `objects/manifests/files.jsonl` before canonical replacement;
- writes one canonical zet through atomic replacement;
- verifies the replacement bytes immediately;
- creates one new immutable receipt under
  `receipts/revisions/canonical/<write-plan-digest>.zet-revision.json`;
- stores reviewer id, canonical identity/path, timestamps, fixed change
  categories, before/after hashes, and the text-free before-snapshot descriptor
  in a v0.2 private receipt;
- stores no title, abstract text, body text, or custom frontmatter value in the
  receipt;
- records the reviewed abstract/body hash pair so `abstract-freshness` can
  recognize the revised zet as fresh;
- calls no model, provider, remote object store, database, credential store, or
  network.

CLI output does not echo the zet id, canonical path, proposal filename,
reviewer id, title, abstract, body, custom frontmatter value, provider URL,
absolute path, or secret. The digest-only receipt path is safe to return.

v0.4.0 does not enter that writer, create its lock, preserve a new snapshot,
replace a canonical zet, or create a revision receipt.

## Historical Failure And Interruption Evidence

An ordinary runtime failure after canonical replacement restores the exact
previous canonical bytes, removes a partial receipt, and removes the temporary
private write lock. The verified content-addressed snapshot remains for safe
idempotent reuse. If the process is interrupted after the atomic replacement
but before receipt creation, the private lock retains text-free before/after
hashes, the before-snapshot descriptor, and review bindings. Rerunning the exact
approved command verifies the preserved bytes, recognizes the already-written
candidate, and finishes the receipt without writing the canonical zet again.

The write lock is keyed to canonical identity rather than one proposal. A
second plan for the same zet therefore stops while the first transaction is in
progress, even when the proposals and write-plan digests differ.

An unexpected lock or mismatched state is never deleted automatically. It
blocks and stays available for human inspection.

## Honest Stop

A v0.4.0 result can prove only that the revision effect was planned without
writing. It cannot report `applied`. Historical `applied` receipts remain
auditable evidence of their recorded local event but do not authorize replay.
MCP exposes the read-only `zet_revision_plan` tool and no revision writer.
