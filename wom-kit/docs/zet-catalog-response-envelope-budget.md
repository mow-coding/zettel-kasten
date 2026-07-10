# zet Catalog Response Envelope Budget

Status: implemented in v0.3.211

## Why Items-Only Is Not The Whole Response

`max_estimated_tokens` originally limited only the catalog's `items` JSON. A
host also receives coverage, snapshot, readiness, order, workload, warnings,
and safety fields. That non-item material is the response envelope.

v0.3.211 keeps the old items-only default and adds two compatible tools:

- a measured compact service-result and envelope estimate on every page;
- an optional reserve that leaves room for the envelope before selecting items.

## Measurement

`workload_estimate.response` reports:

```text
service_result_json_chars
service_result_json_utf8_bytes
estimated_service_result_json_tokens
items_json_chars
estimated_items_json_tokens
response_envelope_json_chars
response_envelope_json_utf8_bytes
estimated_response_envelope_tokens
```

The basis is compact, key-sorted service-result JSON. The estimate is
`ceil(character_count / 4)` and is not provider-reported tokenization.

The measurement explicitly excludes:

- its own `workload_estimate.response` block, avoiding recursive self-size;
- CLI `--format json` indentation and pretty-print whitespace;
- MCP/JSON-RPC framing around the structured service result;
- zet bodies and objet bytes.

Use it as a planning signal, not an exact model bill or context-window proof.

## Reserve

```powershell
archive zet-catalog <archive-root> `
  --projection reading `
  --coverage-mode strict `
  --max-estimated-tokens 8000 `
  --response-envelope-reserve-tokens 2500 `
  --dry-run `
  --format json
```

With those values, WOM budgets at most 5,500 estimated tokens for `items` and
reserves 2,500 for the compact service-result envelope. The output reports:

```text
coverage.effective_items_token_budget
workload_estimate.response.budget.reserve_active
workload_estimate.response.budget.estimated_total_within_requested_budget
workload_estimate.response.budget.reserve_covers_measured_envelope
```

The reserve requires `max_estimated_tokens` and must be non-negative. If it
uses the entire requested budget, WOM still returns one item so the host cannot
deadlock. If the measured envelope is larger than the reserve, WOM warns and
the host should increase the reserve on the next page. Strict continuation
allows page-size and token-budget changes without skipping a cursor.

## Scale Evidence

A temporary 10,000-node seeded compact-reading fixture used:

```text
max_estimated_tokens: 8000
response_envelope_reserve_tokens: 2500
effective_items_token_budget: 5500
```

It completed 264 pages in 58.1 seconds. The largest page estimates were 5,500
items tokens and 6,879 compact service-result tokens. No page exceeded the
effective items budget or requested response budget, and the reserve covered
every measured envelope. All 10,000 ids were unique and all three readiness
signals completed.

This is a local synthetic observation, not an SLA or provider token count.

## Closed Actions

Measurement and reserve selection are read-only. WOM does not call a model,
inspect a provider context window, persist token state, create a host loop,
drop nodes, or rewrite archive files.
