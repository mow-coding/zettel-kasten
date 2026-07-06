# Decision Log - v0.3.177 Force-Reupload Ledger-Only Hardening

Date: 2026-07-06
Batch: v0.3.177.
Anchor: v0.3.176 public release.
Release action: main session release after gates. No real archive write and no real provider call in tests.

## Problem

The basoon v0.3.176 verification letter showed `object-storage-upload --force-reupload` returning
`skipped_already_present` with `put_calls:0`, `part_count:0`, and no execution receipt. That means
the reviewed force run did not exercise a live provider PUT.

Root cause: v0.3.175 bypassed the manifest-level present+match skip, but only set the executor's
`force_upload` flag inside the plan row's `already_uploaded` branch. A post-crash/handoff state
can keep a terminal resume-ledger row while the manifest no longer has a `wom_uploaded` location.
In that state the executor still saw `force_upload=False` and honored the ledger skip.

## Decisions

- **DEC-1 - Force outranks the resume ledger.** When `force_reupload` is active,
  `object_storage_upload_run` now calls `object_storage_execute_one_upload` with
  `force_upload=True` regardless of whether the current plan row is `already_uploaded`.
  Rationale: the operator explicitly requested a live PUT proof; a terminal ledger row is a
  resume authority for default runs, not a veto over reviewed force execution.
- **DEC-2 - Keep the existing integrity gates.** The pre-PUT local
  `sha256(local)==object_id` check still runs before the executor call; if local bytes are
  corrupt, no PUT is attempted. Rationale: force changes sequencing, not integrity.
- **DEC-3 - Expose force in execution output.** Per-object run results now include
  `forced_reupload: true` when the flag is active. Rationale: the client should not need to open
  a receipt to know that this run was a force attempt, and a zero-receipt failure still needs to
  disclose the force context.
- **DEC-4 - Zero PUT is not success for force.** If `force_reupload` is active and a per-object
  result has `put_calls == 0`, add `force_reupload_not_performed` and make the run `ok:false`.
  Rationale: the field failure was not only that the PUT did not happen, but that the command
  reported an apparently successful executed result.
- **DEC-5 - Default idempotency is unchanged.** With the flag absent, ledger resume authority and
  manifest present+match skips behave as before. Rationale: this is a force-only patch.
- **DEC-6 - Tests model the exact hole.** Add a fake-transport regression where the manifest
  `wom_uploaded` location is stripped after a seed upload, leaving the resume ledger behind; a
  forced run must reach multipart PUT. Add a defense-in-depth fake executor test for a forced
  zero-PUT skip. Rationale: the previous tests only covered the manifest `already_uploaded` path.

## Consequences

Operators can retry the 7.8 MiB forced multipart proof after upgrading. A correct result should
show an `uploaded` execution, `forced_reupload:true`, `put_calls > 0`, and `part_count > 1` when
the lowered multipart threshold/part-size flags are used. If a future regression produces
`put_calls:0`, the command fails closed with `force_reupload_not_performed`.

