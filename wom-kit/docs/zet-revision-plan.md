# Canonical zet Revision Plan

Status: v0.4.0 read-only single-zet planning; v0.3.235 writer evidence is historical

`zet-revision-plan` is the first half of WOM's ordinary canonical correction
workflow. It compares one complete private revision proposal with the current
canonical zet before any canonical byte or receipt is written.

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

## Writer Preview And Current Stop

A green plan can be handed to CLI `zet-revision-write --dry-run`. Keep these
exact values:

```text
canonical.sha256
proposal.sha256
proposal.semantic_sha256
plan_digest
```

The writer creates a second no-write preview that binds `revision_at` and the
exact writer-produced candidate. In v0.4.0 approval returns
`compound_exact_human_approval_binding_required` before private target reads or
mutation and writes no canonical byte, lock, snapshot, or receipt. See
[Canonical zet Revision Write](zet-revision-write.md).

MCP remains read-only and exposes no revision writer.

## Honest Stop

A green plan means only that the private proposal is structurally safe and
bound to the current canonical bytes for human review. It does not mean the
correction is true, approved, applied, understood by a model, or safe to copy
into the canonical file by hand. Machine output reports
the historical field `approval_contract.approved_write_implemented: true`, but
v0.4.0 fixed-close policy overrides it; only writer dry-run is current.
