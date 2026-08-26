# Decision Log — v0.4.8 Integrity Recovery

Date: 2026-08-26
Status: accepted for v0.4.8

## Context

Several recovery paths already had exact plans and native human approval, but
an interrupted run, incomplete historical evidence, or a mixed manifest could
still leave too much technical reconstruction to the operator. Public release
work also must remain separate from any client execution.

## Decisions

1. **WOM owns technical verification.** The machine computes populations,
   hashes, source bindings, drift, and safe effects. The ordinary human choice
   is only the plainly described operation or cancel.
2. **Interrupted exact work is recoverable from durable evidence.** A command
   may auto-discover one unambiguous authenticated control for resume or revert.
   Missing, corrupt, or ambiguous controls stop the operation. Reverting an
   unfinished field recovery durably supersedes its parent apply so the old
   resume path cannot run afterward.
3. **Recovery changes only proven fields.** Title repair uses the paired source
   index, omission-marker repair changes only the marker token, and unrelated
   body drift blocks automatic mutation.
4. **Sidecar evidence is bounded and stable.** Oversized, linked, reparse-point,
   changing, or non-regular files are not trusted as recovery evidence.
   Occurrence anchors remain diagnostic-only until a verified occurrence-
   recovery receipt contract exists.
5. **Existing evidence is reused without inventing authority.** A capture
   selection may be created only from a canonical existing intake record, and
   local object-storage registration records local metadata only. Neither step
   performs capture, reads credentials, or contacts a provider.
6. **Strict duplicate reconciliation is lossless and reversible.** Only a
   narrowly proven canonical-local plus external-prehashed pair may collapse to
   one canonical row. Both original definitions and provenance remain bound in
   private evidence, and an exact whole-manifest revert is available. An
   unambiguous interrupted source journal is also revertible after WOM
   revalidates the original approval. WOM preserves that source journal and
   records separate authenticated terminal-compensation evidence that blocks
   forward replay. A `finalization_pending` revert resumes with the same
   reviewer label and the existing authenticated claim, never a second native
   approval. A `started` claim resumes the writer idempotently; a `succeeded`
   claim runs only the finalizer, with no second manifest write. An initial
   unknown-state stop returns one fixed content-free same-reviewer resume
   action instead of making the operator reconstruct technical state.
7. **Release and client execution remain separate.** Source validation,
   packaging, publication, and installation do not modify a client archive.
   Client recovery requires an explicit project-scoped run and its own durable
   verification evidence.

## Consequences

- Ambiguous evidence remains an explicit review state instead of being merged
  or rewritten automatically.
- Public documentation and release artifacts expose only content-free behavior
  and capability facts.
- The existing command families and `ExactOperationManifest v1` remain the
  shared surface; no extra top-level command is introduced for these repairs.
