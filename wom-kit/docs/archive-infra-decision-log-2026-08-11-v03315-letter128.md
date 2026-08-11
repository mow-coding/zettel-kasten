# v0.3.315 paired Objet batch capture and derived-text recovery

Date: 2026-08-11

## Context

The bounded multi-item adapter accepted reviewed rows that paired an original
with derived text, but it converted those rows into original-only selection
items. The mature lower capture engine already supported the pair. The adapter
therefore could finish original capture while silently omitting the reviewed
derived half and reporting a misleading batch completion surface.

## Decisions

1. The request remains schema v0.1 for compatibility, but paired fields are
   closed-shape and dependency-checked. `model` is a legacy spelling for
   `model_name`; providing both is a conflict, not an overwrite rule.
2. The batch plan binds the exact reviewed request and exact generated
   selection. Apply must pass that selection document directly to the lower
   engine and accept its result only when archive id, selection id and digest,
   item set, receipt route, item shapes, and exact `files_written` delta all
   match the expected contract.
3. Original and derived work use separate requested, written or ready,
   skipped, and blocked partitions. Every requested item must appear in exactly
   one terminal partition before completion is true.
4. Request, staged original, and staged derived reads are regular-file,
   no-follow, stable, and bounded. The request and each derived source have a
   64 MiB ceiling; any identity or size change fails closed.
5. Batch receipts bind `request_sha256`, `selection_sha256`, `plan_sha256`, and
   an attempt-specific `attempt_sha256`. Older valid v0.1 receipts remain
   readable because the new attempt and partition fields are additive.
6. Publication observation is tri-state: `verified_exact`, `not_written`, or
   `ambiguous`. This is distinct from result states `partial`,
   `evidence_incomplete`, and `recovery_required` and from the blocker code
   `batch_capture_outcome_unverified`. A possible durable write followed by an
   exception never becomes a guessed zero-write result; it returns
   state-specific safe next actions.
7. Replay remains bounded per item, not atomic batch rollback. The same request
   may skip exact existing originals and finish the paired derived half. If
   original staging is unavailable, a separately reviewed
   `derive-text capture --from-manifest` request may use object ids from durable
   original capture receipts instead of recopying originals.

## Consequences

The public CLI reports actual original and derived outcome partitions, not
plan-time counts. It never echoes manifest values, staged paths, titles, file
bodies, or raw exceptions. `batch_capture_outcome_unverified` is a stop signal,
not permission to replay automatically. A batch receipt is evidence for one
attempt and one exact selection; it is not a claim that the whole batch was
atomic or that absent staging bytes can be reconstructed from hashes.
