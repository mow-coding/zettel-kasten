# Bounded operation control

`operation-control` gives a later CLI process a small, content-free view of a
long command. It is available only when one of these commands starts with an
explicit `--output` file:

- `project-version-update`;
- `index`; or
- `index-health`; or
- `staged-cleanup-check`.

Without `--output`, those commands keep their existing behavior and create no
operation journal. With `--output`, stderr prints an opaque
`op:sha256:<digest>` reference early. The same reference and follow-up command
templates are stored under `cli_output_artifact.operation` in the complete
JSON result.

For `staged-cleanup-check`, operation control keeps only the inspection state,
the `safe_to_cleanup` boolean, four bounded counts, and fixed reason codes. It
never copies staged paths, filenames, object ids, hashes, receipt names, or raw
messages. A complete inspection with `safe_to_cleanup: false` is a valid saved
result with process exit `1`, not a transport failure. Deferred entries remain
staged and also produce that not-safe result.

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

`completed_result_available` also does not mean that the domain command
succeeded. For example, a project updater can finish with a complete bound
result whose own `ok` is false because materialization was safely blocked. In
that case operation recovery remains false because no output was lost, while
`result.ok: false` and the allowlisted `result.domain` projection show that the
update still needs attention.

For `project-version-update`, operation control copies no free-form blocker
message. It projects only a grammar-checked target tag, fixed blocker codes,
the exact `materialization_plan_sha256`, and sorted ordinal references such as
`update-entry:0001`. For one reference, status and recovery-plan return a
path-free single-entry command like:

```powershell
archive project-version-update-collision <project-or-archive-root> `
  --target vX.Y.Z `
  --entry-ref update-entry:0001 `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --action inspect --dry-run --format json
```

For multiple references, they return one batch command instead of asking the
operator to run many serial inspections:

```powershell
archive project-version-update-collision <project-or-archive-root> `
  --target vX.Y.Z `
  --expected-plan-sha256 sha256:<64-lowercase-hex> `
  --action inspect-all --dry-run --format json
```

`inspect-all` derives the exact complete set from the unchanged plan digest and
prints only counts, fixed kinds, and the remediation route. It never accepts a
caller-supplied partial reference list.

The collision command reruns the planner and refuses digest or ordinal drift.
Do not repeat updater approval merely because operation recovery is false.
When the safe projection is incomplete, inspect the bound complete output and
run only a new updater dry-run after resolving its fixed blocker codes.

Successful transport is also routed by the updater's allowlisted status, not by
a generic success sentence. `ready_for_approval` and
`ready_to_fetch_on_approve` remain dry-run review states and point to a separate
approval only after review. `preview_only_platform_unsupported` says that no
update was applied and requires a fresh Windows preview.
`updated_restart_required` points to a new-process `archive version` check,
while `no_change` says that neither a write nor restart is required and asks
only for version verification. An unknown successful status is not interpreted;
it points back to the complete bound output and a fresh dry-run. Status, wait,
and recovery-plan share these exact punctuation-free routes.

If collision preservation reports `recovery_required`, its deterministic
private case or owned project-update lock is intentionally retained. Do not
delete the lock, move the payload back, overwrite a receipt, or rerun either
approval. Preserve that state for operator review. This is distinct from an
intact completed updater output whose operation-control recovery flag is
false.

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
