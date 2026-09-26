# v0.4.46 public release evidence

This release was tracked in product PR #151. It carries the changes of PR #150 (git index retry) and PR #152 (development rule R9 Docker cleanup), both merged first.

What changed:
- Git backup retries its exact `git add` briefly, only while another program holds the Git index. Two fixed markers identify that condition: "unable to write new index file" and an existing `index.lock`. Every other failure stops at once, and the commit is never retried. This was the recurring hosted-Windows CI failure. It was reproduced locally by holding `.git/index` open for 0.5 s.
- The writer-session coverage audit: 28 writers listed as pending already reach the approval broker's environment grant route and are now recorded as integrated. A traced-route test is the evidence. `credential-adopt` is recorded as a secret-entry exception. No writer behaviour changed.

Development validation used synthetic repositories. Publication and clean installations do not establish success on a customer's machine.

## Source and product checks

- [PR #151](https://github.com/mow-coding/zettel-kasten/pull/151) candidate: `ecba6c38896b15a777d1653f74a24b116b9c2db8`.
- [Full PR CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36216191738) passed every required job on attempt 1, with no rerun. The earlier PR #150 needed one full rerun: an unrelated project-update test failed during temporary-directory cleanup with "Directory not empty: objects".
- Squash merge and annotated `v0.4.46` tag target: `6c82ae2b2b92d065a62c155a029671a5b0faa8c9`.
- Candidate and merge have the identical complete tree `fdcfa916250708a4e0ea99897656ea10e7a67c6c`.
- Annotated tag object: `625b04b36a5bbf9c32483aba75716c3f913a4ca1`.
- [Post-merge main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36235338367) succeeded for that merge.

## Stable package and public verification

[Stable v0.4.46](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.46) was published at 2026-09-26T10:36:44Z and marked Latest. The published file is the retained wheel from the attempt-1 installed-wheel artifact; it was not rebuilt for release.

The release artifact verifier returned `basis: same_full_tree_and_same_verified_wheel_bytes`, `ci_attempt` 1. The draft asset was downloaded and compared byte for byte before publication.

- File: `wom_kit-0.4.46-py3-none-any.whl`
- Size: 3,448,601 bytes
- SHA-256: `bc1c9f73eb8c0db0cb8c8c74f6ee59f9b96a88e0e5bb17e76205b04d54653c31`

Public checks:
- An anonymous download returned the same bytes.
- Two separate fresh Windows Python 3.12 environments installed the wheel, one from the downloaded local file and one from the public URL.
- Each reported `archive 0.4.46` from a new process and passed `pip check`.
- Each verified all 179 packaged resources with zero hash mismatches.
- Both verification environments were removed afterwards.

## Automated opt-in beta

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36235399340) completed successfully for the same main merge before the stable release was published.

- Published prerelease `v0.4.47b20` from generated commit `930a46273adabcfec1b6044e17240eb851f65f8e`.
- Wheel size: 3,447,565 bytes.
- SHA-256: `d98888aedd851d28d01884ca40641153bcdaa00e2a064b96fd926219bddd5087`.
- Its evidence records the reused full-PR-CI proof (`identical_tree_including_workflows_and_dependency_locks`, attempt 1).
- The beta remains opt-in and does not replace the stable latest release.

## Boundaries

No client workspace was used for development tests. The retry has not been observed on a customer machine. A single Ubuntu-only `git_backup_commit_verification_failed` seen once in another test is unrelated and not addressed.
