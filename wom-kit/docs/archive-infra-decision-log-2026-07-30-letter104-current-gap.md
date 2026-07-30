# Decision Log — Letter 104 Remains An Active Backlog

Date: 2026-07-30

## Context

Letter 104 combined five unfinished relationship/source requests with runtime
version skew, base-type adoption safety, event-anchor prerequisites, and AI
command-routing failures. Later releases addressed several prerequisites, but
the letter had not been reconciled as a whole.

## Decision

Do not mark Letter 104 resolved.

- Credit v0.3.278, v0.3.279, and v0.3.287 for command routing, unmanaged inbox
  detection, and occurrence-alignment evidence.
- Describe v0.3.291 runtime alignment as partial: it provides honest diagnosis
  and a read-only version bridge, not global tool installation or a general
  write-command bridge.
- Keep weekly relationship judgment, `sequence`, non-event Principal
  registration, source URL restoration, recurrence, selective base-type
  adoption/revert, existing-archive guidance adoption, and unmanaged objet
  duplicate detection open.
- Preserve the v0.3.292 through v0.3.299 Letter 105 order. Begin the remaining
  Letter 104 work after that train, starting with installed-tool provenance
  and safe runtime alignment.

## Consequences

- Release notes must not claim that v0.3.291 fixes the beta tester's global
  write-command skew.
- The five immediate questions have direct, evidence-backed answers, but those
  answers do not substitute for missing writers or recovery lifecycles.
- Relationship activation and mutation features remain separate, small
  releases with independent plan/write/revert/recovery review.
- Existing beta archives are never silently rewritten to adopt new agent
  guidance.

Detailed reconciliation is recorded in
`meeting-minutes/2026-07-30-letter104-current-gap-reconciliation.md`.
