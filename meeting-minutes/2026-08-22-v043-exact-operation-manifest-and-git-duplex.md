# Meeting Minutes: v0.4.3 Exact Operation Core and Git Duplex Repair

Date: 2026-08-22
Status: implementation complete in isolated candidate branch; release and
domain integration not claimed

## Direction and boundaries

The v0.4.3 work was split so the common operation core and the Git pipe defect
could be completed independently of domain recovery writers. Work remained in
the dedicated `codex/v043-core` worktree. The protected beta archive and all
other worktrees were left unchanged.

The implementation was directed to avoid another approval subsystem. The
existing exact-human approval, operation binding, and one-use workflow remain
the only authority path. The new manifest supplies only domain-neutral digest,
checkpoint, field-receipt, resume, revert, verification, and progress
mechanics.

An architecture review corrected two initial risks:

- whole-file hashes cannot be the restore authority for a field-scoped revert,
  because a later legitimate change to an unrelated field would block the
  restore;
- an unthrottled heartbeat from every adapter callback would create tens of
  thousands of status events on an 8,569-item operation.

The final implementation therefore binds stable target identity plus exact
field hashes and throttles cooperative heartbeats with a monotonic clock.

A later completeness review found three shared lifecycle gaps: domains would
otherwise reinvent durable checkpoint storage and locking; a process stopping
after its last item checkpoint had no durable final receipt; and `resume=True`
alone did not prove that the original one-use human approval was still the
authority. The common core now owns one fixed archive-wide OS lock, private
fsynced JSONL checkpoints, content-free create-or-match final receipts, and an
approval binding carried by the execution and first checkpoint. The existing
exact-human claim core can reauthenticate only the same `started` claim and
byte-identical context without opening another dialog.

Review also rejected a public generic resume function because arbitrary
`checkpoint_guard=True` and writer callbacks could reuse a started claim as a
general capability. The callback orchestration remains underscore-only;
production integrations must be operation-specific and non-injectable.

## Implemented files

- `wom-kit/src/wom_kit/exact_operation_manifest.py`
  - strict manifest construction and parsing;
  - target/source/effect/manifest digests;
  - full preflight, per-field compare-and-swap, independent readback;
  - hash-chained item checkpoints and field receipts;
  - explicit resume after write-before-receipt interruption;
  - selected-field revert and independent verification;
  - immediate first status and ten-second cooperative heartbeat contract;
  - fixed local writer lock, durable strict checkpoint store, and content-free
    final receipt;
  - exact-human approval-reference binding in the execution and checkpoints.
- `wom-kit/src/wom_kit/exact_human_approval.py`
  - private authenticated rehydration of the same `started` claim only.
- `wom-kit/src/wom_kit/exact_human_approval_workflow.py`
  - private resume orchestration with an exact-checkpoint guard and no native
    prompt or new key creation;
  - terminal, tampered, context-drifted, and missing-checkpoint rejection;
  - no public generic resume writer-injection surface.
- `wom-kit/src/wom_kit/operation_approval_binding.py`
  - adapter from a verified manifest to the existing native approval binding;
  - operation and archive-identity match checks;
  - content-free warning-set and review-code binding.
- `wom-kit/src/wom_kit/archive_services.py`
  - concurrent bounded stdin writer and stdout reader;
  - timeout begins before pipe workers and also covers child exit;
  - overflow, broken-pipe, read, timeout, and lingering-worker failures remain
    fixed closed.
- focused tests for the manifest lifecycle and capped Git runner.

No top-level CLI command, MCP tool, approval token, provider call, archive
mutation, Git commit/push writer, version number, tag, or release was added by
this branch.

## Verification feedback loop

The first exact-operation run passed five focused tests. Review then required
the explicit two-second first-status and ten-second heartbeat contract. The
contract was added, and a second review found that an event on every callback
would be inefficient. A fake monotonic clock test now proves suppression before
ten seconds, one event at the boundary, and reset after ordinary progress.

The first 6,501-path Git test reached the intended private helper without the
planner's pinned-Git context and failed with `git_executable_not_pinned`. The
test was corrected to establish and reset the same context variable used by
the real planner; no product code was weakened. The corrected large-path test
passed.

Focused evidence was expanded after the lifecycle review. The final targeted
run covered 59 tests:

- exact-operation manifest, apply, resume, field receipt, selected revert,
  preflight, authority-bound checkpoint, fixed lock/store, final receipt,
  tamper, final-receipt evidence, and heartbeat tests: 12 passed;
- duplex runner, 6,501-path Git attribute probe, and version/source-match call
  path tests: 3 passed;
- existing exact-human approval suite: 11 passed;
- exact-human workflow, same-started-claim rehydration, terminal/tamper/context
  drift rejection, checkpoint guard, and no-public-generic-resume tests:
  10 passed;
- existing Letter 139 Git planner suite: 15 passed;
- existing operation approval binding suite: 7 passed;
- existing oversized-stdout capped-runner regression: 1 passed.

All changed Python modules and tests passed `py_compile`; `git diff --check`
reported no content error (only the checkout's existing LF-to-CRLF warning for
one test file).

The version/source-path regression verifies that both version tag inspection
and project source snapshot matching call the corrected common capped runner.
It does not claim that the protected archive's previously interrupted live
version command was rerun; this branch uses synthetic repositories only.

## Remaining integration

Each Letter 138/141/142 domain writer must still provide its stable target
identity, exact field encoding, source acquisition, and operation-specific
non-injectable approval wrapper. It must use the common lock/store and convert
the live claim reference into `ExactOperationApprovalAuthority`; the common
module deliberately does not guess those domain-specific policies.
