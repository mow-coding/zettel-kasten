# Archive Infra Decision Log - v0.3.193 Local Profile Secret-Safety Progress

Date: 2026-07-07

Release: v0.3.193

## Context

After v0.3.192 reduced doctor progress volume, large full-archive runs could
advance beyond mint receipts, retire receipts, reconcile receipts, and object
storage execution receipts. The next quiet point was
`local-profile-secret-safety`.

That stage walks archive files, checks secret-like filenames, scans eligible
config/text content for secret-like values, and validates ignored local profile
files. Previously it had no internal progress.

## Decision

Add content-free progress and summary output inside
`local-profile-secret-safety`.

The stage now names gitignore checking, archive walking, checked-file counts,
content-scan counts, local-profile counts, skipped ignored-directory counts, and
the final summary. Long archive walks and long config/text content scans can
emit heartbeats.

Secret-content scanning now streams eligible files in chunks instead of loading
the whole file into memory.

## Consequences

- A pause inside `local-profile-secret-safety` can now be localized to archive
  walking or a specific long content scan.
- The progress stream remains content-free and does not echo secret values.
- Result JSON, receipt semantics, manifests, and archive files are unchanged.
