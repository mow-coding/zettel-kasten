# v0.4.64 public release evidence

This WOM-kit release answers beta letter 183: an activity-cleanup request may select no files and name `remove_empty_directory_trees` (every folder of a tree is bound at plan time and removed deepest first only if unchanged and empty; a folder holding a file, link or reparse point stays with its parents), a `.git` with no file at any depth is no longer treated as a repository, results report folder removal apart from the file items, and previews and results name a missing session-ref context. It does not establish the customer's own run.

## Source and checks

- [Product PR #182](https://github.com/mow-coding/zettel-kasten/pull/182): candidate `2756f08b`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37271196879) passed on attempt 1 and Required CI passed.
- Squash merge and annotated `v0.4.64` target: `fce217a1` (tag object `7f558ac846d9565dfacda8895437ce50cd41eafb`). Candidate and merge complete tree: `d58dc9a418d1a004f8312f7fdeae401f35bf0f78`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37279569692) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37279821091) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.64](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.64) became Latest at **2026-10-05T07:49:57Z**:

- `wom_kit-0.4.64-py3-none-any.whl`
- **3,685,285 bytes**
- SHA-256 `92575d1495595c54dbead4a3f50c2054975fa6dce6f850f7df51794620e78eca`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-05-v0464-public-install.md).

## How the conditions were reproduced

The customer's stated reproduction was built with synthetic files: one file hard-linked into two folders, each with an empty subtree, both folders listed for removal. Before the change the run ended `partial` with guidance that read as unfinished items; after it the result names the folder-only remainder. A follow-up request without items removed the empty trees through the real CLI with no upload, kept a retained secret file and its parent folders, and accepted a `.git` holding no file. Also covered: a folder replaced after the plan is held, a file or folder created after the plan is left alone, a junction is neither followed nor removed, a `.git` with any file keeps the Git checks, a real repository is still a repository. Windows: 266 cleanup-related tests; Linux (container): 147. Executing model: Claude Fable 5.1. The design was decided under the owner's 2026-09-25 design delegation.

## What this release does not prove

The customer's folders (64 and 2,642 empty subfolders), their run, and the cause of the roughly 19-minute first run reported in letter 183 are not confirmed. The legacy alternate-stream boundary of letter 181 is unchanged.
