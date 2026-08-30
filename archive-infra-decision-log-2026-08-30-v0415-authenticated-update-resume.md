# Decision: authenticated, identifier-free interrupted-update resume

## Context

A clean v0.4.14 project can still write Zet drafts. The reported draft failure
occurs when a project-version update is interrupted after only some runtime
components have reached the target version. WOM correctly keeps its durable
update lock and blocks ordinary writers, but the previous resume interface
made the operator reconstruct the target, transaction reference, reviewer, and
an opaque locator. Some of that state could disappear with the interrupted
console. A regression test concealed the gap by reading private recovery state.

Separately, a public wheel installer can omit the installed archive SHA-256 from
distribution metadata. Such an installation cannot safely authorize a project
runtime update merely because its version string and download URL look right.

## Decision

- Keep the durable update lock and global fail-closed project write guard.
- Make the ordinary human resume command contain only the project root,
  `--resume`, and `--affirm-external-writers-quiescent`.
- Reconstruct the target, transaction reference, reviewer, and exact approval
  context from the live durable lock and authenticated private plan. Require
  those sources to describe one coherent operation before discovery proceeds.
- Bind only existing recovery state, authenticate every candidate, require the
  reconstructed exact operation context and durable checkpoint, and proceed
  only when exactly one candidate matches.
- Treat an optional caller-supplied `--approval-id` only as an exact assertion
  after that complete authenticated discovery. It never selects, narrows, or
  directly opens one candidate and therefore cannot bypass ambiguity checks.
- Make discovery non-creating and content-free: no new key, directory, lock, or
  recovery record, and no private identifier, path, or value in output.
- Apply a recursive content-free projection to every successful or claimless
  automatic-resume result. Remove nested approval objects, approval ids,
  transaction references, logical transaction references, and strings or
  paths containing those locators while preserving safe state and evidence
  digests. Report explicitly that those identifiers were not exposed.
- Reuse the existing exact human approval without displaying a second native
  prompt. Do not make a human supply the target, transaction reference,
  reviewer, or internal approval locator.
- Route exact preapproval interruption through the same public command. Cancel
  only an empty locked reservation, a complete sealed preapproval scaffold, or
  a checkpointed scaffold whose authenticated claim count is exactly zero and
  whose domain components remain exact preimages. Return
  `fresh_approval_required` rather than pretending that an update completed.
- Accept a missing live lock only for one sealed, backlinked, exact-journal
  transaction already at the verified unlock tail. Never recreate the lock as
  a read operation and never guess among candidates.
- Bound v0.4.15 automatic outcome recovery to a live exact lock or that exact
  lockless unlock tail while the original transaction directory still exists.
  Once terminal cleanup has renamed that directory, return nonzero
  `terminal_cleanup_outcome_unknown` through a bounded read-only observation;
  do not infer the terminal branch, authorize retry, reopen a writer, or delete
  cleanup-shaped evidence.
- Run the cleanup-unknown observation before output-path preparation and before
  opening the archive identity or approval boundary. If cleanup residue appears
  only after this preflight, report the archive identity metadata read
  truthfully while still distinguishing it from archive domain-content access.
  Emit the first progress state before this bounded observation.
- Defer authenticated terminal-outcome reconstruction to v0.4.16. Its required
  design is a fixed terminal handoff published before unlock, checkpoint-bound,
  and independently reauthorized by the succeeded claim or deterministic
  cancellation evidence.
- Treat malformed or unauthenticated claim-shaped files as invalid evidence,
  not as an empty claim store.
- Remove private recovery inputs from every hard-exit regression boundary.
- While recovery is pending, allow only a new, create-only feedback body and its
  exact body receipt as domain writes. Its bounded cross-process mutex is
  control evidence, not another feedback record and not the project update
  lock. Keep revision, supersession, metadata registration, delivery,
  resolution, draft creation, and all other writers blocked.
- Scope `files_written` in a preapproval-cancellation result to project-domain
  files and return a separate content-free effect summary. That summary must
  disclose no path or identifier while truthfully reporting durable control
  evidence, cancellation checkpoints or reservation-abort evidence, candidate
  cleanup or verified absence, and lock release. Report whether this invocation
  verified a live lock or continued from an exact prior binding with verified
  lock absence; never hard-code live-lock success for a lockless tail.
- Require the bootstrap installation to retain the exact public wheel SHA-256
  in installed metadata. Use a dedicated external CPython 3.12 environment and
  `python.exe -m pip` for the verified bootstrap. Missing or malformed hash
  evidence fails closed.
- Keep developer and client responsibilities separate: developers publish and
  verify code; clients run resume against their own project and return durable
  post-recovery evidence. Development work never edits or deletes a client
  update lock.

## Consequences

- Losing console output no longer strands an eligible live-lock or original
  unlock-tail case or forces inspection of private implementation storage.
  Terminal-cleanup residue remains intentionally nonzero and unsupported in
  v0.4.15.
- The safety property is preserved: ambiguous, forged, stale, or drifted
  recovery state produces zero domain writes.
- Draft creation remains unavailable during a genuinely mixed runtime state,
  then returns only after the update converges and a fresh process verifies the
  aligned project runtime.
- Users can still preserve a new failure report during recovery without WOM
  claiming that the report is registered, delivered, or resolved.
- An empty project-domain `files_written` list can no longer be mistaken for a
  no-effect claim: private control effects remain explicit but content-free.
- Terminal cleanup residue cannot silently grant authority in v0.4.15; the
  unsupported outcome remains visible and nonzero until the v0.4.16 handoff
  contract is implemented.
- Automatic resume output no longer exports the internal locators needed to
  reopen approval or transaction storage, including locators nested in a
  writer result or path string.
- The ordinary cleanup-unknown path does not open `archive.yml`, an approval
  key, a claim store, or cleanup-artifact content. A late race is reported with
  precise metadata-versus-domain access fields instead of a blanket false
  claim.
- Install convenience cannot replace supply-chain evidence; unsupported
  installer metadata receives a safe corrective action instead of a bypass.
- A passing focused suite is not release or client-recovery evidence. Full CI,
  exact wheel release verification, and client-side terminal proof remain
  mandatory.

Longer record:
[meeting-minutes/2026-08-30-v0415-interrupted-project-update-recovery.md](meeting-minutes/2026-08-30-v0415-interrupted-project-update-recovery.md)
