# v0.4.43 public release evidence

This hotfix answers beta letter `wom-feedback-20260925-173` and was tracked in product PR #146. A v0.4.38 -> v0.4.42 project update run with a bare `--reviewed-by` id stopped before the approval window. The official resume and abandon then stopped the same way, and the update lock blocked new work sessions.

The fix has three parts:
- A bare reviewer id is now read as `person:<id>`.
- A failure while the approval context is built releases the reserved update.
- The update result names the fixed approval sub-code and stage.

Development validation used synthetic data and a simulated approval. Publication and clean installations do not establish success on a customer's machine.

## Source and product checks

- [PR #146](https://github.com/mow-coding/zettel-kasten/pull/146) candidate: `78bb4c1ddd3f55784badc4f513ef07d7e927edd0`.
- [Full PR CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36100583683) passed every required job on attempt 1, with no rerun.
- Squash merge and annotated `v0.4.43` tag target: `48735328a97b39d4eae58ff7a2e2aed8831b6753`.
- Candidate and merge have the identical complete tree `a83b5baa86204b93a1194e9b27911c1c92f808c3`.
- Annotated tag object: `e504dfb19a691f123f240d3d53a14b3c9ad7fc2a`.
- [Post-merge main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36108838796) succeeded for that merge.

## Stable package and public verification

[Stable v0.4.43](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.43) was published at 2026-09-25T08:00:42Z. The published file is the retained wheel from the attempt-1 installed-wheel artifact; it was not rebuilt for release.

Before publication, the release artifact verifier checked the PR head, the CI attempt and jobs, the merge, tag and tree, the package metadata, the actual wheel bytes, and the installed-wheel proof. The result was `basis: same_full_tree_and_same_verified_wheel_bytes`, `ci_attempt` 1. The draft asset was downloaded and compared byte for byte before publication.

- File: `wom_kit-0.4.43-py3-none-any.whl`
- Size: 3,451,904 bytes
- SHA-256: `3e22193d7dc02184e31e1638cd1c474076812b42ac65fa2f25a69e32f57400fe`

Public checks:
- An anonymous download returned the same bytes.
- Two separate fresh Windows Python 3.12 environments installed the wheel, one from the downloaded local file and one from the public URL. Each reported `archive 0.4.43` from a new process, passed `pip check`, and verified all packaged resources with zero hash mismatches.

## Automated opt-in beta

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36108948079) completed successfully for the same main merge before the stable release was published.

- Published prerelease `v0.4.44b14` from generated commit `c14d6c390319f5264ed47ece81764b574a078055`.
- Wheel size: 3,450,719 bytes.
- SHA-256: `b7afc653c5bf731ca00745f686f1a9af6271a6188a56160d73497264ba87787c`.
- Its evidence records the reused full-PR-CI proof (`identical_tree_including_workflows_and_dependency_locks`).
- The beta remains opt-in and does not replace the stable latest release.

## Boundaries

No client workspace was used for development tests. The tester's stuck update is expected to close through the new bootstrap's `--resume`: it authenticates zero claims and releases the lock without project changes. That outcome and the following update are not confirmed here.
