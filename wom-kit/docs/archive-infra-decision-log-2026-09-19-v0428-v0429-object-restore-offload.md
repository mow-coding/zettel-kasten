# Decision Log — v0.4.28/v0.4.29 Object Restore And Offload

Date: 2026-09-19
Status: accepted (v0.4.28 restore); v0.4.29 offload decisions recorded ahead of implementation

## Context

The 2026-09-04 decision log (decision 6) and the acceptance register rows
OB-01, OB-02 and OB-03 planned the object-storage offload family for v0.4.23:
prove remote bytes with a full authenticated GET, restore verified bytes into
the local objet store, and only then free local disk by an approved offload.
The v0.4.22 through v0.4.27 update-failure and dialog hotfix train pushed the
rows aside without recording a decision; the maintainer and the client had
asked for the feature since the first object-storage uploads. This log records
the design as built for v0.4.28 and the decisions the v0.4.29 offload will
follow, so the slip is a recorded fact and not a silent one.

## Decisions

1. Restore before delete. v0.4.28 ships only OB-01 and OB-03 (`object-storage-restore`
   with `--verify-only`); OB-02 (the offload writer) is v0.4.29 and reuses the
   v0.4.28 receipt, sink and projection machinery. Nothing that removes local
   bytes ships before the way back exists and is client-verified.
2. Remote evidence. A restore source is a WOM-verified `wom_uploaded` location
   for the requested provider and store, or a v0.4.13 `bytes_preserved` /
   `already_remote_verified` preservation receipt for that store (key derived
   from the digest). `declared_uploaded` and `declared_external` claims are
   never sources. The restore GET itself is the decision-6 full digest proof,
   so formally adopted presence-size rows qualify.
3. The only new transport surface is `get_object(key, sink_path, expected_size,
   expected_sha256)`: the sole live egress gains two sink keywords that only
   this primitive passes; every existing HEAD/PUT/multipart/verification GET
   keeps the five-keyword injected-sender contract. The sink is create-only
   (O_EXCL), bounded by the manifest size, fsynced, and discarded on any
   incomplete or mismatching body.
4. Local placement is create-only. A verified sink is re-hashed from disk,
   moved no-replace into `objects/sha256/<2>/<64>`, and the destination is
   re-hashed. An existing local file that reproduces the object id is
   `already_present_verified` without a download; one that does not is a
   `local_conflict` that is never overwritten. The remote object is never
   deleted: `delete_object` is unreachable from the restore module.
5. Per-object outcome, batch projection. Each object ends as one immutable
   receipt (`bytes_restored`, `already_present_verified`, `remote_verified`,
   `review_required` with a fixed reason); a corrupt or absent remote copy
   never blocks the other objects. One final manifest projection adds or
   reactivates the local location only for restored objects, under the
   manifest index mutation lease, resumed like formal adoption. A transport
   failure leaves the item unfinished and resumable; a finished object is
   never downloaded twice.
6. Always-dialog. `object_storage_bytes_restore` joins the always-dialog set:
   it reads a provider credential and writes canonical bytes, so a session
   permission mode can never skip its dialog. The count-first target list
   shows the objet identities only.
7. Broker meaning for OB-01. The existing object-storage credential path
   (env/keyring/credential-manager refs resolved lazily inside the approved
   write through one shared live-transport factory) satisfies "existing
   transports use the broker"; the scoped Windows credential broker of
   decision 5 remains NP-01 work and is not widened here.
8. Idle timeout. The live sender applies a 120 s per-operation socket idle
   timeout to every object-storage call so a silent socket becomes a
   retryable transport error; a slow but progressing transfer is never cut.
9. Offload state (v0.4.29, decided now so v0.4.28 already reads it). An
   offloaded object keeps its manifest row and its local location with
   `availability: offloaded`, `offload_receipt_ref` and `offloaded_at`; the
   location is never removed. v0.4.28 restore flips it back to `available`.
   Doctor reports an offloaded location as an INFO-level recovery dependency
   (never `local_object_missing`, never a strict failure), backup-evidence
   counts remote-only objects, staged-cleanup-check treats an offloaded
   object as `deferred` (cleanup stays unsafe until restore), and
   `resolve-objet-ref` names the restore workflow.
10. Retention predicates (v0.4.29). An object is offload-eligible only when
    its remote proof is fresh (a full GET in the same run), it is referenced by
    no unminted draft, it is not the fidelity source of a pending intake, its
    local bytes re-hash to the object id, its path chain has no reparse point,
    and the operator's explicit size/age filters select it. Defaults stay
    conservative and every exclusion is counted in the plan.

## Amendment 2026-09-19 (after the v0.4.29 implementation review)

- Decision 3 said v0.4.29 needs no further approval-kind change; that was
  wrong: a deletion must not show the restore dialog copy. v0.4.29 adds the
  always-dialog kind `object_storage_bytes_offload` ("오브제 로컬 바이트 비우기").
- Offload sources are WOM-verified `wom_uploaded` manifest locations only;
  a v0.4.13 preservation receipt alone stays restorable but never offloadable,
  because the row must carry the remote proof every reader keys on after the
  local bytes are gone. Only capture-provenance objects
  (`b4_local_objet_capture`, `tiro_lossless_recovery_bundle_capture`) are
  candidates; snapshot and provider-recovery objects stay local.
- The offload proof is the existing remote-query adapter (HEAD then the full
  GET re-hash), not a sink download: no local copy is written, no disk is
  doubled. The proof marker is bound to the approved execution
  (`<manifest16>/<execution16>/`), written atomically, honoured only for a
  byte-identical file identity, and discarded when torn or foreign.
- Removal uses the handle-bound compare-and-delete primitive, which the
  codebase keeps Windows-only by design (POSIX never mutates); a plan is
  inspectable everywhere and approval is refused elsewhere with
  `object_storage_offload_platform_unsupported`.
- Bytes a capture re-materialises before the projection keep their row
  `available` and are counted; the window between a per-object removal and
  the final projection is reported truthfully by Doctor and closed by resume.

## Consequences

- The client can bring deleted or offloaded originals back with one dialog
  and see, per object, whether the remote copy is intact.
- `--verify-only` gives the first complete "are my uploads really there"
  proof across a store; it costs a full download per object, so `--only` and
  `--max-objects` bound it.
- v0.4.29 can implement the offload writer without another transport or
  approval-kind change: the state, receipts and reporting are decided here.
- The OB rows carry "slipped from v0.4.23" so the register stays honest about
  the delay.
