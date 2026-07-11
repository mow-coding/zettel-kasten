# Decision Log: v0.3.213 Local Sovereignty Authority

Date: 2026-07-11
Status: implemented

## Decision

Make local WOM the explicit canonical working and recovery authority. Treat
GitHub as metadata/version-history backup, object storage as objet-byte backup,
and external databases as map backup or replica layers.

## Context

Older documents accurately described what each external substrate stores but
did not consistently say which copy wins. An AI could mistake a warehouse or
relationship database for the canonical archive.

## Consequences

- One machine-readable contract is shared by the CLI, runtime context, AI
  start-here surface, recovery plan, and upgrade check.
- Local reviewed records win conflicts by default; reconciliation stays
  explicit and reviewed.
- External maps must be regenerable from local relation-bearing records.
- Backup completion claims require boundary-specific evidence. Missing generic
  GitHub and external-DB receipts remain explicit gaps.
- The command performs no live audit, provider call, network access, secret
  read, archive write, or zet migration.
