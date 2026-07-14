# Archive Infrastructure Decision Log: v0.3.233 Abstract Freshness

Date: 2026-07-14
Decision: accepted for v0.3.233

## Context

v0.3.232 prevents new canonical zets from being published without an explicit
abstract, but later edits can separate that abstract from the body it was
reviewed against. Presence alone cannot distinguish a current compact first
read from an old one.

## Decision

- Record a text-free abstract/body review basis in approved mint and promotion
  receipts.
- Reconstruct compatible evidence from retained v0.3.232 publication sources
  and existing reviewed abstract-backfill receipts.
- Add read-only CLI `abstract-freshness` and MCP `abstract_freshness` surfaces.
- Report `fresh`, `stale`, `unverified`, `missing`, `unreadable`, or policy
  `excluded` without echoing content, hashes, receipt paths, or reviewer ids.
- Index receipts once and scan canonical zets once; never rescan every receipt
  for every zet.
- Put the check in the canonical AI runtime order after first-read readiness and
  before exhaustive abstract enumeration.
- Never auto-rewrite an abstract or body from this diagnosis.

## Consequences

WOM can now distinguish “an abstract exists” from “retained human-review
evidence still matches this exact body.” Older zets without reconstructable
evidence remain valid and are honestly `unverified`, not mislabeled as stale.
The check proves only hash-pair continuity, not semantic truth, completeness,
or model consumption.
