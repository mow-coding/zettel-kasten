# v0.4.59 public release evidence

This WOM-kit release is the second part of the answer to beta letter 180 (performance) and also closes the recurring Git backup `_exact_add` failure. The archive index now rewrites only changed manifest rows instead of every row three times per cleanup item; `measurements.work_timing` splits the processing time into non-overlapping categories; progress and ETA count only the remaining items; Git backup re-hashes stat-cached CRLF blobs and stages its proof index in bounded `update-index` batches. It does not establish any customer's run.

## Source and checks

- [Product PR #173](https://github.com/mow-coding/zettel-kasten/pull/173): candidate `46b835df52641e64ce5b0d831da6a42f8b4c2c54`. [Full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36918210468) passed on attempt 2, a full rerun after attempt 1 failed only on the known two-process `test_cli` cold-start timeout (test-only; its budget is corrected in PR #174). An earlier head of this PR failed CI because one unbatched `update-index` of 11,132 paths passed the 120 s step limit on a hosted runner; the candidate batches it. Required CI passed.
- Squash merge and annotated `v0.4.59` target: `762877a7` (tag object `af7510a49c891ad4c0ad2a80b3a1e4f9221c0d6a`). Candidate and merge complete tree: `dde9fe73de68621654620673fa839939a3be6a99`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36942430834) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36942706039) passed.
- The retained CI artifact from attempt 2 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.59](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.59) became Latest at **2026-10-01T23:50:01Z**:

- `wom_kit-0.4.59-py3-none-any.whl`
- **3,663,955 bytes**
- SHA-256 `05cd161d9b8504aea104421b75ccf1149454e9b85d38c295bec87cbcc01cbc7c`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-02-v0459-public-install.md).

## How the conditions were reproduced

The index projection change is tested against the previous full-rewrite behaviour (one row rewritten in place, appended and removed rows, duplicate object rows, a key-order-only change, stale stored rows). The work timing and skip-aware progress run through the real `activity-cleanup` CLI on a synthetic archive. The Git backup causes were traced from four CI job logs and reproduced locally: delaying the pre-stage `git add` past a one-second boundary made the pre-staged group test fail every time before the change (the Git stat cache kept the CRLF-converted blob) and pass after it; the batched `update-index` staging produces the identical tree. Executing models: Opus 5.5 up to the first v0.4.59 commit, Claude Fable 5.1 from the Git backup fix on (owner switch on 2026-10-02).

## What this release does not prove

Every speed figure comes from a synthetic archive; the customer's real archive is not measured. The customer's own run is not confirmed.
