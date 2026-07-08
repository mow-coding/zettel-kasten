# Archive Infra Decision Log - v0.3.199 Object-Storage WOM Location Reconcile

Date: 2026-07-08
Release: v0.3.199

## Context

Field diagnostics after v0.3.198 exposed a narrow object-storage doctor
problem. A successful upload receipt and the object manifest can disagree about
the exact `execution_receipt_ref` in the `wom_uploaded` location.

One observed shape is benign: a repeated `skipped_remote_same` receipt confirms
that the remote object is still present at the same key, while the manifest
already has one valid `wom_uploaded` location for that same object/provider/
store/key. Because the manifest writer de-duplicates by remote key, adding a
second location just to point at the repeat receipt would be the wrong model.

The other shape is real drift: a successful upload receipt has no exact manifest
location and no same-key coverage. That needs a reviewed repair path, not a
manual JSON edit.

## Decision

Make doctor coverage-aware and add a dry-run-first repair command:

- `archive doctor` accepts a `skipped_remote_same` receipt when an existing
  audited `wom_uploaded` manifest location covers the same object, provider,
  store, and remote key.
- `archive doctor` suggests
  `archive object-storage-wom-location-reconcile <archive-root> --receipt <path>
  --dry-run` for genuine missing bindings.
- `archive object-storage-wom-location-reconcile` supports `--dry-run` and
  `--approve --reviewed-by <actor>`.
- Approved mode writes only the object manifest and one audit receipt under
  `receipts/providers/object-storage-manifest-reconciles/`.

## Consequences

- Repeated same-key skip receipts no longer create false doctor failures.
- Real missing bindings now have a local, reviewable, receipt-backed repair
  route.
- The repair route never calls providers, reads credentials, reads object bytes,
  uploads, downloads, or checks remote availability.
- Public output keeps object ids, remote keys, bucket names, provider URLs,
  exact credential refs, and local absolute paths out of candidate summaries.
