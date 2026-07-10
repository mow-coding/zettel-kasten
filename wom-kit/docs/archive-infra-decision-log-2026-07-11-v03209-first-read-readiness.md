# Decision Log: v0.3.209 First-Read Readiness

Date: 2026-07-11
Status: implemented

## Decision

Keep strict catalog node coverage, abstract availability, and id-based
follow-up resolvability as three independent machine-readable claims.

## Context

v0.3.208 could visit every file node even when one or more nodes had no compact
frontmatter text. That was correct for exhaustive discovery but too easy for a
host AI to paraphrase as “every abstract was read.” Duplicate ids similarly did
not remove file nodes, but they made later id-only reads ambiguous.

## Consequences

- Existing `archive_wide_coverage_claim_ready` semantics stay compatible.
- Redacted nodes remain visible in node counts and are excluded only from the
  readable-abstract requirement.
- Missing/unreadable first reads and duplicate/unaddressable ids keep their own
  counts and readiness booleans.
- No automatic abstract generation, id rewrite, migration, or persistent loop
  state is introduced.
