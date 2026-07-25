# Archive Infra Decision Log - v0.3.261 Honest Search Coverage

Date: 2026-07-26

Status: accepted for v0.3.261 implementation and release

## Context

A beta report from a large real archive said the generated index could not
answer an ordinary topic question and asked for a full-text-search table.

Reading the code produced a different diagnosis. `search_archive` already
LIKE-matches a concatenation that includes the zettel body, so bodies are
searchable today. The reported two-of-fifty-five shortfall came from ad-hoc SQL
against the `title` column, which is not this product's search surface.

What did reproduce is a contract defect. `search_archive` returned
`{"query", "count", "results"}` where `count` is the number of rows returned.
The limit is clamped to at most 100 and defaults to 20, and nothing in the
result distinguishes "these are all the matches" from "this is the first page".
The MCP tool then summarized it as `Found N result(s).`

That is the failure mode the beta report describes from the other side: an
operating AI receives a capped page, reads it as the complete answer, reports a
wrong total, and falls back to scanning files directly.

This also contradicts the project's own doctrine. `zet-abstract-catalog.md`
requires enumeration that does not "silently stop at an arbitrary top-k limit",
and the catalog implements `complete`, `truncated`, `total`, and continuation
tokens. Search was the retrieval surface that never adopted it.

## Decision

1. `search_archive` reports coverage on every surface: `truncated`, `complete`,
   `returned`, `total_matches`, `total_matches_known`, `matches_by_type`,
   `limit_applied`, and `limit_ceiling`.
2. Truncation is detected with a probe budget of `limit + 1`. Reading one row
   past the caller's limit proves whether more matches exist while every
   channel keeps its `LIMIT`, so the cascade still terminates early.
3. An exact total is opt-in: `--count-total` on the CLI, `count_total` on MCP.
   A leading-wildcard `LIKE` cannot use an index, so an exact count costs a full
   scan of each searched table. A non-truncated result set is already exact and
   reports its total for free; a truncated one reports `total_matches: null`
   and `total_matches_known: false` unless the caller asks.
4. `count`, `query`, and `results` keep their existing meaning and shape.
   `count` remains the returned row count for compatibility.
5. All three surfaces state which case occurred: the JSON result, the default
   CLI text line, and the MCP summary. Fixing only the machine-readable
   surfaces would leave the defect in place where most callers meet it.
6. Each channel's `WHERE` clause is a single constant used by both its result
   query and its count query, and the zettel status list is generated from
   `ZETTEL_QUERYABLE_STATUSES` so the SQL filter and the Python-side guard
   cannot describe different sets.
7. Result rows and any count run inside one read transaction, so a concurrent
   index rebuild cannot make them describe different database states.
8. Matching behavior, ordering, the channel cascade, and the 100-result ceiling
   do not change. The ceiling is reported instead of silent.

## Privacy Contract

`total_matches` must never reveal that suppressed content matched. Because the
count shares the result query's clause, a redacted zettel whose body contains
the query term is neither returned nor counted. A regression asserts this at a
capped and an uncapped limit, and also asserts that the redacted zettel's id and
title do not appear in the output.

## Verification Contract

- A capped search over five planted matches reports `returned: 2`,
  `truncated: true`, `complete: false`, `total_matches: null`, and
  `total_matches_known: false`.
- The same search with `--count-total` reports `total_matches: 5` and
  `matches_by_type: {"zettel": 5}`.
- The same search at a sufficient limit reports `truncated: false`,
  `complete: true`, and an exact total without being asked.
- The default text output states that more matches exist for a capped page and
  states completeness for a full one.
- The redaction regression passes at a capped limit, an uncapped limit, and
  with `--count-total`.
- The MCP tool test asserts all three summary phrasings and the structured
  fields, including the `count_total` path.
- Existing search, related-zets, and legacy-status regressions stay green.

## Consequences

A caller can now tell a complete answer from a first page, which is the
precondition for an operating AI to continue rather than conclude. Search stays
as fast as it was: the honesty signal costs one extra row, and only a caller
that explicitly wants a number pays for scanning.

## Review Outcome

Four independent reviewers held the first implementation. It computed exact
totals on every truncated search, which replaced an early-terminating query
with five unindexed full-table scans — including the two tables that store full
document text — on exactly the large archives that motivated the release. The
non-zettel channels are gated behind `remaining > 0`, so the baseline often did
not read them at all; the regression was therefore larger than a doubling. The
same reviewers found that the first implementation left the default CLI text
output printing `Found {count} result(s).`, the exact sentence this decision
identifies as the defect. Both were corrected before versioning, along with the
shared status list, the single read transaction, and the MCP tool description.

The reviewers also found that this batch's doc tooling had converted a stray
carriage return inside the already-shipped v0.3.260 upgrade sections into a line
break, splitting a sentence. That literal was a mangled `..\report.json` from
the v0.3.260 batch; both guides now carry the intended text.

Deliberately not in this batch: a full-text-search table, a classification-path
facet, an approval-gated retitle tool for imported zettels whose title is a
meaningless identifier, and continuation cursors for search. Full-text search in
particular needs a separate decision about tokenizing non-space-delimited text,
where the default tokenizer would not segment Korean the way substring matching
currently does.
