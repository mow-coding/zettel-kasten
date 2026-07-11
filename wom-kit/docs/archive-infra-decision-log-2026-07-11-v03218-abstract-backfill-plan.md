# Decision Log: v0.3.218 Abstract Backfill Plan

Date: 2026-07-11
Status: implemented as read-only planning

## Decision

Treat a missing zet abstract as a reviewed canonical metadata revision, not an
automatic catalog repair.

## Context

Real-archive catalog validation showed that exhaustive node visitation can
succeed while thousands of canonical zets still lack first-read text. Writing
AI summaries directly would bypass source-version binding, review, staleness,
rollback, and revision evidence.

## Consequences

- `read-zettel` exposes exact non-redacted canonical file and decoded body
  hashes alongside the body an AI or human reads.
- Private JSONL proposal rows bind one proposed abstract to exact canonical
  bytes and declare human-written or AI-assisted preparation.
- `zet-abstract-backfill-plan` validates current identity, canonical status,
  first-read absence, safe bounded text, and a minimal one-field insertion.
- Output omits zet ids, paths, titles, bodies, abstracts, and private proposal
  filenames while preserving row-indexed blockers and hash evidence.
- Proposal batches are bounded to 5,000 rows; larger archives use multiple
  review batches.
- v0.3.218 writes nothing. Human-approved transactional revision and receipts
  remain a separate next release.
