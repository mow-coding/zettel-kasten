# Decision: separate shared CLI version from client project version

Date: 2026-08-23

## Context

Several beta-client project folders can run under one Windows user account.
An isolated `uv tool` package environment still exposes one user-level
`archive.exe` on PATH, so replacing it can affect every session that resolves
that executable. A project source mirror and pin do not by themselves replace
the PATH command or provide a general-command sandbox.

## Decision

Treat these as separate evidence and mutation scopes:

1. public release availability;
2. wheel installation in an explicitly named environment;
3. the user-shared PATH launcher;
4. one client's project source mirror and version pin; and
5. one client's archive data.

Release verification must use a dedicated temporary environment and explicit
executable path without replacing the shared PATH launcher. A client update is
judged with `archive version <project-or-archive-root> --format json`, not
`archive --version` alone. Project update remains a separate exact-human
workflow.

## Consequences

- v0.4.3 does not claim automatic per-folder isolation for general commands.
- A shared CLI replacement can surprise every same-account client and must not
  be hidden inside release verification.
- Fully independent same-computer clients require dedicated environments or
  operating-system accounts until a separately designed project-runtime
  launcher exists.
- Runtime, project, archive, release, and live-result evidence remain distinct.
