# Canonical zet Revision Write

Status: fixed closed in v0.4.11; v0.3 receipts remain readable

`zet-revision-plan` can validate a private proposal against the current
canonical zet for human review. In v0.4.11 that validation result is not an
actionable handoff to `zet-revision-write`: its hashes and `plan_digest` are
evidence only and grant no approval authority. The result reports
`approval_fixed_closed`, `approved_write_implemented: false`, and
`actionable_handoff_available: false`.

The historical writer changed canonical bytes, private snapshot/manifest
state, lock state, and receipt history as one compound effect. v0.4.11 has no
exact-human binding for that complete effect set, so no supported preview,
handoff, or apply workflow is exposed from the current validation result.

## Step 1: Review The Proposal

Run the read-only plan first:

```powershell
archive zet-revision-plan <archive-root> `
  --zettel-id <safe-id> `
  --proposal .wom-scratch/revisions/<private-name>.md `
  --dry-run `
  --format json
```

The plan may return these four binding values:

```text
canonical.sha256
proposal.sha256
proposal.semantic_sha256
plan_digest
```

They identify what was validated for review; operators do not need to copy or
replay them. Review the complete private proposal and its current canonical
zet together. The plan is not approval and writes nothing.

## Step 2: Stop After Validation

Do not transfer the returned bindings into `zet-revision-write`, and do not
edit the canonical zet by hand to bypass the closed workflow. v0.4.11 exposes
no supported next-step writer command from a green validation result. No
reviewer flags, validation digest, or stale v0.3 receipt can grant authority.

A direct approval attempt remains fail-closed before private target read or
mutation with the content-free reason code
`compound_exact_human_approval_binding_required`; it writes nothing.

The development-only historical dry-run code and old receipts may remain
available for compatibility and audit. Their presence is not a product
handoff, and operators must not be instructed to use them as one.

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

The supported v0.4.11 validation workflow does not enter that writer, create
its lock, preserve a new snapshot, replace a canonical zet, or create a
revision receipt.

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

A v0.4.11 validation result can prove only that one proposal was structurally
checked against the exact current canonical bytes. It cannot report a writer
preview, approval, or `applied` state. Historical `applied` receipts remain
auditable evidence of their recorded local event but do not authorize replay.
MCP exposes the read-only `zet_revision_plan` tool and no revision writer.
