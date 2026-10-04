# Archive infra decision log: letter 181 (2026-10-04)

Status: implemented for v0.4.61 under the owner's standing instruction
("바로 작업 시작해"); the performance work follows in the next release
(sequential small releases, 2026-09-24).

Letter 181 came from v0.4.60. All 1,070 original items, 28 further items and
95 remote temporaries were cleaned without dialogs, yet the session closeout
still blocked; small cleanups stayed slow; and the customer's agent revised a
letter the person had already delivered.

## A. Closeout evidence for legacy cleanup intents

The closeout (`activity_closeout.evidence`, used by
`session-handoff-checkpoint --cleanup-request`) accepted an item whose intent
has no `alternate_streams` field only with an EMPTY recorded stream
inventory. Intents written by v0.4.38-v0.4.46 have no such field and those
runs recorded no inventory, so the finished request counted 2 of 1,070.
Reproduced with a synthetic archive (4 items: 1 of 4 before).

Evidence that exists for such an item: the signed intent (file state and
object id), the remote preservation receipt (full body bytes verified), the
delete intent and completion records, and the signed `attempt-*` record of
each run, whose items say `deleted` (an actual bound delete) or
`already_absent_after_intent`. With no expected streams the bound delete
refuses any file that carries an alternate data stream
(`legacy_cleanup_bound_delete._reject_windows_alternate_streams`, checked
before and after the delete mark; present since 2026-08-08, before activity
cleanup existed).

Decisions:

1. Per item, the closeout names how the stream state is proven:
   `bound_delete_guard_no_streams` (a `deleted` row in a signed attempt bound
   to this exact intent), `recorded_inventory_empty`,
   `recorded_inventory_with_stream_backup` (rejected before: a bug that
   failed 51 of the customer's items whose streams were preserved),
   `intent_inventory_empty`, `intent_inventory_with_stream_backup`.
2. Anything else is `legacy_stream_state_unknown` (an interrupted run that
   wrote no attempt record, an item absent after its delete intent): counted
   and listed with a plain summary, never assumed empty.
3. The official restore accepts guard-proven legacy items (it refused them as
   `activity_cleanup_restore_stream_inventory_unknown`).
4. When the only remaining gap is that boundary, the handoff names it, and
   after the person agrees `--accept-legacy-stream-boundary` completes the
   closeout as `complete_with_accepted_legacy_stream_boundary`. The acceptance
   is bound into the checkpoint's state digest; the count stays reported and
   is never added to the verified evidence. Nothing is re-executed.

## C. A delivered letter was revised

The person said "전달하고 올게"; the agent kept the record at 전달 전 and
later revised the same letter. WOM cannot know about delivery outside it, so
the record was not wrong; the agent's reading was. Decisions: the operator
guidance says a statement that the letter was or is being delivered counts as
delivered (mark it delivered at once, never revise it, write later
observations as a new letter); the revise preview carries
`delivery_check_before_approval`.

## E. Restoring the delivered text

Restoring the delivered body through revise failed after the approval with
`feedback_body_existing_receipt_conflict`: that exact body's ordinary receipt
already existed from the approval that created it, bound to a different plan.
Decision: an existing receipt that attests exactly the restored body (same
id, body ref, path, size, valid shape) is reused, and the revision receipt
records the new approval; any other existing receipt is still a conflict, now
decided in the preview, before any approval.

## F. A stale claim-finalize plan

While a finalize plan was under review the agent wrote a letter (new
receipts); the approve byte-scanned about 58,000 receipts before reporting a
plan mismatch. The reviewed digest binds the receipt inventory fingerprint,
so once the current complete fingerprint can no longer yield it, no scan can
make it match. Decision: report
`exact_approval_claim_finalize_evidence_changed_since_review` and refuse with
`plan_mismatch` at once, before any scan or claim swap; the CLI approve also
passes the reviewed digest to its first plan, so an unchanged inventory no
longer repeats the byte scan before the dialog.

## Not in this release

B (28 small items took about 26 minutes; 80 remote deletes about 14 minutes;
progress without counts) is investigated at the customer's scale and follows
next.

Executing model: Claude Opus 5.5 (two read-only investigation subagents).
