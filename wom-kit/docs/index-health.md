# Index Health

Status: v0.3.91 read-only generated index drift check; v0.3.255 adds opt-in
progress/result capture and a crash-safe rebuild procedure; v0.3.256 adds
fail-closed frontmatter inspection and physical-path accounting
Date: 2026-06-17; updated 2026-07-17

`index-health` checks whether the generated local SQLite index still matches
the live zettel files.

The index is disposable and rebuildable. Commands such as `view-zets`,
`view-health`, `related-zets`, and `search` depend on it, so stale index rows
can make a real archive look emptier or older than it is.

## Commands

CLI:

Command shape:

```text
archive index-health <archive-root> --dry-run
```

```powershell
python wom-kit\cli\archive.py index-health <archive-root> `
  --dry-run `
  --format json
```

Long-running inspection with complete-only local result capture:

```powershell
archive index-health <archive-root> `
  --dry-run `
  --progress `
  --output .wom-scratch/diagnostics/index-health-20260716T180000Z.json `
  --format json
```

MCP:

```text
index_health
```

Inputs:

- `archive_root`
- `dry_run`, which must be true
- optional `max_items`

## Progress And Result Capture

`--progress` is opt-in. It writes only fixed content-free stage labels, safe
aggregate counts, elapsed time, and a 10-second heartbeat to stderr. Without
`--output`, the complete final JSON or text result stays on stdout. Progress
never includes absolute paths, zet ids, titles, body text, or object content.

`--output` accepts only a new archive-relative `.json` path below
`.wom-scratch/diagnostics/`. It rejects traversal and a preexisting destination
before inspection begins. Symbolic-link and Windows reparse-point components
are also rejected. The full result is published with no-overwrite semantics
only after the CLI reaches a complete result boundary, and stdout becomes a
compact completion summary.

The saved result includes `cli_output_artifact` and:

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

`completed` is not a success label and does not prove that a PTY displayed the
later compact summary. Use the scoped `exit_code` and `index_state` together.
A forced termination before result publication has no complete output file;
absence means the result is unconfirmed. A handled failure stores a sanitized
error type/code, never the raw exception message. Use a new output filename for
every attempt.

## What It Checks

The command compares:

- every safely enumerated live zettel archive-relative path, including a path
  whose frontmatter is unreadable or invalid,
- live paths with safely readable lifecycle metadata,
- indexed zettel paths,
- live and indexed `zettel_id`, `status`, and `kind`,
- zettel files modified after `db/archive-index.sqlite`.

It can report:

- `live_zettels_missing_from_index`,
- `index_has_paths_missing_from_live_zettels`,
- `indexed_zettel_metadata_differs_from_live_frontmatter`,
- `live_zettel_modified_after_index`,
- `live_zettel_frontmatter_unreadable_or_invalid`,
- `archive_index_schema_incomplete`,
- `archive_index_missing`.

Since v0.3.256, `summary.live_zettel_count` is the physical-path count rather
than only the number of paths whose YAML happened to parse. Separate
readable-metadata and issue counters plus bounded archive-relative samples make
an invalid delimiter, YAML object, lifecycle status, UTF-8 stream, or file read
visible. Fixed issue codes are used instead of raw parser/I/O messages. A new
unreadable file therefore makes health stale/incomplete; it can no longer be
silently absent from both sides of a false `current` comparison.

`summary.index_schema_complete` distinguishes a usable `zettels` table from a
SQLite file left behind when the very first index build stopped before schema
commit. That incomplete file is reported as `stale_or_incomplete` with zero
indexed rows, so the normal explicit rebuild procedure remains available
instead of ending in an unstructured `no such table` error.

It does not prove every part of a complete index build. In particular, it does
not compare every object, derived text, view, source map, edge, facet, or warning
count returned by `archive index`. `index_state: current` proves only the health
scope listed above.

## Safety Boundary

The `index-health` inspection is read-only. Opt-in `--output` is one explicit
local-scratch exception: it creates one result file and any missing parent
directory inside `.wom-scratch/diagnostics/`. That file is a private local
diagnostic, not a WOM record, receipt, canonical zet, or generated index.

It does not:

- rebuild the index,
- edit zettels,
- write manifests, receipts, or generated-index rows,
- read object bytes,
- call provider APIs,
- echo zettel body text,
- echo zettel titles,
- print absolute local paths,
- echo provider URLs.

It returns only archive-relative sample paths and basic drift counters.

For a well-formed zet, live inspection accepts only the exact supported opening
and closing frontmatter delimiter grammar, a YAML object, and lifecycle status
`draft`, `canonical`, `archived`, or `redacted`. It stops at the closing
delimiter and does not read the body. Invalid delimiter/YAML/object/status,
UTF-8, or I/O states expose no parsed frontmatter values or body. A malformed
file with no valid closing delimiter can require body bytes to prove that the
boundary is invalid; in that case `privacy_guards.zettel_body_text_read` is
honestly `true`. Those bytes and raw exception details are never echoed.

## Official Recovery Procedure

Use a new diagnostic filename at each step:

1. Run `index-health --dry-run --progress --output ... --format json`.
2. If the completed result has exit code 0, `index_state: current`, and zero
   live frontmatter inspection issues, stop.
3. If health reports `live_zettel_frontmatter_unreadable_or_invalid`, repair
   the bounded archive-relative source paths first. Rebuilding cannot repair a
   malformed source zet.
4. Only after source repair, if health still reports a missing or stale index,
   run:

   ```powershell
   archive index <archive-root> `
     --progress `
     --output .wom-scratch/diagnostics/index-20260716T180200Z.json `
     --format json
   ```

5. Judge the rebuild from `ok`, `state`, `index_rebuilt`, `index_complete`, and
   `cli_execution.exit_code` together. A completed quarantining rebuild is
   deliberately nonzero, safe, and incomplete.
6. Run `index-health` again with another new output filename. Only that final
   health result confirms currentness within this command's scope.

If an index output file is absent after interruption, do not immediately assume
that the database is old or current. The SQLite commit can succeed before the
later scratch publish fails. Run a fresh read-only health check to distinguish
that partial result-capture failure.

## Relationship To `archive index`

Use `index-health` to decide whether the generated index is stale.

Use `archive index` to rebuild the index after review. Rebuilds remain explicit;
`index-health` never runs them automatically.

Approved `mint-zet` operations already update the generated index through their
existing fast path. A successful mint therefore does not require an
unconditional full rebuild. The official sequence remains health, conditional
index, then health.

Since v0.3.255, `archive index` encloses schema setup, old-row deletion, all new
inserts, and metadata updates in one explicit SQLite transaction beginning with
`BEGIN IMMEDIATE`. Failure before the final commit rolls back the whole rebuild
and preserves the previously committed index. This prevents a delete-only
intermediate state from becoming the current generated index.

Since v0.3.256, one unreadable or invalid zettel does not roll back and preserve
an older logically unsafe row. The rebuild commits a path/stat-only row with
status `unreadable`, clears id/title/kind/body/frontmatter/hash content, and
creates no edge or facet rows for that file. The result is
`state: completed_with_quarantined_zettels`, `index_rebuilt: true`,
`index_complete: false`, `ok: false`, with process exit code 1 and fixed
path/code samples. This is a safely installed but incomplete generated index;
source repair is still required. It is not a complete success and not a
transaction rollback.

The same rebuild transaction writes generated-index metadata v0.2 with
`index_complete` and `quarantined_zettel_count`. Mint/promotion duplicate
approval checks and facet-scoped validation reject `index_complete: false`;
only source repair followed by a complete rebuild can restore that approval
boundary. A pre-v0.3.256 index has no current completeness evidence and should
be rebuilt after health is clean.

The quarantine boundary sanitizes WOM logical/API query results. It does not
claim forensic secure deletion from SQLite free pages, WAL files, filesystem
snapshots, backups, storage media, or the still-present source zettel.

This v0.3.256 document describes the core read/index/query/health boundary.
Revision/restore, retire-reconcile, abstract-backfill, and target-workpack
fingerprint ordering remain the explicit v0.3.257 follow-up. Bounded-memory
default S3-compatible transport remains the separate v0.3.258 release scope.

The basoon v0.3.254 incident demonstrated why both boundaries matter. The first
post-mint commands lost operator-visible output. A later official read-only
health run completed after roughly 90 seconds with exit code 1 and reported
8,586 live zettels, zero indexed zettels, and 8,586 missing rows. Output capture
loss did not prove index loss, but the later health result did; the transaction
fix addresses the index-loss cause while progress and scratch output address
operator observability.
