# Archive infra decision log: WOM's own byproducts are deleted (2026-10-01)

Status: requested by the owner on 2026-10-01 ("build it while we wait for the
beta testers' feedback"); design delegated to Claude's recommendation under
the 2026-09-25 delegation; implemented for v0.4.55.

## Question

WOM itself, not the person or their AI, leaves files on the operator's PC
while it updates, downloads and recovers. Which are they, and is anything
cleaning them? Without cleanup the PCs of everyone using WOM fill with junk.

## What an inventory of the code found

- Nothing ever deleted old project runtimes (`.zettel-kasten/runtimes/v*`,
  about 35-50 MB each, "never deletes an older runtime" by design) or the
  bootstrap environments the install instructions create under
  `%LOCALAPPDATA%\WOM` (40-56 MB each; 25 of them, 1.4 GB, on the
  developer's PC).
- Every update run left an update result, a consumed handoff capsule and an
  operation journal; nothing deleted them. More than 4096 journals make the
  update's delivery scan fail, so the clutter eventually blocks updates.
- Abandoned restore downloads (`*.part`), WOM temporary files after a crash
  and archive operation results also stayed.
- Already cleaned: index snapshot generations (v0.4.54), the runtime
  candidate on handled outcomes, finished update transactions, temporary
  files in `finally` blocks.

## Decision

1. `archive system-cleanup <archive-root> --dry-run` lists kinds, counts and
   bytes (never paths); `--approve --reviewed-by --expected-plan-sha256`
   deletes the exact plan under one approval (grantable kind
   `system_cleanup`) and writes a content-free receipt under
   `receipts/system-cleanup/`.
2. After a successful update whose result delivery was acknowledged, WOM
   deletes project-internal byproducts automatically (the person approved the
   update; these are superseded WOM files, like the v0.4.54 snapshot pruning).
   Bootstrap environments, temporary files and archive items need the
   command's approval.
3. Rules:
   - runtimes: keep the pinned version and the one before it (rollback);
     delete others only with a valid WOM runtime receipt for that version;
     never the running interpreter;
   - update results and handoff capsules: keep the newest five and anything
     younger than seven days; keep all while a delivery is pending;
   - operation journals: keep the newest twenty and anything younger than
     seven days; delete only completed ones (an update journal only after its
     delivery was acknowledged) and unreadable ones;
   - bootstrap environments: folders in `%LOCALAPPDATA%\WOM` named
     `bootstrap-v<version>...` with a `pyvenv.cfg`, not newer than the pinned
     version, older than a day, not the running interpreter;
   - WOM temporary files and abandoned restore downloads: WOM name patterns,
     older than a day;
   - nothing in the project while the update lock or an update transaction
     exists;
   - never deleted: receipts, approval claims, credential records, manifests,
     ledgers, locks, open update transactions.
4. Deleted items cannot be recovered; all are rebuildable or finished.

## Not in this release

- Work-session registry generations grow with every session change and
  cannot be pruned without a format change (a base checkpoint); source-intake
  contexts stop at 128. Both need their own design and are recorded here as
  the next step.
- The source mirror is not garbage-collected (its Git metadata is part of the
  update's checks); the pip cache is pip's.

## Validation

A synthetic project with every kind of byproduct, the planner run read-only
against the developer PC's real `%LOCALAPPDATA%\WOM` (22 bootstrap
environments, about 1 GB, found), the CLI with an injected dialog. The
customer's PC is not inspected.
