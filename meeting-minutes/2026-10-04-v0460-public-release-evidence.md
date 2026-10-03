# v0.4.60 public release evidence

This WOM-kit release answers the v0.4.59 follow-up in beta letter 180 (the same letter, revised by the customer on 2026-10-03). On v0.4.59 the customer's reconcile finished item B in about 94 seconds, but item A remained at the upload step. Item A (an upload child whose claim started before any remote write and whose object's manifest row changed afterwards) was reproduced with the real CLI on Windows and is now uploaded again from the exact local bytes when the original cannot resume. Also in this release: `compose --intent revise` moves the draft record to the revised body; a verified Git backup push refreshes the cached remote-tracking ref read by the session-start attention; Git preview and run report non-overlapping `work_timing`. It does not establish the customer's own run.

## Source and checks

- [Product PR #175](https://github.com/mow-coding/zettel-kasten/pull/175): candidate `43dbf79b55f48f6df8f0b63380e88bfd94fbb572`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37137408701) passed on attempt 1 and Required CI passed. The previous head failed only on Ubuntu in two test_cli revise tests that rebound the record by hand (the revise approval now does it); the candidate updates them.
- Squash merge and annotated `v0.4.60` target: `ed1d348a` (tag object `c7e366d227d65fb0743ca646e81ea98ea0b00ef3`). Candidate and merge complete tree: `1274ebacecf30fd040e3d9ab4609bae597d7d9c4`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37144499583) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37144635577) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.60](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.60) became Latest at **2026-10-03T18:34:40Z**:

- `wom_kit-0.4.60-py3-none-any.whl`
- **3,667,714 bytes**
- SHA-256 `9deac4a8e20d43d839dbb7453788a5e90b0d6534439e9bf8280f19fab6a41f29`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-04-v0460-public-install.md).

## How the conditions were reproduced

Synthetic archive, synthetic bytes and an in-memory transport through the real `activity-cleanup` CLI on Windows: the upload cut before the remote PUT, with and without a later change to the object's manifest row, and with damaged local bytes (the file is kept). The letter revise flow ran create, revise and body-check through the real CLI, plus a service-only revise to check that body-check names the exact record update. The Git tracking-ref refresh and the work timing ran through the Git backup writer tests. Executing model for v0.4.60: Claude Opus 5.5.

## What this release does not prove

The exact change to item A's manifest row on the customer's PC, the time on their real archive and their own run are not confirmed.
