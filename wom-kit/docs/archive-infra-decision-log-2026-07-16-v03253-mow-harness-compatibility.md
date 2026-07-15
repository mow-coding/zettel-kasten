# Decision Log: Optional MOW Harness Compatibility Boundary

Date: 2026-07-16
Status: accepted for v0.3.253

## Decision

Support MOW Harness as an optional external operating layer through namespace
isolation, explicit authority separation, and public interoperability guidance.
Do not bundle its installer, duplicate its state machine, grant its write or
activation approval, or reinterpret its local receipts as WOM knowledge.

## Context

WOM already reserves `/collab/` and `/.mow-harness/` as local-only. The external
MOW project has since added a source-alpha CLI and Cockpit work, while existing
WOM-shaped hosts can still contain manual pre-CLI Harness metadata.

Without one current boundary, an AI operator could either miss the existing
compatibility protections or overreach by treating an external source alpha as
a released WOM dependency. It could also confuse a successful file update with
Harness activation or treat coordination transcripts as canonical archive
records.

## Consequences

- WOM remains fully usable without MOW Harness.
- Generated archives and artifact hygiene keep both Harness namespaces outside
  normal archive and public-repository surfaces.
- The compatibility guide names the external read-only preview and separate
  write/activation boundary without promising an npm package or real apply.
- Durable outcomes must be deliberately captured through normal WOM records.
- No command, archive schema, receipt, model call, provider call, remote call,
  database call, UI, or new write authority is added.
