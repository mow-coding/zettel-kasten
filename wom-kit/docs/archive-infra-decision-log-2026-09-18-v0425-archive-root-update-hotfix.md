# Decision amendment: recorded update locations are inspection-root relative

Date: 2026-09-18
Status: accepted; v0.4.25 hotfix, development verified

## Context

Beta letter 161 (2026-09-17) reported a reviewed v0.4.21 update that failed
after the native approval and a `--resume` that died in preflight; v0.4.22
added the cause projection, journal stage names and the started-claim abandon,
but its reproduction ran from the project root and updated cleanly, so the
refusing gate stayed unknown. The client's 2026-09-18 report showed the same
resume failure on v0.4.24. Reproducing the client's exact invocation form,
the archive root as the positional argument, exposed the defect.

## Decisions

1. Recorded update locations (`mirror_logical`, pin `logical`, component
   `logical_target`, receipt logical) stay exactly as preflight writes them:
   relative to the inspection root, with the `parent_of_archive` label when
   the archive root was given. Changing the recorded form would alter plan
   digests and could not help the transaction the client already holds.
2. Every consumer that turns such a location into a path goes through one
   resolver that strips the label and refuses absolute, empty or traversing
   values. The six sites are the transaction reopen (mirror, component
   paths), the post-approval snapshot guard (pin specs) and the
   terminal-original checks (mirror, regular components, active pin). The
   runtime and launcher locations were already project-root relative and are
   unchanged by the resolver.
3. A failure raised by the service before any result carries its fixed code
   and the journal stage as the content-free cause, under the v0.4.22
   allowlist plus the `operation_` family. The journal schema is not bumped;
   the stage names already say where the run stopped.
4. Deferred, recorded here so they are not lost: the public `files_written`
   list keeps the recorded (labelled) form; the fresh path's pre-dialog
   `failed_rollback_incomplete` result carries a text blocker without a fixed
   code (observed once on a fixture under concurrent test load, not
   reproduced on a clean rerun); a `--resume --dry-run` read-only preview.

## Evidence

Synthetic fixtures only (`repro_v0424_resume.py`, session scratchpad):
released v0.4.18 wheel from the archive root fails after the dialog with
`approved_snapshot_changed`; released v0.4.21 wheel reproduces letter 161 ③;
released v0.4.24 wheel's `--resume --abandon-started-approval` raises
`directory_stability_unavailable` from the reopen from either root; the
hotfix build returns `preapproval_scaffold_cancelled` and a fresh archive-root
approve reaches `updated_restart_required`; a plain `--resume` on the same
state reopens, rediscovers the started claim and is refused by the
snapshot guard (`project_runtime_policy_invalid` under the newer runtime
policy), so the abandon route is the documented recovery.
`tests/test_v0425_archive_root_update_hotfix.py` pins the resolver, the
consumers and the direct-cause projection.
