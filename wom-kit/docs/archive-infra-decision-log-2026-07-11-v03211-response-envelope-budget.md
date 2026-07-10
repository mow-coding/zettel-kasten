# Decision Log: v0.3.211 Response Envelope Budget

Date: 2026-07-11
Status: implemented

## Decision

Keep `max_estimated_tokens` items-only by default. Add compact service-result
and envelope measurements to every page, plus an explicit opt-in reserve that
subtracts envelope room before item selection.

## Context

The host receives more than the `items` array, so an 8,000-token items estimate
can produce a larger actual structured response. Silently redefining the old
option as a whole-response limit would break compatibility, while a fixed
hidden reserve would conceal assumptions.

## Consequences

- Existing calls keep their current item-count and item-budget behavior.
- Reserve math and its measured adequacy are machine-readable.
- Measurement excludes its own block, pretty CLI whitespace, and MCP/JSON-RPC
  framing, and does not claim provider token accuracy.
- An insufficient reserve warns but never removes nodes or prevents progress.
- No token ledger, host goal/loop, archive write, or provider call is created.
