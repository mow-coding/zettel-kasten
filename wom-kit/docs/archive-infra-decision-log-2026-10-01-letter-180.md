# Archive infra decision log: letter 180 (2026-10-01)

Status: implemented for v0.4.58, v0.4.59 and v0.4.60 under the owner's standing instruction to
finish every implementable item before the reply ("이것도 읽어보고 작업
진행해"). The deeper performance work is split into v0.4.59 (sequential small
releases instead of deferring, 2026-09-24).

Letter 180 came from v0.4.56. A foreground `activity-cleanup --reconcile`
with keychain-rebound refs ran about 61 minutes, deleted 51 of the 53
remaining items and ended `partial` with the same two items as letters 174
and 179 (A and B). operation-control's recovery-plan showed the index-health
text, and the heartbeat thread died with a TypeError.

## Reproduction

Every condition was reproduced on Windows with the real CLI, a synthetic
archive and an in-memory transport (scenarios now in
`tests/test_letter180_activity_cleanup_recovery.py`):

- A: an item's child upload stores the remote bytes, then the process is cut
  before the claim is finalized (claim stays `started`). The next reconcile
  resumed the old child plan, whose preimage no longer matched, and the item
  surfaced only as `exact_human_approval_state_unknown`. The cut after the
  remote PUT and the cut after the receipt both reproduce it.
- B: an item's child offload claim starts, but the process is cut before the
  offload control file is written. A later reconcile tried to rebuild the
  original plan; its manifest binds the whole archive inventory, which the
  other items had changed, so the rebuild could never match
  (`activity_cleanup_child_control_missing_original_not_reconstructable`).
  The customer's "control file absent" state is exactly this.
- Approving the same reconcile a second time (items still pending) conflicted
  with the first approval record before any item ran.

## Decisions

1. The reconcile preview (`--reconcile --dry-run`) adds
   `pending_item_diagnosis`, read-only and content-free: for each unfinished
   item the steps recorded, each child step's control file (present or absent)
   and claim statuses, and the route the approved reconcile takes. No remote
   request is made in the preview (`remote_bytes_checked_now: false`); it is
   not part of the approval binding.
2. A (upload): when the full remote bytes of the object match, the upload's
   effect is complete whatever its claim recorded. The reconcile closes the
   left-started child claim as failed with
   `activity_cleanup_upload_superseded_by_remote_proof` (never as succeeded)
   and continues with the offload.
3. B (offload without a control file): the original plan is not rebuilt.
   - claim succeeded: the item completes after the remote proof;
   - claim started and the local object still holds the exact bytes and its
     manifest location is not offloaded (no effect): the started claim is
     closed with `activity_cleanup_offload_superseded_no_effects` and the
     offload runs again under the new approval, recorded as a new
     create-once control label (`-r<k>`);
   - anything else keeps the file with
     `activity_cleanup_child_control_missing_effects_unproven`.
4. Approving the same reconcile again keeps the first approval record and adds
   the new approval as an attempt.
5. A failed item now carries `child_stage` (chain, upload, offload, restore)
   and the child's fixed `cause_code`/`cause_stage`; the broker's cause
   allowlist covers the offload, scope and activity-cleanup errors, so A/B no
   longer hide behind `exact_human_approval_state_unknown`.
6. operation-control: activity-cleanup results are projected (state, fixed
   item codes, counts) and recovery-plan names the activity-cleanup steps;
   other storage commands get their own command's guidance; the index-health
   text stays only for index-health. `command_outcome` says whether the
   command itself succeeded, apart from operation-control's own
   `ok`/`recovery_required`. The guidance states that Git backup and storage
   work on objects outside the activity are independent; the activity's own
   remaining items finish only through `--reconcile`.
7. Heartbeat: the stream-bundle child sent `"N-streams"` as the progress count;
   the heartbeat divided it and the thread died. Counts are validated
   (non-negative integers only, violations counted), emit failures are
   counted instead of ending the thread, the child reports its parent's
   1-based position, and the result carries `progress_reporting`.
8. Performance, first step: each composed child plan ran the archive-wide
   capacity scan, a display-only figure (`capacity`, `cost_estimate`) that is
   not part of any approval binding. Measured on a synthetic 20k-row archive
   it was about half of the per-item time. Composed children now skip it
   (`not_computed_for_composed_child`); standalone upload and offload still
   show it.

## v0.4.59: where the time goes

1. Index projection: the objects and manifest projection tables are made
   equal to the manifest by writing only rows whose stored values differ,
   instead of deleting and re-inserting every row three times per item. The
   tables end exactly as a full rewrite leaves them (tested against the old
   behaviour, including duplicate object rows, removed rows, a key-order-only
   change and stale stored rows). Lease, fence, owner, seal and the final
   exact-bytes check are unchanged.
2. Non-overlapping timing: `measurements.work_timing` splits the processing
   time into `provider_request`, `manifest_read_parse`,
   `index_projection_seal`, `intake_capture`, `local_hash_verify`,
   `child_approval_claim`, `lock_wait`, `remote_verification`,
   `upload_child_other`, `offload_child_other` and `unattributed_seconds`.
   Entering a category pauses the enclosing one, so they add up to the total;
   only the writer's own thread is measured.
3. Progress and ETA: items already completed are counted in their own
   `activity-cleanup-skip-completed` stage; the item stage and its ETA count
   only the real remaining work (1-based, never jumping backwards).
4. Not done, by measurement: a shared manifest parse cache. The prototype
   measured no gain for the manifest readers (about 11 s before and after on
   the synthetic 20k-row archive), so it is not shipped; `work_timing` will
   show whether the customer's archive differs.

## v0.4.59 also: the Git backup `_exact_add` flake

The recurring Windows CI failure `git_backup_exact_add_failed` (runs 36493971657,
36503046363, 36558030274 and 36858046636 attempt 1) was traced from the job
logs and reproduced locally. It is two product defects:

1. Git's stat cache plus the default Windows `core.autocrlf=true`: a file
   staged by the person (or an editor) a second or more after it was saved
   keeps the converted blob, `git add` on the real index skips the unchanged
   entry, and `_index_matches_group` refuses the exact bytes. Forced
   reproduction (pre-stage delayed 1.1 s) failed 4/4 before, passed 3/3 after.
   Fix: after the normal add, `git add --renormalize` on the paths that
   still exist (deleted paths cannot take it); the index check stays as the
   final guard. The v0.4.46 explanation (a scanner holding the index) was
   wrong and its retry never triggered for this case.
2. `git add --pathspec-from-file` with 1024 literal paths walks the entire
   untracked directory per batch (74 s for the first batch on a hosted
   runner against a 60 s limit). Fix: the isolated proof index, which has
   no stat cache, stages with `update-index --add --remove -z --stdin`
   (identical tree, about 10x faster); the real-index add batches use the
   120 s commit deadline. `update-index` is not used on the real index
   because it trusts the same stat cache. The first PR CI run of this fix
   (36901371101) showed that one unbatched `update-index` of all 11,132
   paths also passes 120 s on a hosted runner (126 s), so the proof index
   is staged in the same 1024-path / 256 KB batches as the real index.

Executing models: the investigation was a read-only subagent (Opus 5.5);
the fix, tests and documents from this point were made by Claude Fable 5.1
after the owner switched the session model on 2026-10-02. Earlier v0.4.58
and v0.4.59 units were Opus 5.5.

## v0.4.60: the customer's v0.4.59 follow-up (same letter, revised 2026-10-03)

The customer updated to v0.4.59 and reran the reconcile for A and B once
(about 94 s instead of 61 min). B was deleted as designed. A remained:
`child_stage=upload`, `exact_human_approval_state_unknown`. They also
reported a letter-flow defect, a stale Git attention and long Git runs.

1. A was not reproduced by the v0.4.58 tests: they cut the upload after the
   remote PUT, where the remote proof completes the item. Reproduced now with
   the real CLI: the upload claim starts, the process is cut before the PUT,
   and the object's manifest row changes afterwards (a later version, or a
   second row for the same bytes). The original child then fails its own
   precondition (`object_storage_upload_plan_changed`) under
   `exact_human_approval_state_unknown`, every time. The customer's A was
   started by a version many releases older, so this is the likely path; the
   exact row change on their PC is not confirmed.
   Decision: when the original upload cannot resume, the remote copy is
   absent and the local object still hashes to its id, close the started
   claim as failed (`activity_cleanup_upload_superseded_original_not_resumable`,
   never as succeeded) and upload again under the reconcile approval (content
   addressed, idempotent, the full remote bytes are verified afterwards);
   otherwise keep the file. The preview reports `original_resume_check` (local
   preconditions only) and the route
   `upload_complete_after_remote_proof_or_upload_again_from_local_bytes`.
2. `operator-feedback-compose --intent revise` rewrote the body and receipt
   but left the draft record on the prior `feedback_ref`, so body-check
   blocked with `feedback_record_binding_mismatch` and no next step; the
   customer's AI had to read the source. The revise approval now moves the
   draft record too (compare-and-swap on the record that still names the
   prior body; status stays draft), and body-check names the exact
   `--intent update --expected-record-sha256` command when needed.
3. Session-start Git attention reported verified pushes as "not pushed" with
   a remote tip 11 days old: the backup pushes to the resolved URL, so Git
   never moved the cached `refs/remotes/<remote>/<branch>` that the attention
   reads. A verified push now moves that ref exactly as `git push <remote>`
   would (only when the remote's fetch refspec maps the branch), and the
   attention says its numbers come from the cached ref.
4. Git preview and run now return `work_timing` (non-overlapping categories);
   the timer follows one owning thread at a time.
5. Shared archive files (manifest, policy, operational context, ledgers) are
   archive-owned; a scoped backup leaves them out by design and an
   archive-wide backup needs the human's agreement (operator guidance).

## Not established

The customer's own run, which internal step originally cut their A and B
transactions, and the per-row cost of their real receipts.
