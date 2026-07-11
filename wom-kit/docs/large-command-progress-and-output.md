# Large-Command Progress And Bounded Output

Status: implemented in v0.3.214; complete-only catalog JSONL in v0.3.216

## Purpose

Large local archives can make a read-only command look frozen while it scans
many files. WOM-kit must show that work without echoing private archive content
or changing the meaning of the command result.

The shared v0.3.214 contract covers:

```text
archive ai-start-here
archive upgrade-check
archive zet-catalog
```

## Progress Contract

Add `--progress` to any of the three commands:

```powershell
archive ai-start-here <archive-root> --dry-run --progress --format json
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
- elapsed time;
- `eta=warming_up` until enough counted progress exists for an estimate;
- a 10-second quiet-interval heartbeat with the last completed stage.

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
