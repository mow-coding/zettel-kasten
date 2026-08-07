# Archive infrastructure decision log: Letter 113 real-use gaps

Date: 2026-08-07

## Context

A beta archive verified the preceding release train on real data and found that
safe stored values were still unreachable through five operator workflows:
mixed ready/blocked markup plans, objet-backed body references, migration-tag
normalization, locator coordinate enrichment, and large/short title remapping.

## Decision

- Keep strict markup planning as the default, and add an explicit ready-only
  selection mode whose digest binds both the selection mode and exact reviewed
  bytes. Blocked zets remain byte-identical and visible in the report.
- Accept `objet` in reviewed markup binding manifests only when the full
  `sha256:<64 hex>` id exists in the archive object manifest. Emit an RFC
  3986-shaped opaque `wom-objet:` identifier rather than a provider URL.
- Preserve visible or reconstructable information: strict ISO mention dates
  become text, synced-block wrappers retain their complete inner content,
  unresolved media remains blocked, and numeric column widths may be dropped as
  presentation while header semantics are carried into GFM as far as GFM can
  represent them.
- When one active locator occurrence matches the same type/ref, add missing
  reviewed coordinates to that row instead of appending a duplicate. Preserve
  the stable locator id and exact-byte revert evidence. Different occurrence
  anchors remain separate occurrences.
- Align title-remap plan/write defaults to the existing 5,000-row ceiling. A
  short non-generic source title may pass only with exact
  `source_export_property` provenance and an explicit warning; `human_written`
  does not bypass the normal specificity gate.

## Consequences

The changes unlock already-safe work without weakening unresolved-tag or stale
byte protections. They add no provider calls, credential access, automatic
object matching, canonical beta writes, or UI changes.

Standards references:

- https://github.github.com/gfm/#tables-extension-
- https://html.spec.whatwg.org/multipage/tables.html
- https://www.rfc-editor.org/rfc/rfc3986.html
