# Workpack Spec v0.1

A workpack is a portable archive slice.

It is the "packed lunch" format for moving only the necessary context between PCs, people, companies, or family archives.

## Required Fields

```yaml
package_id: workpack_20260519_example
source_archive: archive:personal:example
target_archive: archive:company:example
mode: derive
purpose: "Create a sanitized company memo from a private personal insight."
contents: {}
permissions: {}
provenance: {}
scope_gate: {}
trust_gate: {}
lineage: {}
expires_at: 2026-06-19T00:00:00+09:00
```

## Modes

```text
reference
  Metadata and citations only.

copy
  Independent copies of selected files.

mount
  Temporary access to remote or local object locations.

derive
  Sanitized derivative records for another archive.

handover
  Operational context for another person or team.

return
  Completed work/results sent back to the source archive.
```

## Suggested Structure

```text
workpack-example/
  package.yml
  zettels/
  objects/
  manifests/
  views/
  db/package.sqlite
  receipts/
```

## Import Rule

An archive should never blindly import a workpack. Import should create a receipt that records what changed.

```yaml
receipt_id: import_20260519_001
package_id: workpack_20260519_example
imported_into: archive:company:example
actor: person:example
result:
  zettels_created:
    - zet_20260519_company_derivative
  objects_added: []
  edges_created:
    - derived_from
warnings:
  - "Private source hidden; imported as derivative summary only."
```

## Scope And Trust Gates

Workpacks can carry dry-run metadata for governed sharing:

```yaml
scope_gate:
  unit: view
  view_id: view.example
  included_zettels:
    - zettels/example.md
  excluded: []
  sensitive_categories_blocked_by_default:
    - medical
    - psychological
    - journal
    - relationship-private
trust_gate:
  counterparty_identity_required: true
  counterparty_fingerprint_required: true
  verification_method: archive_identity_fingerprint
ownership_gate:
  ownership_transfer: false
  current_owner: person:example
  proposed_owner:
  operators_after_transfer: []
lineage:
  event: share_scope
  source_archive: archive:personal:example
  target_archive: archive:company:example
```

Real import remains unavailable in the safe baseline. Dry-run must show the scope gate and trust gate before future real writes. Workpacks that propose ownership changes must also show an ownership gate.
