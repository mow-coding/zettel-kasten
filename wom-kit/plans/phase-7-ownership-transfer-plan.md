# Phase 7 Addendum: Ownership Transfer Receipts

Date: 2026-05-21

## Summary

Archive ownership is separate from archive operation.

This matters for families and companies:

- A family or household can own an archive.
- Parents or guardians can operate a child-related archive.
- A company can own a business-unit archive.
- Employees, founders, or roles can operate that archive.
- Later, ownership can be transferred without pretending the past never happened.

The deeper design principle is that family lineage and company lineage use one archive model:

```text
love / household / child independence
work / company / merger / spin-out
```

The emotional, legal, and social meanings are different, but the archive system should handle them through the same primitives: identity, owner, operator, subject, scope gate, trust gate, receipt, fork, merge, exit, and ownership transfer.

## Core Model

```text
owner
  The person or group the archive belongs to.

operator
  The person or role allowed to work inside the archive.

subject
  The person the records are about.
```

## Child Archive Case

```text
early child archive
  owner: family:example-household
  operators: person:father, person:mother
  subject: person:child

later child archive
  owner: person:child
  operators: person:child, optional trusted helpers
```

The transfer must not erase the family period. It should write a receipt saying the family owned and operated the archive first, then transferred ownership to the child.

## Company Case

```text
business-unit archive
  owner: company:parent-company
  operators: role:business-unit-admin, person:founder

after exit or spin-out
  owner: company:new-company
  operators: new company's approved roles
```

## Future CLI Shape

Implementation starts as dry-run:

```text
archive transfer-ownership <archive> \
  --new-owner person:child \
  --operator-after person:child \
  --approved-by person:parent-a \
  --approved-by person:parent-b \
  --counterparty-id person:child \
  --counterparty-fingerprint SHA256:child-primary \
  --dry-run
```

Current behavior:

- Returns `scope_gate`, `trust_gate`, `ownership_gate`, and `receipt_preview`.
- Shapes `receipt_preview` to match `schemas/ownership-transfer-receipt.schema.json`.
- Requires explicit `--operator-after`.
- Requires trusted new-owner fingerprint verification.
- Requires approval actors when the transfer policy says human approval is required.
- Writes nothing.
- Does not mutate `archive-identity.yml`.
- `archive doctor` validates example ownership-transfer receipts under `receipts/lineage/*.ownership-transfer.json`.

Real transfer should later require:

```text
--approve
--reviewed-by <person-or-role>
```

## Receipt Preview

```json
{
  "action": "transfer_archive_ownership",
  "dry_run": true,
  "previous_owner": "family:example-household",
  "new_owner": "person:child",
  "operators_before": ["person:father", "person:mother"],
  "operators_after": ["person:child"],
  "subject": "person:child",
  "scope_manifest": {},
  "approval_actors": ["person:father", "person:mother"],
  "trust_gate": {},
  "ownership_gate": {},
  "proposed_receipt_path": "receipts/lineage/<id>.ownership-transfer.json"
}
```

## Safety Rules

- AI/MCP can prepare the dry-run and receipt preview.
- AI/MCP must not perform real ownership transfer.
- Real transfer requires human approval.
- The old owner remains in lineage history.
- The new owner must have a verified identity/fingerprint.
- Operators after transfer must be explicitly listed.
- Sensitive child, medical, psychological, and family-private records require extra review.

## Implemented Transfer Surface

CLI:

```text
archive transfer-ownership <archive> --dry-run
archive transfer-ownership <archive> --approve --reviewed-by <actor>
archive providers <archive>
```

MCP:

```text
ownership_transfer_check
```

The MCP surface intentionally does not include a real transfer tool. This keeps AI-assisted operation on the safe side: the AI can prepare the preview, but only the human-approved CLI path performs the local archive identity change.

## Implemented Safe-Complete Baseline

The current safe baseline is broader than one CLI command:

- CLI dry-run and MCP check exist.
- CLI real transfer exists behind `--approve --reviewed-by`.
- Receipt preview has a schema.
- Doctor validates ownership-transfer receipt examples.
- Provider bindings and provider change plans exist.
- Fake archive examples cover family-to-child transfer and business-unit spin-out.
- External provider API mutation remains unavailable.

