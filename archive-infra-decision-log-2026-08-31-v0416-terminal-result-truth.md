# Decision log: v0.4.16 terminal result truth

## Decision

Treat an authenticated project-update result and its later control-resource
cleanup as separate truths.

Before unlock and exact cleanup, publish a durable privacy-safe terminal
handoff bound to the succeeded approval claim, completed checkpoint, approved
plan and target, and verified domain postimage. A later process may replay the
result only after independently reauthorizing all of those bindings and proving
lock absence. Cleanup proof alone is never authority.

Publish and finish the handoff through atomic same-directory transitions:
`active` -> `display-pending` -> hash-named `consumed`. Bind the immutable
output and exactly one immutable terminal journal record to the handoff with a
derived one-use delivery proof; never serialize the raw delivery capability.
Do not append a later delivery- or display-committed journal event. Once bound,
resume must reject replacement output and reuse the exact original bytes. A
stop while display is pending may cause the identical result to be shown again;
this is at-least-once display, never writer replay. Consumed state is history,
not a replay candidate. `durable_result_delivery_acknowledged` proves the
authenticated durable output handoff, not human or model observation of stdout.

Classify legacy cleanup residue without turning shape into authority. Restore
one complete tombstone only after exact plan, full tree, terminal checkpoint,
succeeded claim, current postimage, and legacy cleanup-authority validation.
Treat a canonical proof-only artifact as inert history: report
`no_resumable_project_update`, attribute no past success, verify no current
project state, and require a fresh preview and approval for any new update.
Keep partial, malformed, mixed, changing, ambiguous, or unsafe residue as
`terminal_cleanup_outcome_unknown` and fail closed.

## Context

A terminal cleanup failure could occur after every project component, receipt,
claim, and lock transition had succeeded. The finalizer exception then replaced
the already-authenticated success result with a generic command failure. The
same risk existed when the trusted Git runner closed, and a hard exit after
cleanup left no authenticated result for the next process.

## Consequences

- Fresh approval and resume share one terminal-result and resource-close path.
- Cleanup or runner-close uncertainty is reported as follow-up control
  attention; it does not rewrite verified domain success.
- Both independent closes are attempted. Neither a close failure nor terminal
  display failure may mask the primary exception or authenticated result.
- Windows retains authority after a failed `CloseHandle`; POSIX consumes local
  descriptor ownership on the first close attempt and never retries a possibly
  reassigned descriptor number.
- A hard exit after terminal publication can be recovered without another
  writer or native approval.
- Terminal display is at-least-once. The identical result may appear twice
  around a crash, but a new or changed result may not be generated.
- The immutable terminal journal remains authoritative for its original event;
  read-only status derives later delivery truth from the exact bound output and
  handoff namespace rather than rewriting history.
- Complete legacy tombstones are recoverable only through exact validation;
  proof-only history never claims old success, and incomplete residue never
  becomes fresh-write authority.
- Forged, ambiguous, stale, or claimless handoffs remain fail closed.
- Terminal domain results are recursively privacy-projected before signing.
  Private locator keys, identifiers embedded in values or dynamic keys,
  private scratch roots, and absolute local paths never enter the replayable
  result; redacted-key collisions fail closed.
- Runtime binding accepts the exact `python -m` `__main__` identity while
  retaining receipt, byte, path, and real-component checks.
- A false same-version binding observation is fixed without rewriting the
  runtime. A genuinely invalid same-version runtime is repaired by the existing
  approved updater: seal the old identity and inventory, atomically move it
  into the private transaction as an exact private recovery preimage,
  atomically promote a fully verified candidate, resume each exact crash state,
  preserve the lock, new runtime, and recovery preimage across later
  durable-component failures for authenticated
  checkpoint-forward resume, and clean the preimage only after authenticated
  terminal handoff. Historical pre-handoff and separately authorized rollback
  behavior remain distinct from this durable forward-resume contract.
- Only create-only append-only incident-body preservation crosses a runtime
  mismatch; ordinary writers remain blocked.
- Product vocabulary is not treated as a secret, while high-confidence values
  and headers remain blocked without echo.
- Terminal privacy projection is semantic as well as lexical. Canonical private
  bindings are validated before redaction, private-root-bearing arbitrary text
  is redacted as a whole, and public route exceptions apply only to exact
  top-level route fields rather than to look-alike path or sequence values.

Long-form evidence and verification status are recorded in
`meeting-minutes/2026-08-31-v0416-runtime-result-recovery.md`.

## Amendment: bind namespace authority, not checked pathnames

No-replace publication, state transition, or cleanup may rely on a parent or
entry that was checked only before a later pathname mutation. Hold the exact
source and destination parents across the namespace operation and address
entries relative to those authorities where the platform permits it. Cleanup
must delete only an exact retained object; if exact compare-and-delete cannot be
proved, preserve the evidence and fail closed.

Initial terminal publication uses one deterministic, content-bound stage.
Interrupted partial bytes are preserved under a deterministic
identity-and-content-bound residue and a fresh stage is attempted; no cleanup
path deletes an unknown staging occupant. An exact complete stage is resumable
without a second domain write or approval. These invariants are release gates,
not optional cleanup hardening.

## Amendment: platform and legacy cleanup authority

In v0.4.16, approved project-update mutation, same-version repair, and any
resume that can mutate are Windows-only. POSIX supports preview and read-only
inspection and otherwise fails before creating any transaction artifact. This
zero-write boundary is preferable to shipping a pathname-based mutation model
whose retained namespace authority cannot yet be proved across every step.

Windows mutation holds the exact root and guard handles and verifies volume,
inode, creation time where applicable, regular-file type, non-reparse state,
single-link state, and the absence of alternate streams. Cleanup may delete
only through retained handles after the same identity is revalidated.

The predecessor `cleanup-plan.json` format is historical evidence, not delete
authority. A complete predecessor tombstone must be restored and authenticated
through the ordinary transaction, succeeded claim, plan, checkpoint, and
postimage rules; only then may recovery issue the current
`cleanup-plan-v0416.json` sidecar that binds root device, inode, and Windows
creation time. Partial or ambiguous legacy residue remains preserved and fails
closed.

## Amendment: remote CI is a release feedback loop

The first PR #92 CI run is a blocked candidate, not a partial release. Passing
readiness and scale gates do not override failed platform shards. Contract tests
may be updated only where they assert a superseded interface or platform scope;
the v0.4.16 Windows authority checks and POSIX zero-write boundary may not be
weakened to make old fixtures pass. Every correction requires focused Windows
evidence, an independent Linux selection where relevant, and then a completely
new remote matrix before merge.

Platform skips apply only to tests that execute Windows-only mutation. Tests
that mock the mutation boundary and verify routing, approval exclusion,
no-write behavior, or progress timing remain cross-platform.

## Amendment: synthetic credentials are still forbidden public source

A complete provider credential shape must never be checked into public source,
including tests, examples, and fixtures. Tests may assemble a deterministic
shape only at runtime, while the public privacy gate scans every tracked public
file, including test paths, and reports a content-free reason code without the
candidate or a recoverable tail.

Any GitHub secret-scanning alert blocks CI completion, merge, tag, and release.
For an unmerged feature branch, remove the shape from the final tree and replace
the branch history from a clean main base before resolving a proven test fixture
as `used_in_tests`. An unknown-origin value would instead require provider
revocation or rotation before any history decision.
