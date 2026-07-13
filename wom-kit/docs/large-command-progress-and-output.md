# Large-Command Progress And Bounded Output

Status: implemented in v0.3.214; complete-only catalog JSONL in v0.3.216;
same-count suppression and counted-unit/rate contract in v0.3.222; safe receipt
phase and reporter coalescing in v0.3.223; explicit runtime-context full-Doctor
progress in v0.3.224; aggregate edge-receipt progress in v0.3.227; current
local-profile safety counters in v0.3.228

## Purpose

Large local archives can make a read-only command look frozen while it scans
many files. WOM-kit must show that work without echoing private archive content
or changing the meaning of the command result.

The shared v0.3.214 contract covers:

```text
archive ai-start-here
archive runtime-context
archive upgrade-check
archive zet-catalog
```

## Progress Contract

Add `--progress` to any of the three commands:

```powershell
archive ai-start-here <archive-root> --dry-run --progress --format json
archive ai-start-here <archive-root> --dry-run --full-doctor --progress --format json
archive runtime-context <archive-root> --full-doctor --progress --format json
archive upgrade-check <archive-root> --dry-run --progress --format json
archive zet-catalog <archive-root> `
  --status canonical `
  --projection reading `
  --coverage-mode strict `
  --cursor 0 `
  --dry-run `
  --progress `
  --format json
```

Progress is written only to stderr. The final result remains on stdout. This
keeps shell pipelines and JSON consumers able to separate liveness from the
command result.

The progress stream includes:

- immediate stage start and completion lines;
- current/total counts where the underlying operation has a safe total;
- total elapsed time and current-stage elapsed time;
- a stable work unit such as `zet_files` or `mint_receipts`;
- processed items per second;
- `eta=warming_up` until enough counted progress exists for an estimate;
- a 10-second heartbeat with the last completed stage and latest safe count.

Compact stderr prints one stage/count immediately, then suppresses that same
stage/count for 30 seconds unless the line is a heartbeat. Detailed substeps
remain available in Doctor verbose/progress-log surfaces, but they cannot create
dozens of identical `1/N progress` lines in an AI start-here run.

For `mint-receipts`, the count and total mean mint receipt files being checked.
They do not mean canonical zet files, target-id resolutions, or graph steps.

Since v0.3.223, a count-bearing heartbeat in the shared AI command reporter can
also include one fixed safe mint-receipt phase:

```text
receipt_checks
source_file_ref
target_file_ref
snapshot_file_ref
file_hash
target_frontmatter
mint_link
target_edge_evolution
edge_receipt_index
```

Unknown details produce no phase. Path-bearing source text is never copied; a
recognized message can produce only its fixed label. The reporter forwards
generic progress only once per stage/count; later same-count substeps update
phase state without invoking the compact formatter again. Direct Doctor verbose
output and explicit private progress logs retain detailed events. No validation
work is skipped.

Since v0.3.227, the filename index and targeted source-load phases have an
additional compact contract. A fast filename index prints start and done; only
an index that remains active for 10 seconds can add a count heartbeat. Targeted
source loads keep one aggregate across the complete Doctor run:

```text
sources=<sources loaded so far>
candidates=<candidate receipt documents opened so far>
cache_hits=<source-result cache hits so far>
```

The shared runtime reporter keeps that aggregate alive across surrounding
`mint-receipts` events and includes it in a 10-second heartbeat. Complete
Doctor exit prints one final `done` summary. The final source count is dynamic:
WOM-kit does not add a second broad pass merely to predict how many sources
will later require historical SHA checks.

Each source's `start`, `0/N`, `1/N`, `N/N`, and `done` events move to the
`edge-receipt-source-load-detail` trace. Compact stderr suppresses that trace;
direct `doctor --progress-detail verbose` and private `--progress-log` JSONL
retain it. Counts and fixed labels remain content-free in every mode.

Since v0.3.228, an older edge aggregate cannot hide a newer long-running
Doctor stage. While `local-profile-secret-safety` is current, shared compact
heartbeat uses only the fixed numeric form:

```text
checked_files=<files visited>
content_scanned=<text-like files scanned>
local_profiles=<local profile files checked>
skipped_dirs=<ignored directories skipped>
```

The final local-profile summary uses the same fields. The edge aggregate stays
available for the complete Doctor `done` summary after the safety stage, but it
does not override the current stage. A strict regular expression accepts only
those labels and non-negative integers; source paths and arbitrary trace text
cannot enter shared progress.

Progress is content-free. It does not emit local paths, zet ids, titles,
abstracts, body text, object refs, provider values, credential refs, tokens, or
secret values. Path-bearing Doctor trace messages are reduced to stage/count
events rather than forwarded.

## Full Result In Private Scratch

When the full result is too large for stdout, add a new archive-relative JSON
path under `.wom-scratch/diagnostics/`:

```powershell
archive zet-catalog <archive-root> `
  --coverage-mode strict `
  --cursor 0 `
  --dry-run `
  --progress `
  --output .wom-scratch/diagnostics/catalog-page-000.json `
  --format json
```

With `--output`, WOM-kit writes the full JSON result and prints only a compact
summary to stdout. The writer:

- accepts only archive-relative paths below `.wom-scratch/diagnostics/`;
- accepts only `.json` filenames;
- refuses path traversal and any existing destination;
- uses an atomic file replacement helper after the nonexistence check;
- labels the result as local scratch, not a WOM record or receipt;
- never echoes the local absolute path.

The full result can contain private catalog metadata such as titles and
abstracts. Keep it local, do not commit it, review it according to the archive's
privacy policy, and delete it when no longer needed.

The core inspection remains read-only. `--output` is an explicit exception that
creates one scratch result file and any missing parent directory inside the
allowlisted scratch surface. It does not write zets, manifests, receipts,
indexes, maps, provider state, or external backups.

## Honest Performance Boundary

The default `ai-start-here` path no longer runs Doctor. It returns bounded
identity, authority, entrypoint, and operational-context metadata. Use
`--full-doctor` when complete archive diagnostics are required; that broader
mode records its observed content-reading boundary. See
[AI Start-Here Quick And Full Inspection](ai-start-here.md).

CLI `zet-catalog --progress` reports path-metadata and frontmatter scan counts.
It does not make that scan disappear. Separate CLI invocations still use
separate processes and each process live-verifies its selected scope.

No persistent catalog cache is introduced in v0.3.214. A future optimization
must separately define private-data content, expiry, invalidation, crash
cleanup, snapshot revalidation, and ownership before it can persist catalog
state. Progress is visibility, not a performance-completion claim.

## v0.3.216 One-Process Catalog Output

`zet-catalog-pass` addresses repeated CLI scans without persisting a cache. It
runs all strict pages inside one process, keeps intermediate catalog state only
in memory, and revalidates local state before a multi-page completion.

Its required output is a new private `.jsonl` below
`.wom-scratch/diagnostics/`. The final path is published only after completion;
handled failures remove the invocation's partial. `--max-output-mib` bounds
disk growth. A forced termination can leave a hidden private partial, which
later runs count but never read or auto-delete. The JSONL must not be committed
and should be read incrementally then deleted. See
[zet Catalog One-Process Pass](zet-catalog-one-process-pass.md).
