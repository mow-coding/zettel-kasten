# zet Catalog Compact Continuations

Status: implemented in v0.3.212

## Why This Exists

A strict archive-wide catalog pass may need hundreds of pages. The items change
on every page, while several diagnostic sections are expensive to repeat.
Repeating all of those sections spends host context without helping the AI read
another zet.

v0.3.212 adds an opt-in continuation response profile. It reduces repeated
metadata only. It does not reduce the selected scope, skip a node, change item
projection, weaken snapshot validation, or replace the continuation chain.

## Required First Page

The first strict page must use the default full response:

```powershell
archive zet-catalog <archive-root> `
  --projection reading `
  --coverage-mode strict `
  --cursor 0 `
  --max-estimated-tokens 8000 `
  --response-envelope-reserve-tokens 2500 `
  --dry-run `
  --format json
```

Retain that page's full diagnostics. For every later strict page, the
host may add:

```powershell
--response-profile continuation
```

MCP uses `response_profile: "continuation"`. The profile blocks at cursor zero
or outside strict coverage mode. A host may switch back to `full` on a later
page when it needs the repeated diagnostics again.

## What The Continuation Profile Omits

Only these repeated sections are omitted:

```text
abstract_counts
abstract_coverage
identity_coverage
order_evidence
scan
closed_actions
workload_estimate.scope
```

The response keeps:

- every page item and its selected projection;
- cursor, total, remaining, and all three readiness signals;
- snapshot id and strict continuation token;
- page-entry digest and cumulative chain hash;
- session consistency and completion revalidation state;
- page and measured service-result token estimates;
- privacy guards, warnings, blockers, and next actions.

`response_profile_contract` names the omitted sections and states that items,
coverage semantics, snapshot, and token remain unchanged. The strict token does
not bind the response profile, so profile changes between pages do not restart
or fork the coverage chain.

## Scale Evidence

Two temporary 10,000-node seeded strict-reading runs used the same 8,000-token
request, 2,500-token response reserve, and 5,500-token effective item budget:

| Measure | Full on every page | Full first page + compact continuations |
| --- | ---: | ---: |
| Pages | 264 | 264 |
| Full / continuation profile pages | 264 / 0 | 1 / 263 |
| Cumulative estimated service-result tokens | 1,785,893 | 1,671,758 |
| Difference | - | 114,135 fewer (6.39%) |
| Largest estimated service result | 6,905 | 6,781 |
| Largest continuation result | n/a | 6,472 |

Both runs returned 10,000 unique nodes and completed node, abstract-reading,
and unique-id follow-up readiness with no item-budget, response-budget, or
reserve-insufficiency pages. Timing varied and is not used as a performance
claim. Token values use WOM's four-characters-per-token heuristic, not provider
tokenization or billing.

## Safety Boundary

The profile is response shaping, not memory summarization. It calls no model or
provider, reads no zet body or objet bytes, writes no archive file, persists no
map or host loop, and creates no receipt. Missing first-read text and duplicate
ids remain visible through the first full page and the readiness signals; WOM
does not repair them automatically.
