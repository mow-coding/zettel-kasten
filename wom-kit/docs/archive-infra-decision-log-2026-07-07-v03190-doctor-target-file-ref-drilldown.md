# Archive Infra Decision Log - v0.3.190 Doctor Target File-Ref Drilldown

Date: 2026-07-07

Release: v0.3.190

## Context

v0.3.189 proved that doctor could name the current mint receipt and identify a
slow receipt as being inside `checking target file ref`.

That was still too coarse. A file-reference check includes safe path resolution,
existence checks, sha field validation, stat, SHA-256 reads or cache hits,
sha comparison, and possible target edge-receipt evolution checks.

## Decision

Add content-free file-reference drilldown progress for mint receipts.

The drilldown names path resolution, existence, resolved archive-relative refs,
sha field validation, stat, cache hit, hash start/end, hash chunk liveness,
sha mismatch, edge-receipt evolution, and ref-ok.

For fresh SHA-256 reads, emit `hashing <section> file bytes` before the read
regardless of file size. Keep `still hashing ...` as chunk liveness only.

When a mint source is retired through a retire-draft receipt, name the skipped
source check.

## Consequences

- A pause after `checking target file ref` can now be localized to resolve,
  exists, stat, hash, cache, compare, or edge-evolution work.
- Operators get a safe archive-relative ref when resolution succeeds.
- Optional `--progress` stderr output is more verbose for mint receipts.
- Result JSON, diagnostics, receipt semantics, manifests, and archive files are
  unchanged.
