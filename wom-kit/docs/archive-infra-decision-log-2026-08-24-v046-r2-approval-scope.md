# Decision Log: v0.4.6 R2 Approval Scope and Client Boundary

Date: 2026-08-24

## Decision

- Reopen approval only when exactly one existing command flag selects
  `--preserve-local-only` or `--formal-adoption`.
- Keep no-mode, dual-mode, and legacy adopt approval fixed closed with
  `compound_exact_human_approval_binding_required`.
- Publish this conditional scope in the parser-derived capability inventory;
  a top-level `approval_available` label without the flag boundary is not
  sufficiently honest.
- Keep technical verification machine-owned. The person chooses only the
  operation-specific action or cancel.
- Treat code, tests, a release, and installation as preparation evidence, not
  proof of client application. Provider and client-archive writes require the
  client to execute the released project runtime or explicitly delegate the
  exact operation.

## Consequences

The existing command family remains small while its authority is precise.
Emergency byte preservation cannot silently become formal adoption, conflict
review cannot become auto-merge, and development work cannot be reported as a
completed client mutation.
