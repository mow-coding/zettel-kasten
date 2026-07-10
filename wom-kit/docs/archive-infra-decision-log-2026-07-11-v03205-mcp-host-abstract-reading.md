# Archive Infra Decision Log - v0.3.205 MCP Host Abstract Reading

Date: 2026-07-11
Release: v0.3.205

## Context

v0.3.204 added an honest, exhaustive local frontmatter catalog, but an AI
working through MCP still had only the legacy capped list and body-default
single-zet read. Runtime instructions also did not require catalog completion.

## Decision

- Expose the catalog as read-only MCP `zet_catalog` with a 1,000-item page
  ceiling, explicit completion coverage, and snapshot-bound continuation.
- Add `section` to MCP `read_zettel`; keep `body` as the compatibility default
  while directing hosts to request `overview` first.
- Let MCP draft creation carry the same optional bounded `abstract` as CLI.
- Put exhaustive abstract enumeration into runtime context, AI start-here,
  archive agent templates, and the runtime skill.
- Require a host to finish every page under one snapshot before an
  archive-wide claim, then use abstracts, ties, and edges to choose body order.
- Keep goal, loop, branching, and completion UI in the host application.

## Consequences

- Existing clients and archives need no migration.
- A host can prove that an abstract pass completed instead of assuming that a
  search result or first page covered the archive.
- A host sees missing abstracts honestly and may still decide which bodies to
  read next; WOM does not rank or hide zet nodes.
- Generated maps and indexes remain optional accelerators, never canonical
  discovery authorities.
- Scale and token-cost measurements remain the next implementation batch.
