# v0.4.54 public release evidence

This WOM-kit release answers beta letters 177 and 178 and the owner's 2026-09-30 correction. Letter 178 reported that the customer could not update past v0.4.52: the approved update succeeded with an unacknowledged result delivery, and the v0.4.53 preview stopped with `project_version_update_terminal_cleanup_outcome_unknown`. One cause was reproduced through the real CLI (an unrelated torn operation journal made the delivery re-check fail silently) and fixed; the follow-up command is now listed and complete, a pending delivery is named in the next preview, and `outcome_unknown` names its cause and a names-free residue inventory. Letter requests require an author block. Delivered letters are deleted instead of moved. `git-backup-plan` reads private remotes with the saved Git login by default. Old index snapshot generations are pruned. It does not establish that the customer's own project reaches v0.4.54: the customer's exact `outcome_unknown` state was not reproduced.

## Source and checks

- [Product PR #167](https://github.com/mow-coding/zettel-kasten/pull/167): candidate `1023f6838953c810d06f585d381c01b3b10a4892`; [full CI attempt 1](https://github.com/mow-coding/zettel-kasten/actions/runs/36792258622) and Required CI passed. Earlier runs of the PR failed on Ubuntu in new tests only (fixed) and once cancelled the last Windows shard at its 60-minute limit with no failing test (budget raised to 90).
- Squash merge and annotated `v0.4.54` target: `791875c9cf68227478d04068c235774f68a7e992` (tag object `fe05dee21e52ec84dbf152ffa2a0f82a48cf7db4`). Candidate and merge complete tree: `bba19b13aa8fd1a88ad3aefd4ebed6ebdc27ac79`.
- [Tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36805964937) passed. The first main CI run on the merge commit was cancelled because the tag was pushed for the same commit before it finished (CI concurrency groups push runs by commit); [main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36805902864) was rerun after publication for the beta channel. This ordering deviation is recorded; the published bytes are bound to the tag CI and the PR CI below.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.54](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.54) is Latest:

- `wom_kit-0.4.54-py3-none-any.whl`
- **3,633,515 bytes**
- SHA-256 `dd86efdf314139dc131db7158560dd3caf66c750f3fc1a17f2bbfaae4918f1e7`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-01-v0454-public-install.md).

## How the letters' conditions were reproduced

Letter 178: an approved update in a synthetic project through the real CLI with a torn unrelated operation journal (delivery not acknowledged before the fix), a forced post-acknowledgement discovery failure (pending delivery, previously a clean preview and a generic approve failure), and a forced acknowledgement failure; each then a next-version preview, `--resume`, and another preview. Letter author: placeholder and missing author blocks refused by the compose planner. Letter 177 follow-up: the anonymous Git preview default, five index runs with edits (old generations pruned) and a committed archive whose old generations become deletions. The design and boundaries are in the v0.4.54 decision logs (`archive-infra-decision-log-2026-09-30-letter-178.md`, `...-feedback-delete.md`, `...-letter-177-followup.md`).

## What this release does not prove

Validation used synthetic archives and projects and an injected approval window. The customer's exact `outcome_unknown` state, a real private Git remote, real R2 keys, the physical Windows windows and the customer's own run are not confirmed.
