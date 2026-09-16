# Canonical zet Revision Write

Status: reopened through operation-specific exact human approval in v0.4.21; fixed closed from v0.4.0 to v0.4.20; v0.3 receipts remain readable

`zet-revision-plan` validates a private proposal against the current
canonical zet for human review. Its hashes and `plan_digest` are validation
evidence only and grant no approval authority: the result reports
`approval_status: approval_available`, `approved_write_implemented: true`,
and `actionable_handoff_available: false`.

The writer changes canonical bytes, private snapshot/manifest state, lock
state, and receipt history as one effect. Since v0.4.21 that complete effect
set is bound into one operation-specific exact human approval: a fresh
private preflight, a content-free binding of the exact plan, one native
dialog, and one authenticated one-use claim re-verified right after the
dry-run point before the first byte changes. The receipt embeds the approval
reference. From v0.4.0 to v0.4.20 the approve path was fixed closed.

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

## Step 2: Preview, Then Approve The Exact Write

Run `zet-revision-write --dry-run` with the four plan digests and a
timezone-aware `--revision-at`; the preview reports `ready_to_apply` and
writes nothing. Then run the same command with `--approve --reviewed-by
<safe-actor-id>` and the two affirmation flags. WOM re-derives the plan,
compares every digest, opens one native exact human approval dialog, and
writes only after the authenticated claim is re-verified. A reviewer id that
is not a safe actor id returns `zet_revision_write_reviewer_required`; a
cancelled dialog writes nothing; a changed canonical zet or proposal is
refused by the fresh preflight. Do not edit the canonical zet by hand to
bypass this boundary. No reviewer flag, validation digest, or stale v0.3
receipt grants authority by itself: the native dialog with its one-use claim
is the only write authority. Unbound service calls return a content-free
blocked document with `exact_human_approval_required`.

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

The validation workflow alone does not enter that writer, create its lock,
preserve a new snapshot, replace a canonical zet, or create a revision
receipt; only the approved write does.

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

A validation result can prove only that one proposal was structurally checked
against the exact current canonical bytes. It cannot report a writer
preview, approval, or `applied` state; only the approved write's receipt
does. Historical `applied` receipts remain auditable evidence of their
recorded local event but do not authorize replay. MCP exposes the read-only
`zet_revision_plan` tool and no revision writer.
