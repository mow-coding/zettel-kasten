# Decision Log — v0.3.287 Notion Locator Evidence Plan

Date: 2026-07-30

## Context

The v0.3.277 audit can count current `[source locator omitted]` markers and
show whether a private `source_page_id` join key remains. It intentionally
does not read source mirrors or reconstruct historical URL occurrences.

Beta feedback confirms that the remaining corpus is large and that occurrence
order matters. Matching only the number of source URLs to the number of
markers could put a valid locator into the wrong location.

## Decision

Add a CLI-only, read-only
`notion-import-locator-evidence-plan` command.

The command accepts a human-reviewed private JSONL evidence snapshot, joins
only through the exact nested frontmatter key `facets.source_page_id`, binds
the row to exact current canonical bytes, and validates an explicit
source-occurrence-to-marker-ordinal mapping.

The command reports content-free row states and complete aggregates. It
returns no source page id, locator, locator fingerprint, title, body context,
zet identity, filename, or path.

## Authority

- A reviewed evidence row is the authority for the private locator and
  occurrence mapping.
- The current canonical file hash is the authority for which exact zet bytes
  were reviewed.
- Body marker count and import-time omitted count must agree with the evidence
  count.
- Equal counts without complete, unique ordinal sets are insufficient.
- A title, filename, date, `index`, external id, or another page-reference
  field is never substitute join authority.

## Consequences

- The project gains a deterministic bridge from loss census to human review.
- A bounded evidence batch may be useful even when it does not cover the full
  corpus; coverage is reported separately.
- Canonical drift, fan-out ambiguity, duplicate evidence, and malformed
  ordinal mappings fail closed.
- The evidence file remains a private, uncommitted working artifact.
- No canonical restoration, receipt, provider call, raw Notion-export parser,
  or MCP surface is added.

## Deferred Work

- extracting the reviewed evidence schema from raw `recordMap`,
  `pages.index.jsonl`, or `properties['비고']` variants;
- designing an approval-bound, crash-safe locator restoration writer and
  recovery path;
- handling the separate 77 occurrence-coordinate variants; and
- proving a complete corpus-wide recovery rather than a bounded proposal
  batch.
