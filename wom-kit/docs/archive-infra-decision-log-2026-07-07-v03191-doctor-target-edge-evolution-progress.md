# Archive Infra Decision Log - v0.3.191 Doctor Target Edge Evolution Progress

Date: 2026-07-07

Release: v0.3.191

## Context

v0.3.190 proved that a slow mint receipt could be localized past path
resolution, existence checks, stat, and target file hashing. The next observed
quiet point was `checking target edge-receipt evolution`.

That phase can require the doctor run to build or reuse an edge receipt index
and then replay target edge history to decide whether a historical target
sha256 is acceptable. Before this release, that inner work did not emit progress.

## Decision

Add content-free target edge-receipt evolution progress.

The doctor path now names the archive-relative target, target edge receipt
candidate loading, first-build index loading, scan counts, cache hits, candidate
counts, target zettel reads, strict/inclusive history checks, and ok/no-match
outcomes.

The shared edge receipt index builder also accepts an optional progress callback
and emits a 30-second `still scanning edge receipts` heartbeat for long quiet
intervals.

## Consequences

- A pause after `checking target edge-receipt evolution` can now be localized to
  listing/scanning edge receipts, cache reuse, candidate count, target zettel
  read, or strict/inclusive replay work.
- The progress stream remains content-free: counts and archive-relative paths
  only.
- Result JSON, diagnostics, receipt semantics, manifests, and archive files are
  unchanged.
