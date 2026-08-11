# v0.3.316 complete collision-set inspection and cache repair

Date: 2026-08-12

## Context

v0.3.315 could stop an unsafe project update and return opaque collision
references. In a reported 25-entry Python runtime-cache case, however, the
operator had to inspect every reference separately and still received no
official remediation. A detector that leaves the supported recovery path
unreachable is not a complete update experience.

## Decision

1. Keep the no-UI, AI-host-operated v0.3.x product direction. The important UX
   is a short, explicit, machine-readable workflow that Codex or Claude can
   follow without guessing private paths.
2. Add `project-version-update-collision --action inspect-all`. It must inspect
   the complete opaque set from one unchanged materialization plan and expose
   evaluated kind/remediation truth without private names or content.
3. Offer `project_bytecode_repair` only when the complete collision set exactly
   equals a supported set of ignored derived bytecode files and plain cache
   directories. Counts are informational, not authority.
4. Bind the separate repair plan and approval to the updater target,
   `materialization_plan_sha256`, exact internal path set, stable file identity,
   and repair-plan digest. Refuse mixed, unignored, tracked, linked, reparse,
   special, changed, oversized, or incomplete sets.
5. Share the updater's exclusive project lock, require attributed review and
   external-writer quiescence, and retain truthful intent/completion evidence
   for partial or uncertain outcomes.
6. Never combine repair approval with update approval. After repair, require a
   fresh updater preview and a separately reviewed update approval.

## Consequences

- The common 25-cache case becomes one inspection plus one separately reviewed
  repair workflow instead of 25 inspections with no next step.
- Unsupported collisions remain explicit
  `inspected_remediation_unavailable`; WOM does not broaden deletion authority
  merely to make an update proceed.
- Cache repair does not fetch a target, modify `HEAD` or a project version pin,
  retry an updater, or prove that a release artifact is installed.
- Implemented source, local tests, merge, CI, tag, GitHub Release, public wheel,
  fresh install, beta-client execution, and human acceptance remain distinct
  evidence layers.
