# Archive Infra Decision Log - v0.3.206 Catalog Scale And Token Budget

Date: 2026-07-11
Release: v0.3.206

## Context

Exhaustive abstract coverage was implemented, but fixed item pages did not tell
the host how much context they consumed. Revalidating 10,000 files before every
MCP page also made one synthetic ten-page pass take about 145 seconds.

## Decision

- Report transparent scope/page abstract and items-JSON workload estimates.
- Add an optional items-only token budget that limits a page without dropping
  nodes or ending coverage early.
- Materialize the first MCP snapshot in process memory for intermediate pages,
  then perform full local metadata revalidation before completion.
- Block completion and require restart when that revalidation detects change.
- Use PyYAML's C safe loader when available and a bounded cold-scan thread pool,
  with the existing safe loader as fallback and no new dependency.
- Ship a temporary synthetic benchmark plus automated 1,000-node regression.

## Consequences

- A host can divide all-node reading across its own loops with explicit cost
  evidence instead of silently switching to top-k retrieval.
- Intermediate MCP pages do not repeatedly touch every local file.
- The final completion claim still depends on a current local metadata check.
- The process cache is ephemeral and cannot become an authoritative map.
- Token counts and host timings remain estimates and observations, not provider
  usage records or performance guarantees.
