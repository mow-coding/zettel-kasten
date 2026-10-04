# v0.4.62 public release evidence

This WOM-kit release is the second part of the answer to beta letter 181: remote cleanup fences keys in chunks of up to 16 under one fresh reference scan (every key still goes through proof, delete intent, DELETE, absence check and final journal) and reuses parse results of identical bytes; manifest readers reuse strict-parse facts of unchanged lines; operation journals v0.3 carry done/total so `operation-control` status shows progress for activity-cleanup and object-storage-cleanup. It does not establish the customer's own run or timings.

## Source and checks

- [Product PR #178](https://github.com/mow-coding/zettel-kasten/pull/178): candidate `f1aa150d`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37221719769) passed on attempt 1 and Required CI passed.
- Squash merge and annotated `v0.4.62` target: `e890d7e0` (tag object `3490544fb51cc3065a54f4ed15d4a6070dd3976a`). Candidate and merge complete tree: `ec4e6047d71594bbd41120b5ca58ba4b4a3470cc`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37228951232) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37229070460) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.62](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.62) became Latest at **2026-10-04T19:40:20Z**:

- `wom_kit-0.4.62-py3-none-any.whl`
- **3,674,100 bytes**
- SHA-256 `4048098fc2798b8d6d9fbe593c4f51b7a6ebda50ec5a06b5195eaf53c105c411`

The anonymous download (one transient connection reset, then retried) and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-05-v0462-public-install.md).

## How the conditions were measured

A read-only investigation built a synthetic archive at the customer's scale (23,005 manifest rows, 3,017 approval claims, 3,004 zettels; in-memory transport). Remote cleanup of 80 keys: about 269 s before, about 8 s with the chunked fences and parse reuse. Three activity-cleanup items: 111 s before, 100 s after; manifest parsing 53 s -> 33.5 s. A claim-listing cache keyed by file metadata was measured but not shipped. Executing model: Claude Opus 5.5.

## What this release does not prove

The customer's own timings (their intake and child-step costs were higher than the synthetic ones) and their run are not confirmed.
