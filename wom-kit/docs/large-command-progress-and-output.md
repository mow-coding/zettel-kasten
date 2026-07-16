# Large-Command Progress And Bounded Output

Status: implemented in v0.3.214; complete-only catalog JSONL in v0.3.216;
same-count suppression and counted-unit/rate contract in v0.3.222; safe receipt
phase and reporter coalescing in v0.3.223; explicit runtime-context full-Doctor
progress in v0.3.224; aggregate edge-receipt progress in v0.3.227; current
local-profile safety counters in v0.3.228; index and index-health progress,
complete-only result capture, and crash-safe index rebuild in v0.3.255;
quarantined-index completion semantics and honest unreadable-source counts in
v0.3.256

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

Since v0.3.255, the same transport-safety contract also covers:

```text
archive index
archive index-health
```

## Progress Contract

Add `--progress` to any supported command:

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
archive index <archive-root> --progress --format json
archive index-health <archive-root> --dry-run --progress --format json
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

For `index` and `index-health`, `--progress` emits only fixed stage labels,
safe aggregate counts, elapsed time, and a 10-second heartbeat while a stage is
still active. It does not change exit-code semantics. Without `--output`, the
complete final command result remains on stdout exactly as it does without
`--progress`.

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

archive index <archive-root> `
  --progress `
  --output .wom-scratch/diagnostics/index-20260716T180000Z.json `
  --format json

archive index-health <archive-root> `
  --dry-run `
  --progress `
  --output .wom-scratch/diagnostics/index-health-20260716T180200Z.json `
  --format json
```

With `--output`, WOM-kit writes the full JSON result and prints only a compact
summary to stdout. The writer:

- accepts only archive-relative paths below `.wom-scratch/diagnostics/`;
- accepts only `.json` filenames;
- refuses path traversal and any existing destination;
- publishes only a complete JSON file rather than an in-place partial result;
- labels the result as local scratch, not a WOM record or receipt;
- never echoes the local absolute path.

For `index` and `index-health`, the stricter result writer also rejects every
symbolic-link or Windows reparse-point component, writes and `fsync()`s a unique
private partial, and atomically publishes only when the destination is still
absent. Windows uses no-overwrite rename semantics; other platforms use a
same-filesystem hard link. Concurrent attempts therefore have one winner and
cannot replace the first complete result.

The full result can contain private catalog metadata such as titles and
abstracts. Keep it local, do not commit it, review it according to the archive's
privacy policy, and delete it when no longer needed.

For `index` and `index-health`, the saved root object includes both the existing
`cli_output_artifact` metadata and this complete execution envelope:

```json
{
  "cli_execution": {
    "status": "completed",
    "exit_code": 0,
    "exit_code_scope": "command_result_before_terminal_transport",
    "terminal_output_delivery": "best_effort_not_observed",
    "started_at": "2026-07-16T09:00:00Z",
    "finished_at": "2026-07-16T09:01:30Z",
    "error": null
  }
}
```

`status: completed` means only that the CLI reached and saved its command-result
boundary. It does not mean that the command succeeded or that the surrounding
PTY/agent displayed the later compact terminal summary. Determine success from
`exit_code` together with the command result, including `ok` or `index_state`.
Handled failures store a fixed error type/code and never store the raw exception
message, which may contain a local path or parser excerpt.

Since v0.3.256, a rebuild that safely installs one or more path/stat-only
quarantine rows is also a completed nonzero command result, not an exception
artifact. Its saved result has `ok: false`,
`state: completed_with_quarantined_zettels`, `index_rebuilt: true`,
`index_complete: false`, and exit code 1. Result capture preserves those fields
and must not relabel “completed” as a successful complete index.

These two output files are complete-only. WOM-kit publishes the final path only
after it has a complete command result and execution envelope. A forced
termination before publication has no complete output file. File absence after
an interruption is therefore an unknown result, never success evidence. A
termination after publication can leave the complete file even if the compact
stdout/stderr summary is not delivered; judge that file by its command result
and scoped exit code. A completed nonzero result may have a file and must not be
relabeled as success.

With `--output`, the full result is stored in the scratch file and stdout becomes
the established compact completion summary. stderr remains the progress stream.
After publication those terminal messages are best-effort, so a closed terminal
cannot relabel the already completed command result.
A preexisting destination or a path outside `.wom-scratch/diagnostics/*.json`
is rejected before command work begins. Use a new filename for every attempt.

For inspection commands such as `zet-catalog` and `index-health`, the core
inspection remains read-only. `--output` is an explicit exception that creates
one scratch result file and any missing parent directory inside the allowlisted
scratch surface. It does not write zets, manifests, receipts, indexes, maps,
provider state, or external backups. `archive index` separately writes only its
disposable generated index through the crash-safe boundary below.

## v0.3.255 Crash-Safe Index Rebuild

`archive index` is a generated-index write, so its database safety is separate
from scratch result capture. The complete schema setup, old-row deletion, new
row insertion, and index metadata update run inside one explicit SQLite
transaction. The transaction begins inside the `executescript()` statement with
`BEGIN IMMEDIATE`; the existing final connection commit publishes the rebuild.

The basoon v0.3.254 incident exposed both boundaries. Three post-mint commands
lost their operator-visible final output. A later official read-only health run
completed after roughly 90 seconds with exit code 1 and reported 8,586 live
zettels, zero indexed zettels, and 8,586 missing rows. The first observation did
not prove why output disappeared; the later result separately proved that the
generated index had reached an empty-zettel state.

This boundary is required because Python `sqlite3.Connection.executescript()`
commits a pending transaction before running its script and does not add another
implicit transaction around the remaining Python inserts. A deletion performed
outside the rebuild transaction can therefore survive while later inserts roll
back. With the v0.3.255 boundary, an exception, cancellation, process loss, or
connection close before the final commit rolls the complete rebuild back and
preserves the previously committed index.

On a first-ever build there is no prior schema to preserve, and SQLite can
leave a small database file after rollback. `index-health` checks for the
`zettels` table before querying it and returns
`archive_index_schema_incomplete` / `stale_or_incomplete` instead of a raw
missing-table exception.

A temporary-database atomic swap was considered but rejected. Replacing a live
SQLite database on Windows while coordinating WAL and shared-memory sidecars is
more complex than using SQLite's own transaction and crash-recovery contract.

The database commit and the scratch result publish are two different
boundaries. If the database commit succeeds and the later `--output` publish
fails, the rebuilt index may already be current even though no complete result
file exists. Treat that as a partial result-capture failure and run a fresh
official `index-health` check; do not infer either success or failure from the
missing scratch file alone.

## v0.3.256 Quarantined Index Completion

The strict existing-archive zettel boundary accepts the supported frontmatter
delimiter grammar, a YAML object, and one lifecycle status from `draft`,
`canonical`, `archived`, or `redacted`. Invalid delimiter/YAML/object/status,
UTF-8, and I/O states yield fixed content-free issue codes. They never provide
parsed frontmatter or body content to the indexer.

The rebuild still commits its safe generated state. Each affected file gets a
path/stat-only `unreadable` row with logical content, edges, and facets cleared.
The normal transaction protects the complete replacement, while the command
result separately says the installed index is incomplete. This avoids two bad
outcomes: retaining an older queryable unsafe row by rolling back the rebuild,
or silently treating an omitted physical file as success.

`index-health` likewise keeps every safely enumerated physical zettel path in
its live count and reports separate readable-metadata and inspection-issue
counts. `live_zettel_frontmatter_unreadable_or_invalid` routes the operator to
source repair before another rebuild. A malformed delimiter may require reading
past the intended frontmatter boundary to prove it invalid; the privacy guard
reports that read honestly while never echoing the bytes.

Logical quarantine is not forensic secure deletion from SQLite free pages,
WAL, backups, snapshots, storage media, or the source file. This release also
does not claim strict fingerprint-first ordering for revision/restore,
retire-reconcile, abstract-backfill, or target-workpack flows; those follow in
v0.3.257. Bounded-memory default S3-compatible transport follows separately in
v0.3.258.

## Primary References

- Python documents the transaction boundary of
  [`sqlite3.Connection.executescript()`](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.executescript).
- SQLite documents explicit transaction behavior in
  [Transactions](https://www.sqlite.org/lang_transaction.html).
- Python documents the filesystem primitives used by the complete-only writer:
  [`os.fsync()`](https://docs.python.org/3/library/os.html#os.fsync),
  [`os.rename()`](https://docs.python.org/3/library/os.html#os.rename), and
  [`os.link()`](https://docs.python.org/3/library/os.html#os.link).

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
