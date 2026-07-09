# Archive Infra Decision Log - v0.3.201 AI Start-Here Surface

Date: 2026-07-09
Release: v0.3.201

## Context

OpenWiki's public demo showed a simple repo-documentation pattern: generate one
obvious documentation directory, make a start-here index, and wire agent
instructions to that index. WOM already had deeper runtime materials, but those
materials were spread across `runtime-context`, `canonical_entrypoints`,
`AGENTS.md`, `ops/operational-context.yml`, capability discovery, and response
contracts.

## Decision

Add a read-only `archive ai-start-here <archive-root> --dry-run --format
markdown|json` command, with `start-here` and `operator-start-here` aliases.

The command is a compact projection over existing runtime-context data. It is
not a broad archive summarizer and does not read zettel bodies or objet bytes.

## Consequences

- AI operators now have one beginner-friendly first command before broad archive
  exploration.
- The existing runtime-context safety model remains the source of truth.
- Local absolute paths remain redacted by default.
- Future work can decide whether to add an approval-gated generated file, but
  v0.3.201 deliberately keeps the surface read-only.
