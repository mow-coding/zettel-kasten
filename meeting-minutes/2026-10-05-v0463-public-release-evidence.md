# v0.4.63 public release evidence

This WOM-kit release answers beta letter 182: activity-cleanup accepts a hard-link group when every link is a selected item with the same role and disposition (the body is preserved once; each link is removed with the exact identity and the expected link count proven before and after the delete mark), a partly selected group or a link outside the selected folders is a named blocker with counts, a `secret_config` role is never uploaded and is discarded only after the person's confirmation, and the result separates `selected_items_complete` from `folders_empty` with a plain summary. It does not establish the customer's own run.

## Source and checks

- [Product PR #180](https://github.com/mow-coding/zettel-kasten/pull/180): candidate `fa3165b2`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37242438057) passed on attempt 1 and Required CI passed.
- Squash merge and annotated `v0.4.63` target: `21e1d6c5` (tag object `aa30ea0549aff56607c22f2aa59042bed01c747f`). Candidate and merge complete tree: `ba65d9e7fc8965dfc4e55df8fe0f4d661d26b2ae`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37248893317) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37249025759) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.63](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.63) became Latest at **2026-10-05T00:51:29Z**:

- `wom_kit-0.4.63-py3-none-any.whl`
- **3,677,979 bytes**
- SHA-256 `9a447b064fcb766dff293204c7459ade6e0c803da42dfb13c9ae91a118410417`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-05-v0463-public-install.md).

## How the conditions were reproduced

The customer's stated reproduction was built with synthetic files: one test PDF hard-linked into folders A and B, both in scope. One representative path is held with counts; both paths selected upload the body once through the real CLI and remove both links; a link outside the selected folders stays held; a link created after planning retains both names; alternate data streams survive both deletes; an interrupted run resumes. Windows: 246 cleanup-related tests; Linux (container): 125. Executing model: Claude Fable 5.1. The `secret_config` design was decided under the owner's 2026-09-25 design delegation.

## What this release does not prove

The customer's ten paths, their two configuration files and their run are not confirmed.
