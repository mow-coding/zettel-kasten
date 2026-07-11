# zet Catalog Scale And Token Budget

Status: implemented in v0.3.206; routed-reading cost comparison in v0.3.210; response-envelope measurement and reserve in v0.3.211; compact continuation comparison in v0.3.212

## Why This Exists

WOM requires every zet in a declared scope to remain discoverable. A host AI
must not call top-k retrieval complete coverage. At the same time, 1,000 or
10,000 abstracts and local connections cannot be assumed to fit one model
context. WOM therefore reports the work and divides it honestly; the host
application owns goal, loop, branching, and continuation UI.

## Workload Contract

Every catalog response reports both `scope` and `page` estimates:

```text
abstract_chars
estimated_abstract_tokens
items_json_chars
items_json_utf8_bytes
estimated_items_json_tokens
```

The estimate is `ceil(character_count / 4)`. It is a deterministic planning
heuristic, not provider-reported usage. The items estimate includes returned
catalog fields such as ids, titles, abstracts, facets, ties, and edges. It does
not include zet bodies or the outer response envelope.

Use a host-sized page without dropping nodes:

```powershell
archive zet-catalog <archive-root> `
  --status canonical `
  --projection reading `
  --coverage-mode strict `
  --cursor 0 `
  --page-size 1000 `
  --max-estimated-tokens 8000 `
  --dry-run `
  --format json
```

Continue with `next_cursor`, `snapshot.id`, and `coverage.continuation_token`
until `archive_wide_coverage_claim_ready: true`. One item is returned even when
it alone exceeds the estimate so the loop always makes progress.

v0.3.211 also measures the compact service result and its non-item envelope.
Optional `--response-envelope-reserve-tokens <n>` subtracts explicit envelope
room from `max_estimated_tokens`; omitting it preserves items-only semantics.
See [zet Catalog Response Envelope Budget](zet-catalog-response-envelope-budget.md).

After retaining the full first strict page, add `--response-profile
continuation` on later pages to omit repeated scope diagnostics while keeping
items and completion evidence. See
[zet Catalog Compact Continuations](zet-catalog-compact-continuations.md).

## Session Consistency

MCP materializes the first safe catalog snapshot in process memory. It serves
intermediate pages from that snapshot, then revalidates all selected local path
metadata before the completing page. A changed snapshot blocks completion and
requires a restart at cursor 0.

This cache:

- is process-local and bounded;
- is never written to the archive;
- is not a canonical map or index;
- does not replace local zet files;
- does not create WOM goal/loop state.

CLI invocations live-verify each page because separate processes do not share
the MCP session cache.

Since v0.3.216, terminal hosts that intend to complete the full chain can use
`zet-catalog-pass`. It applies the same process-memory snapshot and completion
revalidation in one CLI invocation, then publishes a private scratch JSONL.
This does not create a persistent cache: ordinary separate CLI page calls still
live-verify independently, and the pass memory disappears with its process.

## Reproducible Benchmark

The benchmark creates only a temporary fake archive:

```powershell
python wom-kit/tools/benchmark_zet_catalog.py `
  --zet-count 10000 `
  --page-size 1000 `
  --abstract-chars 120 `
  --max-estimated-tokens 8000 `
  --response-envelope-reserve-tokens 2500 `
  --compact-continuations `
  --projection reading `
  --coverage-mode strict `
  --order seeded_connection_walk `
  --seed-index 9000 `
  --format json
```

Two v0.3.210 2026-07-11 Windows seeded strict runs observed:

| Measure | `reading` | `routed_reading` |
| --- | ---: | ---: |
| zets collected / unique | 10,000 / 10,000 | 10,000 / 10,000 |
| pages | 179 | 257 |
| pages above requested estimate | 0 | 0 |
| largest estimated page | 7,925 | 7,913 |
| catalog pass time | 50.8 seconds | 53.8 seconds |
| items-only scope estimate | 1,414,699 | 2,026,799 |

Both runs parsed 10,000 frontmatter files once, checked path metadata twice,
traversed 9,999 passages, placed all 10,000 nodes in the seeded prefix, needed
no fallback component, and reached node, abstract, and id-follow-up readiness.
The abstract-only scope estimate was 300,000 tokens.

The host timing is an observation, not a cross-machine service-level promise.
The fixture uses one simple edge per zet and 120-character ASCII abstracts. A
real archive can differ substantially. `routed_reading` deliberately spends
more tokens on per-item order reasons; ordinary `reading` omits those fields.
The token figures are the documented heuristic, not model/provider accounting.

## Response Reserve Observation

On the same 10,000-node compact fixture, total 8,000, envelope reserve 2,500,
and effective item budget 5,500 completed 264 pages in 58.1 seconds. The largest
items estimate was 5,500 and the largest compact service-result estimate was
6,879. No page exceeded the effective items budget or requested response
budget, and every measured envelope fit the reserve.

The compact service-result estimate excludes its own measurement block, CLI
pretty-print whitespace, and MCP/JSON-RPC framing. It is still a planning
heuristic rather than an exact context-window guarantee.

## Compact Continuation Observation

Equivalent 10,000-node runs both completed 264 pages. Full responses on every
page measured 1,785,893 cumulative service-result tokens. One full page plus
263 compact continuation pages measured 1,671,758: 114,135 fewer, or 6.39%.
Both returned 10,000 unique nodes, completed all three readiness signals, and
recorded no item-budget, response-budget, or reserve-insufficiency pages.

This comparison measures response shape, not model comprehension or provider
billing. It does not justify skipping the full first page or any node.

## Performance Boundary

When available, WOM-kit uses PyYAML's C safe loader and otherwise falls back to
the prior safe loader. Cold catalog frontmatter parsing uses at most eight
threads. No dependency beyond PyYAML, generated SQLite index, vector database,
provider call, or body scan is required.
