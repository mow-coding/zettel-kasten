# Archive Lineage Spec v0.1

Archives are living lineages, not static folders.

They can remain private, share selected slices, merge into shared archives, fork into new archives, or separate through exit/spin-out events.

## Design Principle

Family formation and company formation use the same underlying archive lineage model.

```text
personal life
  -> relationship
  -> family
  -> child archive
  -> later ownership transfer to the child

personal work
  -> shared project
  -> company
  -> business unit
  -> merger, acquisition, exit, or spin-out
```

These are not the same emotionally or legally, but they share the same archive mechanics:

```text
identity
ownership
operators
subjects
scope gate
trust gate
lineage receipts
ownership transfer
```

## Scope Vocabulary

```text
personal
  A person's private life archive.

relationship
  A shared archive for a couple or committed relationship before or outside a family archive.

family
  A shared household or family-history archive.

child
  A person archive forked from family history. It may be operated by parents or guardians first and transferred to the child later.

project
  A project or business-development archive.

company
  A corporation or organization archive.

business_unit
  A business, location, or unit under a company archive.
```

## Lineage Events

```text
share
  A selected view/workpack is shared without merging the whole archive.

merge
  Selected records become part of another archive.

fork
  A new archive starts from selected history.

formation
  A family, company, or project archive is created from people or prior work.

exit
  A business unit leaves a parent company archive.

transfer
  Selected records or rights move to another archive.

ownership_transfer
  The archive owner changes while history and receipts remain intact.
```

## Required Gates

Every share, merge, fork, import, or exit should pass two gates before real writes:

```text
scope gate
  What exactly is included, excluded, copied, referenced, forked, or promoted?

trust gate
  Who exactly is on the other side, and does the archive already trust that identity/fingerprint?
```

Ownership transfer must pass an additional ownership gate:

```text
ownership gate
  Who owns the archive now, who operates it, who will own it after transfer, and who approved the change?
```

## Family To Child Ownership

A family or household can temporarily own a child's archive while parents or guardians act as operators.

```text
family archive
  owner: family:example-household
  operators: person:father, person:mother
  subject: person:child

child archive after transfer
  owner: person:child
  operators: person:child, optional trusted helpers
  lineage: forked_from family archive
```

The transfer should create a receipt with:

```text
action: transfer_archive_ownership
previous_owner
new_owner
operators_before
operators_after
subject
scope_manifest
approval_actor
timestamp
```

In the current implementation, MCP is preview-only and CLI can apply the local archive identity change:

```text
archive transfer-ownership <archive> --dry-run
archive transfer-ownership <archive> --approve --reviewed-by <actor>
MCP ownership_transfer_check
```

Dry-run and MCP return an ownership gate, provider change plan, and receipt preview. The real CLI path reruns those gates, writes a `dry_run:false` receipt, updates `archive-identity.yml`, and appends `lineage.ownership_transfers`. MCP still cannot write receipts or change ownership.

Ownership-transfer receipt previews and examples use:

```text
schemas/ownership-transfer-receipt.schema.json
receipts/lineage/*.ownership-transfer.json
```

`archive doctor` validates those example receipts so the lineage model can be tested before or after real CLI transfer.

## Company To Business Unit Spin-Out

A company can own and operate a business-unit archive while the unit is inside the parent company.

```text
business-unit archive before spin-out
  owner: company:parent-company
  operators: role:business-unit-admin, person:founder
  subject: business_unit:unit-a

business-unit archive after spin-out
  owner: company:new-company
  operators: role:new-company-admin, person:founder
  lineage: exited_from company:parent-company
```

The spin-out should create the same kind of receipt as the family-to-child case:

```text
action: transfer_archive_ownership
previous_owner: company:parent-company
new_owner: company:new-company
operators_before
operators_after
subject: business_unit:unit-a
scope_manifest
approval_actor
timestamp
```

The parent company history is not erased. The separated business archive continues with its own owner while carrying lineage that says it exited from the parent.

## Provider Boundary

Archive ownership is not the same thing as GitHub, Cloudflare R2, Backblaze B2, or Neon account ownership. `provider-bindings.yml` records which outside services are attached to the archive, using env var and keyring references instead of secrets. Ownership transfer receipts include a `provider_change_plan`, but v0.1 provider changes are manual.

## Default Sensitive Categories

These categories are blocked from sharing by default:

```text
medical
psychological
journal
relationship-private
```

They can appear in a dry-run preview, but real sharing must require explicit human approval and a receipt.

