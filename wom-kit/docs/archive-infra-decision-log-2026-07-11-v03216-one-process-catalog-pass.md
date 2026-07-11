# Decision Log: v0.3.216 One-Process Catalog Pass

Date: 2026-07-11
Status: implemented

## Decision

Expose the existing process-local catalog snapshot and final revalidation as a
single CLI pass that publishes a private scratch JSONL only after completion.

## Context

Paged CLI calls are stateless processes. They repeatedly rescan frontmatter on
large archives even though the service and MCP already support safe ephemeral
reuse within one process. Persisting a catalog cache would add private-data
expiry, invalidation, cleanup, and authority questions that are unnecessary for
the immediate bottleneck.

## Consequences

- The first page scans live local frontmatter; intermediate pages reuse only
  process memory.
- Multi-page completion revalidates local path metadata and blocks changed
  snapshots before final publication.
- The output is complete-only private JSONL under `.wom-scratch/diagnostics/`,
  never a canonical record, map, index, receipt, or backup.
- Output size is bounded, existing destinations are never overwritten, and
  handled failures remove the invocation's new hidden partial.
- Forced termination may leave a hidden partial. Later runs count but do not
  read or auto-delete possible concurrent work.
- Hosts read page records incrementally and delete the scratch file after use.
- Existing paged CLI and MCP behavior remain compatible; no provider, model,
  secret, objet byte, archive knowledge, or external database is touched.
