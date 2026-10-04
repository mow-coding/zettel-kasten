# v0.4.61 public release evidence

This WOM-kit release answers beta letter 181 (from v0.4.60), except its performance item, which follows in v0.4.62. The session closeout now proves the alternate-stream state of cleanup items whose intent was written by an older WOM (a signed attempt's `deleted` row under that exact intent, recorded inventories, stream backups; anything else counted as unknown, never assumed empty), and `session-handoff-checkpoint --accept-legacy-stream-boundary` completes a closeout whose only gap is that boundary after the person agrees. A letter can be revised back to its delivered text (the existing approval receipt for exactly that body is reused), delivery statements count as delivered in the operator guide, and `exact-approval-claim-finalize` refuses a stale reviewed plan at once. It does not establish the customer's own run.

## Source and checks

- [Product PR #177](https://github.com/mow-coding/zettel-kasten/pull/177): candidate `da21e8f1`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37214649249) passed on attempt 1 and Required CI passed. The earlier head `97eb50fe` failed once on an unrelated Ubuntu `git clone` in a project-update test and twice by the third Windows shard reaching its 90-minute limit with 1,869 of 1,874 tests done (slow shared runners, no failing test); the candidate raises that shard's limit to 120 minutes.
- Squash merge and annotated `v0.4.61` target: `4a44bfaa` (tag object `aa682500dfe74cb015c93f0459732621f483c16d`). Candidate and merge complete tree: `ce9b40eba4323a8548bc4e0dfe4839ac843270f0`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37221438743) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37221674631) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.61](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.61) became Latest at **2026-10-04T17:46:29Z**:

- `wom_kit-0.4.61-py3-none-any.whl`
- **3,671,543 bytes**
- SHA-256 `e2d33aeb0794241c46c812efb35c30502d03dbcdc991db5ab17558ab4a2a59ba`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-05-v0461-public-install.md).

## How the conditions were reproduced

The closeout: a synthetic legacy-shaped intent with items deleted by the original run, one finished by a reconcile, one with an alternate data stream preserved alongside, and an interrupted run (1 of 4 qualified before, 4 of 4 after; the interrupted run stays unknown). Letters: create, a wrong revise, the restore of the delivered text and body-check through the real CLI. Finalize: receipts written after the dry-run are refused without a byte scan. Executing model: Claude Opus 5.5.

## What this release does not prove

The number of the customer's items that remain unknown and their own run are not confirmed.
