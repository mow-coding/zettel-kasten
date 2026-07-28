# Archive Infrastructure Decision Log: v0.3.277 Notion Locator-Loss Audit

Date: 2026-07-28
Status: accepted and implemented

## Context

A beta report found that historical Notion imports removed provider locators
from many zet bodies while leaving an omission marker. The archive also
retains import-time omission counts and, for most imported zets, a private
`source_page_id`.

An omission marker is not sufficient restoration evidence. Current body marker
counts can differ from the import-time counts, and a source-page key does not
by itself identify which retained source occurrence belongs at which marker.

Existing `notion-objet-import-clue-audit` answers a different question: whether
a zet still has a material-object clue or an object-manifest bridge. It does
not census body locator placeholders or prove provider-URL recoverability.

## Decision

Add the CLI-only, read-only `notion-import-locator-loss-audit` command and
`notion-locator-loss-audit` alias.

- Scan every non-redacted imported Notion zet.
- Count the exact body marker `[source locator omitted]`.
- Compare current body counts with recursively preserved import-time omission
  counts.
- Report exact, body-greater, and frontmatter-greater count states.
- Verify only the presence of `source_page_id`; never echo its value.
- Return allowlisted import-family buckets rather than raw source metadata.
- Limit per-zet summaries independently from the complete aggregate scan.
- Put missing join keys and count mismatches first in the bounded result.
- Write nothing and read no source mirror or object bytes.

Broaden Notion source detection to recognize normalized `notion_*` historical
source labels in addition to the earlier exact and colon-delimited forms.

## Consequences

Operators can now distinguish:

- how much locator loss is visible now;
- where import-time and current counts still agree;
- where positional reconstruction would be unsafe;
- where the intended private source-page join key survived;
- where provenance must be investigated before any source-mirror plan.

The release does not recover or restore a provider locator. A later release
must add a separate read-only source-evidence and occurrence-alignment plan
before any approval-gated write is considered.

The command reads private zet bodies only to count the exact fixed marker, so
it remains CLI-only and returns no body context, provider locator, source-page
value, page title, or absolute local path.
