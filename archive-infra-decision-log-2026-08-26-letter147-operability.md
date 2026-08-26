# Decision: Letter 147 operability is a bounded v0.4.9 release

Date: 2026-08-26

## Context

Letter 147 confirmed that v0.4.8 repaired important data integrity paths but
left three ordinary operating failures: a new file could not enter the exact
single-file capture chain, doctor could stay silent and return findings from a
changed object manifest, and object-storage setup advertised an optional or
unsupported interface.

The development repository and the client archive have separate authority.
The release may implement and prove a recovery path against synthetic and
installed-wheel fixtures. It must not install itself into, or write recovery
results into, the named client archive.

## Decision

- Open `source-intake-record` only through a create-only
  `ExactOperationManifest` writer. Keep the legacy service approval entrypoint
  closed so callers cannot bypass native approval, checkpoints, read-back, or
  input re-derivation.
- Treat one ordinary file as three separately approved effects: intake
  evidence, capture selection, and byte capture. Prove the whole chain from the
  installed wheel without manually manufacturing the first receipt.
- Bind object-manifest doctor findings to the exact bytes parsed by that stage,
  revalidate the manifest at completion, and fail the result as stale or
  unverified when it changed or could not be re-read.
- Resolve each doctor suggested command against the installed parser and report
  the requested mode separately from the command's broader approval status.
- Make doctor progress visible by default with a bounded heartbeat and retain a
  deliberate opt-out. Progress logs are create-only and must live outside the
  inspected archive; the writer retains the exclusively-created handle so a
  later path replacement cannot redirect events.
- Make doctor diagnostic output create-only inside the archive. Existing files,
  the inspected manifest, and hardlink aliases are rejected before publication.
- Re-derive approved intake effects from current exact bytes. Matching receipt
  bytes that lack authenticated completion evidence remain an explicit
  completion-evidence-required state instead of an approval-free success.
- Make `object-storage --profile-id` visibly required. Explain how to resolve
  the id. Hide the unsupported legacy local-profile flag while still rejecting
  old invocations before any archive read or write.

## Consequences

This release does not reopen source-intake batch, object capture batch, or the
other high-risk fixed-closed writers. It also does not claim that doctor's
whole-archive performance problem is solved merely because heartbeat and stale
input detection are improved. Those remain explicit follow-up work.

The public release contains only bounded contracts, synthetic fixtures, and
redacted counts. Client paths, archive payloads, credentials, and private
feedback text stay outside it. Publishing or installing the release performs
no client-archive recovery operation.
