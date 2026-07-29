# Decision Log: v0.3.282 Activity-Group Membership Removal Plan

Date: 2026-07-29

## Context

Beta feedback required an event-group representation that lets an owner later
remove selected members. v0.3.280 established the explicit read-only add plan,
and v0.3.281 implemented approved additions and interruption recovery, but
both deliberately left removal unavailable.

The current data shape allows one scalar or an ordered non-empty list in
`facets.activity_group`. A removal operation therefore needs separate
authority and evidence: absence must be an idempotent no-op, other event
memberships must survive, and malformed state must never become permission to
normalize or delete data.

## Decision

1. Add a distinct read-only
   `activity-group-membership-removal-plan` command and
   `event-group-membership-removal-plan` alias.
2. Use separate removal request and plan schema identifiers and a separate
   private scratch prefix.
3. Reuse the event-anchor, exact canonical-file, duplicate-key, privacy, and
   bounded-read contracts of the addition planner.
4. Classify rows as `ready_to_remove`, `already_absent`, or `blocked`.
5. Remove only the exact named anchor in candidate bytes. Preserve another
   membership list's order and list representation, even when one item
   remains.
6. Bind the removal schema, exact request hash, anchor hash, and ordered
   current/proposed row hashes in the review digest.
7. Add the route to AI command-path routing v0.5 while continuing to report
   removal writing as unimplemented.
8. Do not add `--approve`, a receipt, a writer, or recovery in this release.

## Rationale

Keeping removal separate from addition prevents an add approval or receipt
from being reused as deletion authority. Preserving list representation makes
the candidate the smallest semantic change instead of combining deletion with
unrequested normalization.

Exact live files, rather than search or the generated index, remain the
authority because a stale or partial index must never grant deletion
permission.

## Consequences

- Archive owners can prepare and review exact removal evidence without
  mutating memory.
- Already-absent rows are visible and digest-bound but do not become candidate
  writes.
- Malformed current values remain explicit blockers.
- A later writer must share the existing activity-group serialization
  boundary, revalidate under lock, journal before mutation, write a separate
  immutable removal receipt, and provide hard-interruption recovery.
- General event-group query/health, membership inference, orphan cleanup,
  direct-file repair, and MCP removal remain outside this release.

## Standards And Prior Art

The event anchor remains compatible with the ordinary event/sub-event
separation used by Schema.org, while neutral membership follows the broader
collection principle that grouping and ordering are distinct facts. The
removal plan does not claim RDF or Schema.org serialization compatibility.

- https://schema.org/Event
- https://www.w3.org/TR/skos-reference/#collections
