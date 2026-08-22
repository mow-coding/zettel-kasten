# Decision Log: v0.4.3 Exact Operations and Duplex Git Pipes

Date: 2026-08-22

## Context

Recent beta feedback exposed two common failures. Recovery writers were being
designed independently, which risked multiplying commands and approval
systems, while a large NUL-delimited Git request could fill stdin and stdout
pipes in opposite directions and leave the Python parent and Git child waiting
on each other. A separate live observation found the structured version check
waiting in a Python-to-Git process tree, so the correction also had to cover
the shared Git boundary used by version and project-source provenance checks.

## Decision

- Add one domain-neutral `ExactOperationManifest` v1 module rather than new
  top-level commands.
- Bind exact target identity plus field-local pre, post, and source hashes;
  publish only content-free aggregate digests outside the private operation.
- Reuse `ExactOperationApprovalBinding`, `exact_human_approval`, and the
  existing one-use workflow through a narrow manifest adapter. Do not create a
  parallel approval authority.
- Bind the authenticated approval id, context digest, and authority digest to
  the execution and its first checkpoint. Process resume rehydrates only that
  same authenticated `started` claim, without another native prompt; terminal,
  tampered, drifted, missing-checkpoint, and different-claim attempts stop.
- Keep generic resume writer/checkpoint callbacks private. Production domains
  expose only operation-specific, non-injectable wrappers.
- Require a full selected-target preflight before the first write, exact
  per-field compare-and-swap, independent readback, hash-chained item
  checkpoints, field receipts, explicit resume, and final independent
  verification.
- Make revert authority field-scoped. A legitimate later change to an
  unrelated field must not invalidate an otherwise exact selected-field
  restore.
- Emit the first content-free status before injected adapters run. Pass a
  cooperative heartbeat callback into every potentially long adapter and
  throttle heartbeat publication to one event per ten seconds with a monotonic
  clock.
- Hold one fixed archive-wide OS writer lock and append/fsync/strictly reread
  active checkpoints under ignored `profiles/local/exact-operations/` state.
  Publish only a content-free create-or-match final result receipt under
  `receipts/ops/exact-operations/`.
- Change the common capped subprocess runner to drain stdin and stdout on
  concurrent workers, with one timeout covering both pipes and child exit.
  Keep the existing input/output caps and fail-closed error surface.
- Regress the duplex boundary with a 512 KiB echo process, the Letter 139
  attribute path with 6,501 inputs, and the common runner call path used by
  version tag inspection and project source snapshot matching.

## Consequences

Domain writers can share one exact execution and recovery contract without
gaining authority merely by importing it. They still need their own source
acquisition, stable target identity, and operation-specific existing-native-
approval wrapper, while the common module supplies the durable journal, fixed
lock, final receipt, authority binding, and same-claim rehydration primitives.
Project version update may retain its existing single transaction and approval
binding where that is the narrower correct design.

Large bidirectional Git requests no longer depend on pipe-buffer size or on the
platform scheduler draining one side first. Version and project-source checks
continue to use the same capped helper, so the concurrency fix applies there
without adding a new command surface.

## Letter 139 exact Git writer decision

- Extend `git-backup-reconcile-plan`; add no top-level command and no MCP
  writer.
- Require a private exact manifest that classifies every observed change ref
  once and only once into explicit commit groups.
- Bind group source, paths, commit message, initial HEAD, approved HTTPS URL,
  initial remote object id, and target ref through `ExactOperationManifest`.
- Reuse one native approval and the authenticated same-claim resume path.
- Prove exact selected bytes through an isolated index, then use only literal
  `git add -- <paths>` and `git commit --only`; never use `add -A`, reset, or a
  temporary commit that bypasses the user's index.
- Preserve stage entries outside the current group and independently verify
  each created commit.
- Push the exact private URL through existing non-interactive credentials,
  never force, and require an exact remote-ref requery to equal the terminal
  commit. Any remote advance blocks.
- Cap each group's literal Windows path argv at 24 KiB beneath the 32,767
  character platform ceiling. Large selections use multiple complete explicit
  groups; an oversized group blocks before approval.
- Inventory historical receipt metadata once and do not hash every unchanged
  receipt body. Use bounded Git projections instead of recursive archive-wide
  attribute walks, and publish immediate status plus bounded heartbeats.
- Treat an exact staged group, verified commit, or already-matching remote ref
  as resumable evidence only when the authenticated checkpoint and original
  started claim also match. Terminal replay and drift remain closed.
