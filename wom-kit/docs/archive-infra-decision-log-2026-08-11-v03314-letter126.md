# v0.3.314 Letter 126: bounded long operations and inspectable generated index

## Context

Letter 126 showed two real operational failures after a successful v0.3.313
upgrade: project update materialization spawned thousands of Git processes, and
an ordinary generated-index rebuild could never pass private-projection health
after its final WAL connection closed. A blocked nested private state also
produced no top-level blocker or repair command.

## Decisions

- Materialize Git blobs with a bounded persistent batch protocol. Per-path Git
  subprocess fan-out is not an acceptable Windows implementation.
- Persist the disposable generated SQLite index in rollback `DELETE` mode for
  both rebuilds and incremental writers. Health uses true read-only mode and
  must not create WAL/SHM/journal sidecars. Normal reads accept only a valid
  `1/1` header with no sidecars; legacy WAL and recovery residue block before
  SQLite opens or live zettels are enumerated, and no public row comparison is
  claimed in that state.
  Descriptor/fstat identity checks narrow same-path replacement, while the
  operator still must quiesce unmanaged external SQLite writers because this is
  not an OS-wide lock.
- A valid private authority plus unavailable generated projection is repaired by
  the ordinary combined `archive index` rebuild. It is not a reason to invent a
  second authority writer.
- A nested blocked private state must have a fixed top-level blocker and
  command-shaped recovery actions.
- Long-command observability uses one content-free CLI operation-control
  contract. Status and bounded wait are read-only. This release reports
  `cancel_supported: false` with fixed `operation_cancel_not_supported`; it does
  not implement a cooperative cancellation request. Recovery planning never
  deletes locks. True forward resume is not implemented and must be reported as
  unsupported.

## Consequences

Existing generated indexes require one explicit rebuild after installing the
fixed version. The generated database schema and private durable authority do
not migrate, and no new authority approval is required for rebuilding this
disposable projection. Existing-path incremental writers fail closed instead of
performing that conversion implicitly. WAL concurrency wording is superseded
for this generated cache in favor of no-write read-only health and consistent
inspectability. No provider, network, model, credential, MCP writer, daemon,
queue, or real-archive mutation is added.

## Supersedes

This decision supersedes the generated-cache WAL persistence/concurrency wording
introduced before v0.3.314 and the v0.3.297 test contract that treated an
artificially anchored WAL/SHM pair as a successful C10 read. It preserves the
strict private `mode=ro` rule and does not add an immutable fallback to public
health.

See
`meeting-minutes/2026-08-11-v03314-letter126-long-operation-and-private-index-recovery.md`
for the field evidence and implementation chronology.
