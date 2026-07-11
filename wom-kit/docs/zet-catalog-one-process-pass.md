# zet Catalog One-Process Pass

Status: implemented in v0.3.216

## Plain-Language Purpose

Ordinary CLI catalog pages are independent processes. Each process must inspect
the selected local files again, so a large archive can spend most of its time
repeating the same frontmatter scan.

`zet-catalog-pass` completes the existing strict page chain inside one process.
It does not invent a new map or make local files secondary. It gives the same
local zet nodes one temporary reading session, then destroys that memory when
the command exits.

## One Command

```powershell
archive zet-catalog-pass <archive-root> `
  --status canonical `
  --projection reading `
  --page-size 200 `
  --max-estimated-tokens 8000 `
  --response-envelope-reserve-tokens 2500 `
  --max-output-mib 256 `
  --output .wom-scratch/diagnostics/catalog-pass.jsonl `
  --dry-run `
  --progress `
  --format json
```

Aliases:

```text
catalog-pass
zet-catalog-drain
```

The command always starts at cursor zero and always uses strict contiguous
coverage. The first page keeps the full diagnostics. Later pages use the
compact continuation profile while retaining every item, snapshot, chain, and
readiness signal.

## Scan And Revalidation

The first page:

1. enumerates the selected local zet paths;
2. reads frontmatter only;
3. builds the ordinary catalog snapshot and order;
4. returns the first strict page.

Intermediate pages reuse that materialized snapshot in process memory. They do
not reread every frontmatter file.

Before a multi-page pass returns its completing page, WOM-kit enumerates the
selected paths and checks their size/mtime signatures again. Changed entries
are reparsed. If the resulting snapshot differs from the first page, completion
blocks with `catalog_snapshot_changed` and no complete output is published.

This final check detects the catalog evidence covered by the existing snapshot
contract. It is not a body-byte hash and does not claim that zet bodies were
read.

## Private JSONL

The output contains:

```text
catalog_pass_header
catalog_page (one line per strict page)
catalog_pass_footer
```

Each line is standalone JSON. A host AI should read one line or a small range
at a time, process those zet summaries, and continue until the footer. It should
not inject the whole JSONL into one model response.

The file can contain private zet ids, titles, abstracts, facets, ties, and
edges. It contains no zet body text or objet bytes. It is local scratch, not a
zet, map, index, receipt, or backup. Never commit it. Delete it after the host
has consumed or reviewed the pass.

## Complete-Only Publication

The destination must:

- be archive-relative under `.wom-scratch/diagnostics/`;
- end in `.jsonl`;
- not already exist;
- fit the reviewed `--max-output-mib` bound (default 256 MiB, maximum 2048 MiB).

WOM-kit writes an exclusive randomized hidden partial first. The final path is
created without overwriting an existing destination only after strict coverage,
completion revalidation, footer write, flush, and file sync all succeed.

Handled blockers and failures remove the partial created by that invocation.
A forced process termination can leave a hidden private partial. A later run
reports only the count of matching pre-existing partials. It does not read or
delete them because one could belong to another running process. Confirm that
no pass is active before manual cleanup.

## Boundaries

The command:

- uses no persistent catalog cache;
- creates no generated map, index, WOM goal, or loop state;
- writes no zet, objet, manifest, receipt, provider state, or external DB row;
- calls no provider or model;
- reads no secret or objet byte;
- keeps items out of stdout and progress;
- emits only content-free progress counts and heartbeat to stderr.

Ordinary paged CLI `zet-catalog` remains compatible and continues to live-check
each independent invocation. MCP keeps its existing bounded process-local
session cache. This command solves repeated CLI process scans only for a pass
that a host chooses to complete in one invocation; it does not solve model
context limits or prove model comprehension.
