# Archive infrastructure decision log — 2026-09-20, v0.4.33 (beta letter 164 ①③④: upload reopened)

Executing model: Claude Opus 5 (design v1, implementation, tests, docs),
solo and sequential, under the user's standing approval to work through the
backlog. The first design was refuted by a bounded read-only Ultracode
review (8 agents, `wf_a8b80ac3-001`, 2026-09-20 03:00–03:20 KST); the
corrected design below is what was implemented. No client archive, runtime,
workspace or ledger was read or changed; every fixture is synthetic.

## What the review established

1. The v0.4 line already contained an exact-approval live PUT writer:
   `object_storage_preservation.py` (v0.4.13, reached through
   `object-storage-adopt-existing --preserve-local-only`). It has the
   create-only PUT, the whole-object GET re-hash before and after, the
   manifest-bound provider-call budget with write-ahead reservations, the
   private ledger whose terminal row precedes anything public, and the fixed
   `review_required` outcome. Its only differences from what the client needs
   are the remote key prefix (`wom-bytes-preserved/v1/…`) and the deliberate
   absence of a `wom_uploaded` manifest location.
2. The batch `wom_uploaded` projection already exists in formal adoption
   (`object_storage_adoption.py`): one compare-and-swap rewrite under the
   manifest-index authority. The v0.3 per-object rewrite
   (`_object_storage_apply_wom_uploaded_location`) bypasses that authority and
   leaves the generated index stale; it must not be reused.
3. A `wom_uploaded` location's `execution_receipt_ref` must be a
   `receipts/providers/object-storage-executions/*.object-storage-upload.json`
   file with the v0.3 receipt fields, or the gating matcher, backup-evidence
   and Doctor reject the location.
4. The SA-6 tiered gate cannot be satisfied by a create-only writer (its
   ladder needed a forced re-PUT or a ≥ 5 GiB multipart proof); preservation
   itself has no tier gate.
5. `--local-bytes-only` as first drafted was a no-op (no planner ever calls
   the provider); the flag needed a real meaning.

## Decisions

1. **Upload = preservation PUT + adoption projection under one dialog.** New
   module `object_storage_upload_exact.py` composes preservation's executor
   primitives (`ObjectStorageRemoteQueryAdapter`, the journaled create-only
   transport, `_ManifestBoundPreservationLedger`, `_hash_plain_file`,
   `_read_manifest_groups`, `_inventory`) with restore's manifest-index
   helpers and adoption's location builder. The remote key is the v0.3
   content-addressed `sha256/<2>/<digest>`, so v0.3 objects, restore, offload
   and the gating matcher share one layout. The private ledger keeps its
   preservation format (its `operation` field names the ledger family; the
   manifest digest names the operation).
2. **Operation** `object_storage_bytes_upload` — always a dialog, never
   grantable to a session permission mode; Korean copy: label
   `오브제 로컬 바이트 올리기`, question ending in `까요?`, summary stating no
   overwrite / review on differing bytes / no remote delete, button
   `바이트 올리기`. Approval-context warnings:
   `existing_remote_copy_is_never_overwritten`,
   `remote_object_is_never_deleted`,
   `review_required_objects_get_no_manifest_location`.
3. **Reopen mechanics.** `object-storage-upload` leaves
   `COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS` and joins
   `EXACT_APPROVAL_REOPENED_WRITERS`; the CLI handler's `--approve` refusal is
   removed; the legacy service function `object_storage_upload_run` keeps its
   first-line compound refusal for direct callers (its non-boolean guard row
   stays pinned). The v0.3 flags `--force-reupload`, `--skip-uploaded`,
   `--key-strategy`, `--key-prefix`, `--key-append-extension`,
   `--multipart-threshold`, `--multipart-part-size`, `--allow-tiny-parts` are
   removed (content-addressed layout only; a reviewed re-PUT is a carried
   item); `--local-bytes-only`, `--progress`, `--expected-manifest-sha256`,
   `--resume-approval-id`, `--resume-execution-sha256` are added; the two
   aliases stay.
4. **Planner order (③).** The writer line comes first and the manifest is not
   read when it is `unavailable` (`provider_unsupported` for kinds without a
   live transport, `store_ref_invalid`, `store_setup_missing`,
   `store_setup_mismatch`); then one manifest scan; then one classification
   per unique object in a fixed order with a count per class: conflicting
   definition → byte-external (`external_prehashed` / `declared_external`) →
   already uploaded (verified or official `wom_uploaded` evidence) → already
   emergency-preserved (a `bytes_preserved` receipt; the next step is formal
   adoption) → offloaded → local absent → local size conflict → ambiguous local
   paths → filtered (`--only`, `--max-objects` bounds the candidates instead of
   refusing) → candidates, which are hashed. `provider_calls_in_plan` is a
   fixed `0`.
5. **`--local-bytes-only`.** Without it a manifest row that claims local bytes
   which are absent or the wrong size refuses the plan with the blocker
   `local_bytes_missing` (fail closed, as the v0.3 approve loop and restore's
   `local_conflict`); with it those rows are counted and the plan is built
   from the rows that have bytes. Offloaded and byte-external rows are
   excluded in both modes.
6. **No tier gate.** The approved manifest, the plan-time provider-call
   ceiling, the per-object same-run full-GET proof, `review_required` and
   `--only` / `--max-objects` are the v0.4 safety model, as in preservation.
   `object_storage_proven_tier` stays untouched for the legacy function and
   formal adoption.
7. **Per-object spine, no markers.** local re-hash → ledger terminal row
   present? (re-query, return) → before-query: `verified_match` →
   `skipped_remote_same`; size / checksum mismatch → terminal
   `review_required` (never PUT, never overwrite, no location); absent →
   journaled create-only PUT → full-GET re-hash → `ledger.append_terminal`.
   Every transport failure is nonterminal (no receipt, resumable).
8. **Receipts after the projection.** The trailing manifest item (target
   `objects/manifests/files.jsonl#upload-local-location-batch`) runs one CAS
   rewrite adding a `wom_uploaded` location per verified object, writes the
   projection marker, and only then creates the receipts: the v0.3 execution
   receipt fields (`result_status uploaded | skipped_remote_same |
   remote_conflict_different_bytes`, `manifest_update_applied` true only for
   the two success statuses) plus the exact-approval fields
   (`exact_operation_manifest_sha256`, `receipt_state_sha256`,
   `remote_verification.verification_kind: get_rehash_whole_object`,
   provider-call counts). `manifest_update_applied` is therefore never a
   forward claim, and Doctor's success-receipt linkage check never sees a
   success receipt without its location. A crash between the CAS and the
   receipts leaves locations pointing at receipts that a resume creates.
9. **Control document and resume.** The private control document records the
   pre-execution inventory but a resume does not compare the live inventory
   (this writer's own projection changes it); each spec is revalidated row by
   row instead, as restore does.
10. **Session refs move to v0.4.34** together with the coverage targets of
    restore, offload and claim finalize.
11. **Select-all for `git-backup-reconcile-plan`** is deferred to a later unit
    of v0.4.33 or to v0.4.34 (writer-side splitter over the private capture,
    selections directory under the exact-operations root, a warning code
    naming the mode); the existing operator-manifest route is what the reply
    to the client names now.

## Questions for the client (carried in the letter-164 reply)

- The exact `object-storage-upload --dry-run` argv that ran the full compare
  before reporting the closed writer.
- Whether any objets to upload are inbox-only attachments.
