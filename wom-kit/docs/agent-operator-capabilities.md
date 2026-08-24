# Agent Operator Capabilities Manifest

Status: v0.4.3 candidate parser-derived approval-status inventory

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
`wom-kit/command-approval-status-inventory/v0.1`. The v0.4.3 candidate returns
the successor v0.2 shape, which adds machine-readable conditional
approval scope. Unlike the legacy flattened
command summary, this inventory walks canonical executable paths at every
parser depth and keeps all accepted alias paths attached to their canonical
record. Each record includes:

- `canonical_path` and `alias_paths`,
- `approval_status`,
- the fixed-close `approval_reason_code` when applicable,
- `approval_scope` (`null`, an argument/value allowlist, or an exactly-one
  argument-flag allowlist plus the fixed-close
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

For the v0.4.3 candidate parser, the inventory snapshot is:

```text
canonical executable command paths: 315
alias invocation paths:              259
all invocation paths:                574
approval_available:                   36
approval_fixed_closed:                78
approval_not_exposed:                201
dry_run_exposed:                     270
unmatched fixed-close entries:         0
```

The 78 v0.4.2 fixed-close entries preserve the v0.4.0 boundary except that
`zettel-objet-link` is now operation-specifically bound and available for local
exact-human approval. `zettel-objet-link-revert`, Objet capture writers, and
the project update/collision/bytecode writers remain fixed closed. The
historical v0.4.0 release count was 79. The additional available path is the
existing `git-backup-reconcile-plan` family, whose approval mode requires a
complete private exact Git selection and stored non-interactive credentials;
it does not add a new top-level command or an MCP writer.

Candidate v0.4.3 changes this parser snapshot to 36 `approval_available` and 77
`approval_fixed_closed`: top-level `migrate` leaves the fixed-close inventory
because the single `notion-source-properties` target now has an
operation-specific exact-human writer. This is conditional target availability,
not global migration authority. The `migrate` handler still returns
`compound_exact_human_approval_binding_required` before mutation for every
other approved target. The earlier v0.1 inventory could not express that target
choice; v0.2 records `approval_scope.argument: --target`, the sole
allowed value `notion-source-properties`, and the fixed-close status/reason for
every value outside that scope. The handler independently enforces the same
boundary.

v0.4.6 adds a second conditional scope without adding a top-level command.
`object-storage-adopt-existing` is approval-available only when exactly one of
`--preserve-local-only` or `--formal-adoption` selects the operation-specific
exact writer. No selected flag, both flags, or the legacy argument family stays
fixed closed; the handler independently enforces that same boundary.

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
