# Archive Infrastructure Decision Log: v0.3.231 First-Read Readiness

Date: 2026-07-14
Decision: accepted for v0.3.231

## Context

WOM already had structural Doctor checks and an exhaustive frontmatter catalog,
but an entering AI had no small, dedicated gate that answered whether every
canonical node had an explicit compact first read before the larger catalog
workflow began. A structurally healthy archive could therefore be mistaken for
memory-reconstruction readiness.

## Decision

- Add a frontmatter-only `first-read-readiness` CLI command and MCP tool.
- Require explicit `frontmatter.abstract` plus uniquely resolvable safe ids for
  `state: ready`.
- Count compatibility fields separately instead of silently treating them as
  the finished explicit-abstract contract.
- Return only bounded path/id/status attention records; never echo abstract,
  title, body, duplicate-id values, absolute paths, provider values, or secrets.
- Add the gate to archive status-board counts and the AI start-here command
  order without making quick start scan zet files.
- Keep repair and backfill human-reviewed. The gate writes nothing and grants
  no approval authority.
- The gate does not replace `zet-catalog-pass`; it checks readiness before that
  separate complete private artifact is generated and consumed.

## Consequences

Archive health, compact-memory readiness, complete catalog generation, and
actual host-model consumption are now four distinct claims. Existing archives
need no migration, but archives without explicit abstracts will correctly
receive a non-ready result until humans review and approve their backfills.
