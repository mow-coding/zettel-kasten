# Archive Infra Decision Log - v0.3.200 Object-Storage Manifest Reconcile Receipt Schema

Date: 2026-07-08
Release: v0.3.200

## Context

v0.3.199 introduced `object-storage-wom-location-reconcile --approve`, which
writes a local audit receipt after repairing genuine missing `wom_uploaded`
manifest bindings.

The receipt was intentionally non-secret and local-only, but it did not yet have
the same explicit schema/doctor validation surface as the older mint reconcile
and object-storage upload receipts.

## Decision

Add a dedicated schema and doctor stage:

- `wom-kit/schemas/object-storage-manifest-reconcile-receipt.schema.json`
- `archive doctor` validation for
  `receipts/providers/object-storage-manifest-reconciles/*.object-storage-manifest-reconcile.json`

Doctor verifies schema/action/dry-run/reviewer/path shape, updated execution
receipt refs, positive update counts, and the non-echo privacy guards.

## Consequences

- A damaged or hand-edited manifest reconcile audit receipt is now visible to
  doctor.
- The repair command's no-provider/no-credential/no-object-byte boundaries are
  unchanged.
- The v0.3.199 archive behavior remains additive; no migration is required.
