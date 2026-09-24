# v0.4.40 public release evidence

This release goes through the 58 writers fixed closed since v0.4.0 (27 reopened under exact approval plus two new batch commands, 12 removed, the rest kept closed until designed) and adds the activity-scoped close for beta letter 173 D, tracked in product PR #141. Development validation used synthetic archives. Publication and clean installations do not establish success on a customer's machine.

## Source and product checks

- [PR #141](https://github.com/mow-coding/zettel-kasten/pull/141) candidate: `7d1057969cd343ef7598b32e669e1a15727452c6`.
- [Full PR CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36037717962), attempt 1: all required product/readiness jobs and Required CI succeeded. Windows shard 2/4 took about 95 minutes against about 50 for the other shards; it passed. The earlier run on `05ee4e79` failed on both Ubuntu shard 1/2 jobs because a pytest-style saved-view test still expected the pre-reopen fixed-closed code and called `--approve` without replacing the native dialog; the final candidate injects a declining dialog. Runs superseded by later pushes were cancelled and are not pass evidence.
- Squash merge and annotated `v0.4.40` tag target: `41ae8f0261d0d1d314f11866be4aea8da9722fab`. Candidate and merge have the identical complete tree `cd7a70deb3aa22c0531c9ae0e38881e775e03d13`. Annotated tag object: `7a0a9e071ecf964c09688deabdfd9bb1c998852b`.
- [Post-merge main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36048341615) succeeded for that merge.

## Stable package and public verification

[Stable v0.4.40](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.40) was published at 2026-09-24T19:46:29Z. The published file is the retained wheel from the full PR CI installed-wheel artifact; it was not rebuilt for release. The release artifact verifier checked PR head, CI attempt/jobs, merge/tag/tree, package metadata, actual wheel bytes, and installed-wheel proof before publication (`basis: same_full_tree_and_same_verified_wheel_bytes`). The draft asset was downloaded and compared byte for byte before publication.

- File: `wom_kit-0.4.40-py3-none-any.whl`
- Size: 3,409,933 bytes
- SHA-256: `b6c47163a26d31d0b79803a36aab4eb3b615ba5282ada47e76936f7f898cdad8`
- An anonymous download returned the same bytes. Two separate fresh Windows Python 3.12 environments installed from the downloaded local file and the public URL. Each reported `archive 0.4.40` from a new process and passed `pip check`; the URL install's PEP 610 hash matched the public wheel.

## Automated opt-in beta

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36048463421) completed successfully for the same main merge before the stable release was published. It generated and published prerelease `v0.4.41b9` from generated commit `81bfb505ddf3bff7856b8306866c7a3fe0e325cf`, with wheel size 3,407,795 bytes and SHA-256 `4f5c5d98c8536a6f16436dabb797f50f3f7cc870a7e6d45b2971f43377872710`. Its evidence records the reused full-PR-CI proof (`identical_tree_including_workflows_and_dependency_locks`) and a passed installed-wheel check. The beta remains opt-in and does not replace the stable latest release.

## Boundaries

No client workspace was used for development tests. Product implementation, public package verification and customer acceptance are separate states. The customer must confirm their own update and task result; no such confirmation is claimed here.
