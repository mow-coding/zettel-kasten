# Decision Log: v0.3.217 Catalog Artifact Lifecycle

Date: 2026-07-11
Status: implemented

## Decision

Treat a complete catalog-pass JSONL as SHA-bound private scratch with an
explicit validate, one-page read, and human-approved cleanup lifecycle.

## Context

v0.3.216 made a large frontmatter pass complete in one process, but its host
guidance still depended on ad hoc line reading and manual deletion. That left
three gaps: a host could read a truncated or modified artifact, could inject
the whole private file into one response, or could forget cleanup after use.

## Consequences

- Pass summaries include the SHA-256 of the exact published JSONL bytes.
- `zet-catalog-pass-read` validates every record before it may return one page.
- A private page requires the expected SHA-256 and the command never returns
  more than one page.
- Unsupported result/item fields, body-read claims, broken page continuity,
  incomplete footers, snapshot mismatch, and hash mismatch fail closed without
  echoing the selected private page.
- `zet-catalog-pass-cleanup` previews first and deletes only a complete artifact
  whose expected hash still matches, after explicit human approval.
- Cleanup writes no archive receipt and never deletes hidden partials. The file
  remains disposable scratch, not durable WOM knowledge.
- No zet, objet, manifest, external provider, map, index, or database changes.
