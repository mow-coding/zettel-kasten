# Agent Operator Capabilities Manifest

Status: v0.3.148 read-only agent-operator surface

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

The `summary` includes:

- current WOM-kit version,
- version label,
- local release state,
- release notes presence,
- local git tag presence,
- latest local release tag,
- command count.

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

## Why It Exists

Real AI operators plan by assuming that tools exist. If `archive --version`
shows a development version or a command is only present in the local checkout,
the agent can accidentally plan against a feature that is not publicly
released.

The capabilities manifest gives the agent a stable first question to ask before
it starts chaining commands.
