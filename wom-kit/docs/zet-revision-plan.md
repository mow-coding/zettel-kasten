# Canonical zet Revision Plan

Status: v0.4.11 read-only single-zet validation; writer evidence is historical

`zet-revision-plan` is WOM's read-only validation surface for reviewing an
ordinary canonical correction proposal. It compares one complete private
revision proposal with the current canonical zet without creating a writer
handoff and before any canonical byte or receipt is written.

This is different from `remint-reconcile`. Reconcile explains and receipts a
canonical file that already drifted on disk. Revision planning keeps the
canonical file untouched while a proposed correction is still being reviewed.

## Private Proposal

Prepare one complete Markdown copy under:

```text
.wom-scratch/revisions/<private-name>.md
```

The proposal may change the title, abstract, body, facets, assets, edges,
visibility, source metadata, corrections, and other knowledge fields. It must
retain the current values and presence of WOM-managed identity and lifecycle
fields:

```text
id
archive_id
created_at
updated_at
status
mint
promotion
revision
provenance.created_by
provenance.created_in
```

The scratch file is private working material. Do not commit it.

## Command

```powershell
archive zet-revision-plan <archive-root> `
  --zettel-id <safe-id> `
  --proposal .wom-scratch/revisions/<private-name>.md `
  --dry-run `
  --format json
```

Aliases:

```text
revise-zet-plan
canonical-revision-plan
```

MCP exposes the same read-only operation as `zet_revision_plan`.

## What It Checks

- both files are regular UTF-8 Markdown files no larger than 16 MiB;
- the proposal stays under the private revision scratch folder and crosses no
  symbolic-link boundary;
- the target is one canonical zet with the requested safe id;
- archive identity, zet identity, creation metadata, lifecycle metadata, and
  original creator metadata are unchanged;
- required frontmatter, title, body, provenance, and visibility are present;
- the proposal has a normalized, bounded, safe explicit abstract;
- body locators and edge types pass the existing machine safety checks;
- local quality blockers are absent;
- at least one semantic knowledge field or the body actually changes.

The result separately reports body, abstract, title, edge, provenance,
visibility, source, correction, derived-artifact, and other-frontmatter change
categories. It warns when a changed body reuses the old abstract so a human can
decide whether that first read still fits.

## Binding And Privacy

The plan returns current canonical SHA-256, proposal SHA-256, a normalized
proposal semantic SHA-256, and `plan_digest`. A future writer must revalidate
all four before it may write.

The result never returns the actual zet id, canonical path, proposal filename,
title, abstract, body, custom frontmatter value, reviewer id, provider URL,
absolute path, or secret value. It calls no model, provider, credential store,
object store, or database.

## Validation Result And Current Stop

A green plan returns these exact binding values as review evidence:

```text
canonical.sha256
proposal.sha256
proposal.semantic_sha256
plan_digest
```

They prove what the validation read, but they do not grant approval authority.
The successful result therefore reports `status: approval_fixed_closed`,
`proposal_validation_status: ready_for_human_review`,
`approval_contract.approved_write_implemented: false`, and
`approval_contract.actionable_handoff_available: false`.

v0.4.11 provides no supported preview, handoff, or apply path from this result
to `zet-revision-write`. The command remains fixed closed, and a person should
not be instructed to copy the proposed change into the canonical zet by hand.
See [Canonical zet Revision Write](zet-revision-write.md) for that command's
closed-boundary contract.

MCP remains read-only and exposes no revision writer.

## Honest Stop

A green plan means only that the private proposal is structurally safe and
bound to the current canonical bytes for human review. It does not mean the
correction is true, approved, applied, understood by a model, or safe to copy
into the canonical file by hand. Its validation digests are evidence only and
must not be interpreted as permission to write.
