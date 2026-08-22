# Decision: outcome-complete WOM recovery train v0.4.3-v0.4.7

Date: 2026-08-22

## Context

Feedback through Letter 144 shows a repeated gap between available audits or
plans and actual recovery of historical data.  A three-release grouping coupled
too many unrelated failure domains, especially local recovery, R2, and Notion.

## Decision

Use five vertical releases.  Build one reusable exact-operation manifest,
approval, checkpoint, receipt, independent-verification, and field-scoped
revert foundation in v0.4.3.  Every later writer must reuse it; top-level CLI
command count must not grow merely to add more planning surfaces.

The releases are ordered by dependency and irreversible-loss risk: prove the
foundation with Letter 138, protect R2-only bytes, repair local associations,
recover provider-dependent Notion data, then address quality and cleanup.

Letter 138 recovery is bound to the complete 11,585-file sharded
`block-mirror`, not the narrower 3,605-row Database 3.0 JSONL mirror.  Its
4,034 direct `object_record` and 7,551 legacy `recordMap` files are both source
evidence.  The source snapshot count is a pre-write invariant.  The client's
51/904/2,810 populated email/URL/date counts are retained as provenance for the
historical first-40,000-character, exact-property-name regex probe.  They are
not semantic acceptance totals.  The full semantic typed counts are
51/917/3,439, with every difference classified as truncation, alternate property
name, or raw-regex false positive.  Opaque legacy properties are preserved
losslessly when their modern name/type meaning is unavailable.

Malformed canonical documents affect Letter 138 only when they contain, or
cannot be proven not to contain, a `source_page_id` candidate.  A known BOM
document with no such token is an explicitly accounted non-candidate hygiene
item for v0.4.7; it must not globally convert every mapped source page to
review.

## Consequences

- Release overhead increases slightly, but completed work is not held behind an
  unrelated provider or credential blocker.
- v0.4.3 must include a real backfill outcome, not only infrastructure.
- R2 byte preservation may precede semantic duplicate resolution, but it must
  be labelled `bytes_preserved`, never falsely reported as adopted or verified.
- The emergency R2 target set is exactly 3,374: 3,376 unique local definitions
  minus 2 with existing remote evidence.  The 1,149 conflicting definition
  groups are a separate review population.  Immutable per-object receipts and
  one final projection replace any O(n-squared) central-manifest rewrite loop.
- Superseded Letters 141 and 143 remain immutable evidence.  Letter 144 supplies
  corrected current measurements.
- See `meeting-minutes/2026-08-22-v043-v047-feedback-recovery-execution.md` for
  chronology, starting state, and release completion gates.
