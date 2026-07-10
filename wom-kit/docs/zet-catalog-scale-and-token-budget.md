# zet Catalog Scale And Token Budget

Status: implemented in v0.3.206

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

## Reproducible Benchmark

The benchmark creates only a temporary fake archive:

```powershell
python wom-kit/tools/benchmark_zet_catalog.py `
  --zet-count 10000 `
  --page-size 1000 `
  --abstract-chars 120 `
  --max-estimated-tokens 8000 `
  --projection reading `
  --coverage-mode strict `
  --format json
```

One v0.3.207 2026-07-11 Windows strict-reading run observed:

| Measure | Result |
| --- | ---: |
| zets collected / unique | 10,000 / 10,000 |
| pages | 179 |
| missing or duplicate ids | 0 |
| pages above requested estimate | 0 |
| largest estimated page | 7,925 tokens |
| frontmatter parses across pass | 10,000 |
| path metadata checks across pass | 20,000 |
| materialized intermediate pages | 177 |
| completion revalidations | 1 |
| catalog pass time | 52.4 seconds |
| abstract-only scope estimate | 300,000 tokens |
| compact reading items-only scope estimate | 1,414,699 tokens |
| full items-only scope estimate | 2,064,699 tokens |

The host timing is an observation, not a cross-machine service-level promise.
The fixture uses one simple edge per zet and 120-character ASCII abstracts. A
real archive can differ substantially. The token figures are the documented
heuristic, not model/provider accounting.

## Performance Boundary

When available, WOM-kit uses PyYAML's C safe loader and otherwise falls back to
the prior safe loader. Cold catalog frontmatter parsing uses at most eight
threads. No dependency beyond PyYAML, generated SQLite index, vector database,
provider call, or body scan is required.
