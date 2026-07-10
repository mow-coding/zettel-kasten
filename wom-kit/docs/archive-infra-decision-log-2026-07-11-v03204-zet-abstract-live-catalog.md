# Archive Infra Decision Log - v0.3.204 zet Abstract And Live Catalog

Date: 2026-07-11
Release: v0.3.204

## Context

WOM had a useful one-zet overview, but no archive-wide first-read surface. The
legacy list command capped output at 500 without total, truncation, or cursor
evidence, and the overview could derive its gist by reading a body. That could
not support an honest 1,000- or 10,000-node abstract pass.

## Decision

- Add optional, bounded `frontmatter.abstract` as the preferred compact first
  read. Existing zets remain valid and are not rewritten.
- Prefer `abstract` before compatibility fields in one-zet overview reads.
- Add read-only `archive zet-catalog` with deterministic local path order,
  pagination, total/remaining/complete/truncated coverage, all frontmatter edge
  projections, and snapshot-change blocking.
- Read live local frontmatter directly. Do not require the generated SQLite
  index and do not read zet bodies to fill missing catalog abstracts.
- Keep goal and loop in the host LLM application's UI/UX. WOM records no goal
  or traversal loop state in this release.

## Consequences

- Existing archives need no migration.
- Missing abstracts remain visible as `abstract_status: missing` rather than
  being silently invented.
- A host can distinguish a complete page sequence from a truncated response.
- A changed local catalog blocks continuation with the old snapshot id.
- Snapshot evidence includes path, size, mtime, and frontmatter projection but
  explicitly does not hash body content.
- MCP exposure and host runtime instruction changes remain the next batch.
