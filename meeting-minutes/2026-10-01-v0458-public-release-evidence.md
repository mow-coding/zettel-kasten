# v0.4.58 public release evidence

This WOM-kit release answers beta letter 180, sent from v0.4.56: the same two activity-cleanup items as letters 174 and 179 stayed unfinished after a 61-minute reconcile. Both conditions (a child upload whose claim was left started after the remote bytes were stored, and a child offload whose control file was never written) were reproduced with the real CLI on Windows and are now recovered by the official reconcile; the preview diagnoses each unfinished item read-only; operation-control gives activity-cleanup its own guidance; the progress heartbeat survives non-count values; composed children skip the display-only capacity scan. It does not establish the customer's own run.

## Source and checks

- [Product PR #172](https://github.com/mow-coding/zettel-kasten/pull/172): candidate `fe3595bfae2ea48a19e7da8be5c7389c931fb0c0`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36886214228) passed on attempt 1 and Required CI passed.
- Squash merge and annotated `v0.4.58` target: `0bf1a71b` (tag object `57a56fe01a430823c15caf35be23f9e4886d7f69`). Candidate and merge complete tree: `ff9fe7ae2a89848ff6a9ec8a3db0882a0b258702`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36901214052) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36901568618) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.58](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.58) became Latest at **2026-10-01T17:46:02Z**:

- `wom_kit-0.4.58-py3-none-any.whl`
- **3,660,629 bytes**
- SHA-256 `42d450f605a74458ff25a30ace89d7efc89bf999de07fd6c4767bda0111b84e3`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-01-v0458-public-install.md).

## How the letter's conditions were reproduced

Synthetic archive, synthetic bytes and an in-memory transport, through the real `activity-cleanup` CLI on Windows: item A cut after the remote PUT and after the child effects before the claim finalize; item B cut before the offload control file is written, with and without later inventory changes; the offload completed with its control file removed; a repeated approval of the same reconcile; and local bytes changed so that no effect can be proven (the file is kept). The scenarios are `tests/test_letter180_activity_cleanup_recovery.py`; the design is in `wom-kit/docs/archive-infra-decision-log-2026-10-01-letter-180.md`.

## What this release does not prove

The customer's own run, the original cause of their two interrupted child transactions, and the time on their real archive are not confirmed. The remaining performance work (index projection, work timing, skip-aware progress) and the Git backup `_exact_add` fix follow in v0.4.59.
