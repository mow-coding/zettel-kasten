# Agent Operator Capabilities Manifest

Status: v0.4.12 working-tree parser, help, and runtime approval truth

`archive capabilities --machine` lets an AI operator ask one practical question:

```text
What can this local WOM-kit installation actually run right now?
```

This is not a web dashboard. It is a machine-readable answer that an AI helper
can read before planning a workflow for a human.

## Command

```powershell
archive capabilities --machine
```

To show only release/version identity and command count:

```powershell
archive capabilities --machine --no-commands
```

## Response Envelope

The command uses an agent-facing envelope:

```text
ok / state / summary / data / blockers / warnings / privacy_guards
```

The `data.commands` list is generated from the actual local CLI parser. It
includes:

- command name,
- aliases,
- help text,
- required positional arguments,
- options,
- nested subcommands,
- runnable status.

v0.4.1 introduced `data.approval_status_inventory` with schema
`wom-kit/command-approval-status-inventory/v0.1`. v0.4.10 introduced and
v0.4.11-v0.4.12 continue the successor v0.2 shape, which adds machine-readable conditional
approval scope. Unlike the legacy flattened
command summary, this inventory walks canonical executable paths at every
parser depth and keeps all accepted alias paths attached to their canonical
record. Each record includes:

- `canonical_path` and `alias_paths`,
- `approval_status`,
- the fixed-close `approval_reason_code` when applicable,
- `approval_scope` (`null`, an argument/value allowlist, or an exactly-one
  argument-flag allowlist, an any-matching argument-flag allowlist, plus the fixed-close
  status outside that allowlist),
- whether `--dry-run` is exposed, and
- `invocation_surface_available: true`.

The three approval states mean:

- `approval_available`: this parser path exposes `--approve` and is not in the
  canonical fixed-close set;
- `approval_fixed_closed`: this parser path exposes `--approve`, but the
  current gate requires
  `compound_exact_human_approval_binding_required`; and
- `approval_not_exposed`: this parser path does not expose `--approve`.

These are parser facts, not execution promises. `approval_available` does not
mean that archive-specific prerequisites have passed. `approval_not_exposed`
does not mean that the command is read-only.

For the current v0.4.12 working-tree parser, the inventory snapshot is:

```text
canonical executable command paths: 315
alias invocation paths:              259
all invocation paths:                574
approval_available:                   47
approval_fixed_closed:                67
approval_not_exposed:                201
conditional approval paths:             9
dry_run_exposed:                     271
unmatched fixed-close entries:         0
```

The historical v0.4.0 release count remains 79 fixed-close command paths.
Later releases reopen only exact, operation-specific routes while each handler
independently enforces the same boundary. Parser availability is not permission
to skip archive prerequisites, approval, or post-write verification.

v0.4.3 made `migrate` conditional on the sole exact-supported target. The v0.2
inventory records the allowed argument value and the fixed-close status/reason
for every value outside that scope.

v0.4.6 adds a second conditional scope without adding a top-level command.
`object-storage-adopt-existing` is approval-available only when exactly one of
`--preserve-local-only` or `--formal-adoption` selects the operation-specific
exact writer. No selected flag, both flags, or the legacy argument family stays
fixed closed; the handler independently enforces that same boundary.

v0.4.7 adds five receipt-bound conditional scopes without adding top-level
commands. `objet-capture`, `revert-edge`, `external-locator-record`,
`zet-title-remap-write`, and `zet-title-remap-revert` enter an operation-specific
or common exact local-recovery writer only
when one of their explicitly listed recovery-mode flags is present. The v0.2
inventory represents this as `argument_flag_any_allowlist`; every legacy mode
outside those flags remains fixed closed, and each handler independently
enforces the same boundary.

v0.4.8 adds exact existing-intake selection under `objet-capture-selection`
and advertises only the supported rejection mode under
`relation-candidate-decide`. It also reopens `object-storage` for exact local
setup registration only: that writer records local metadata and a receipt but
does not read credentials, call a provider, create a bucket, upload, copy, or
sync. These changes produce 46 approval-available paths, 68 fixed-closed paths,
and nine conditional scopes without changing the 315 canonical command paths.

v0.4.9 reopened only the strict one-file `source-intake-record` exact-human
route. v0.4.10 additionally opens the bounded `source-intake-batch` and its
authenticated local `objet-capture-batch` handoff without adding a top-level
command. This produces 49 approval-available paths and 65 fixed-closed paths.
The handlers still enforce the full operation-specific manifest and upstream
evidence requirements; parser availability alone grants no write authority.
Doctor may use this inventory to report requested dry-run mode and same-argument
approval mode separately; that metadata executes nothing and does not prove
archive prerequisites.

v0.4.11 centralizes the fixed-close truth used by help, read-only plans, and
machine status. A validation digest from canonical revision or never-minted
draft discard preview is explicitly not approval authority. This clarification
changes no parser path counts and opens no writer.

v0.4.12 reconciles two residual parser/help/runtime mismatches without adding a
command. `derive-text capture` and
`zet-revision-restore-proposal-from-snapshot` are now fixed closed on all three
surfaces and return `compound_exact_human_approval_binding_required` before
private source, receipt, snapshot, archive, or target reads. Their dry-run
previews remain available, but neither path exposes current write authority.
This moves the current working-tree snapshot from the historical v0.4.11
49/65 split to 47 approval-available paths and 67 fixed-closed paths.

The `summary` includes:

- current WOM-kit version,
- version label,
- local release state,
- release notes presence,
- local git tag presence,
- latest local release tag,
- command count.

It also includes the three approval-status counts. With `--no-commands`, both
command arrays are empty while their counts remain available. The legacy
`summary.command_count` and the inventory's
`canonical_executable_command_count` have different traversal contracts; do
not treat them as interchangeable totals.

## Release State

`release_state` is local-only:

- `released_local_tag_present`: the local git checkout has a matching
  `vX.Y.Z` tag.
- `documented_release_candidate`: release notes exist, but the matching local
  tag is not present yet.
- `development_snapshot`: no matching local tag or release note is present.

The command does not call GitHub or any provider. A release supervisor should
still verify remote releases before publishing.

## Safety Boundary

The command:

- writes nothing,
- calls no providers,
- checks no network,
- opens no archive content,
- echoes no local absolute paths,
- echoes no tokens or secret values.

The approval-status inventory itself is derived from the already-built parser.
It does not inspect archive files, evaluate prerequisites, call the network or
a provider, render command help, or execute a command handler. It declares
`parser_derived: true`, `prerequisites_evaluated: false`,
`external_effects_performed: false`, and `private_values_echoed: false`.

## Related Failure Envelope

`wom-kit/cli-error/v0.1` is the content-free JSON failure contract used by the
v0.4.1 parser and repaired high-risk command paths. It separates usage errors
(exit code `2`) from policy/precondition failures (exit code `1`).
`effects_state: none` means the protected workflow did not start;
`effects_state: unknown` means an exact-human workflow had started and its
durable claim must be reconciled without automatic retry. The empty
`files_written` field does not turn an `unknown` effect into proof of no write.

## Why It Exists

Real AI operators plan by assuming that tools exist. If `archive --version`
shows a development version or a command is only present in the local checkout,
the agent can accidentally plan against a feature that is not publicly
released.

The capabilities manifest gives the agent a stable first question to ask before
it starts chaining commands.
