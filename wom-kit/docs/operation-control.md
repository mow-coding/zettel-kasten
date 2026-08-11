# Bounded operation control

`operation-control` gives a later CLI process a small, content-free view of a
long command. It is available only when one of these commands starts with an
explicit `--output` file:

- `project-version-update`;
- `index`; or
- `index-health`.

Without `--output`, those commands keep their existing behavior and create no
operation journal. With `--output`, stderr prints an opaque
`op:sha256:<digest>` reference early. The same reference and follow-up command
templates are stored under `cli_output_artifact.operation` in the complete
JSON result.

## Start an observable command

From an archive root:

```powershell
archive index <archive-root> `
  --progress `
  --output .wom-scratch/diagnostics/index-result.json `
  --format json

archive index-health <archive-root> `
  --dry-run --progress `
  --output .wom-scratch/diagnostics/index-health-result.json `
  --format json
```

From a project root, `project-version-update` uses the project-local diagnostic
scope:

```powershell
archive project-version-update <project-root> `
  --target vX.Y.Z --dry-run --progress `
  --output .zettel-kasten/diagnostics/version-update-result.json `
  --format json
```

If the updater is started with an archive root instead, use an archive-local
`.wom-scratch/diagnostics/*.json` output. Always use a new filename; output
publication refuses overwrite and path traversal.

## Inspect, wait, or recover

Use the exact root that started the command and the exact opaque reference:

```powershell
archive operation-control <project-or-archive-root> `
  --operation-ref op:sha256:<digest> `
  --action status --dry-run --format json

archive operation-control <project-or-archive-root> `
  --operation-ref op:sha256:<digest> `
  --action wait --timeout-seconds 60 --dry-run --format json

archive operation-control <project-or-archive-root> `
  --operation-ref op:sha256:<digest> `
  --action recovery-plan --dry-run --format json
```

`wait` accepts 1 through 60 seconds. `deadline_reached` means only that this
wait call stopped. It is not a command failure, cancellation, or proof that the
writer stopped. Run `status` or another bounded `wait` with the same reference.

The view exposes only fixed fields such as the operation kind, opaque owner,
stage, elapsed time, last completed stage, terminal state, result state, and
safe next actions. It never echoes a process id, local path, private value, or
raw error and never acquires a command lock.

## Terminal truth

A terminal journal line alone is insufficient. `completed_result_available`
requires the current output file to match its root-relative output binding,
size, SHA-256 digest, and embedded operation, run, root, command, result, and
exit evidence. A missing, moved, changed, ambiguous, torn, copied-to-another-
root, future-dated, or otherwise unverifiable record fails closed as
`recovery_required` with top-level `ok: false`.

If journal finalization was interrupted but an old observation and one exact
complete output agree, status may report
`terminal_source: complete_output_reconciliation`. This proves only the saved
CLI result. It does not prove fresh domain truth; follow the command-specific
verification action.

The journal hash chain detects torn records and ordinary drift. It is not a
MAC, signature, authority receipt, or defense against a hostile process running
as the same local user.

## Deliberately unsupported in this version

```powershell
archive operation-control <project-or-archive-root> `
  --operation-ref op:sha256:<digest> `
  --action cancel --approve --format json
```

This always returns nonzero with `operation_cancel_not_supported`,
`cancel_supported: false`, `cancel_requested: false`, and `writes: false`.
There is no cooperative cancel request, force kill, lock deletion, or rollback
trigger. `resume_supported` is also always false; recovery starts a fresh
command only after command-specific authority checks say that is safe.

There are no aliases, MCP method, daemon, queue, background launcher, or
operation-owned process supervisor in this release.
