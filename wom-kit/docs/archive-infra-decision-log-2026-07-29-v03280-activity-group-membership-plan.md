# Decision Log: v0.3.280 Activity-Group Membership Plan

## Context

Beta Letter 102 supplied a twice-reproduced event sample: 96 zets described one
event, but only one of 33 zet edges connected two members inside that set. The
archive could search for the records, but could not record their neutral common
event without an O(N²) pairwise edge expansion.

`activity_group` already existed as a recommended facet and `create-draft
--facet` could record it on new drafts. Runtime code did not interpret the key,
and there was no safe retroactive canonical batch path.

A read-only aggregate check of the beta index found zero canonical
`activity_group` values. A census-only release would therefore report zero
without unblocking the operator.

## Decision

1. Represent an event with one existing canonical `record_note` anchor.
2. Use the anchor zettel id as the `facets.activity_group` member value.
3. Require the anchor to declare `facets.record_type: event`, a title, and an
   ISO 8601 `event_start`; permit a compatible later `event_end`.
4. Treat event membership as neutral co-membership. It implies no source,
   derivation, containment, continuation, or sequence relationship.
5. Add only a read-only plan in v0.3.280.
6. Accept only an explicit private request containing one anchor id and ordered
   member ids. Do not infer members from search, title, time, or proximity.
7. Bind exact current and proposed hashes into `review_plan_sha256` while
   returning no ids, paths, titles, facet values, or bodies.
8. Defer the canonical writer and member removal to separate approval-gated
   releases.

## Standards basis

- RFC 5545 `VEVENT` supplies the stable identifier, summary, inclusive start,
  and non-inclusive end boundary.
- Schema.org `Event` confirms the identifier/name/start/end shape.
- W3C PROV `wasGeneratedBy` is not reused because generation is stronger than
  neutral event membership.

## Consequences

- N members need one anchor plus N facet values rather than N² pairwise edges.
- One zet may belong to multiple events through a list value.
- The plan is useful before a writer exists because it finds stale ids, invalid
  anchors, conflicting current shapes, byte drift, and privacy boundary
  failures.
- v0.3.280 changes no existing archive automatically.
- The base facet vocabulary now documents `event_start` and `event_end`, and
  `activity_group` is classified as a navigation facet.
- A later writer must add explicit approval, exact revalidation, lock, journal,
  receipt, rollback/recovery, and independently reviewed removal.
