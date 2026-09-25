# v0.4.42 public release evidence

This release adds `imap-mailbox-message-fetch`, which keeps whole mail messages with their attachments under one exact approval, tracked in product PR #144. Development validation used synthetic archives and a fake IMAP server. Publication and clean installations do not establish success on a customer's machine or against a real mail server.

## Source and product checks

- [PR #144](https://github.com/mow-coding/zettel-kasten/pull/144) candidate: `ab1f623522e803d74564885154b10a78c36a9d90`.
- [Full PR CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36076316802), attempt 1: two tests failed, one each on Windows shard 4/4 and Ubuntu py3.12 shard 2/2, both in git-backup commit verification:
  - the recurring `test_git_backup_writer.test_pre_staged_later_group_is_preserved_by_first_exact_commit` (`git_backup_exact_add_failed`)
  - `test_v0420_session_intake_git_public_workflow.test_missing_git_claim_original_review_reuses_saved_intake_proofs_without_hint_discovery` (`git_backup_commit_verification_failed`), which passed five times in a row in a clean `python:3.12-slim` container
- The release does not touch git-backup code. The whole run was rerun at the same commit so that the installed-wheel artifact and the verified run share one attempt. Attempt 2 passed every required job. The flake is tracked for a separate fix.
- Squash merge and annotated `v0.4.42` tag target: `8823f412715636f9003b88611f9b4e47a5a45dc5`. Candidate and merge have the identical complete tree `dbbb16d6f8a23b94dd15d2f5016535f52ab4afd1`. Annotated tag object: `0f1b7d10f02f16e5cf7c3c975ba3d3e30f0ef0af`.
- [Post-merge main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36089667063) succeeded for that merge.

## Stable package and public verification

[Stable v0.4.42](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.42) was published at 2026-09-25T03:34:41Z. The published file is the retained wheel from the attempt-2 installed-wheel artifact; it was not rebuilt for release.

Before publication, the release artifact verifier checked the PR head, the CI attempt and jobs, the merge/tag/tree, package metadata, actual wheel bytes, and the installed-wheel proof. The result was `basis: same_full_tree_and_same_verified_wheel_bytes`, `ci_attempt` 2. The draft asset was downloaded and compared byte for byte before publication.

- File: `wom_kit-0.4.42-py3-none-any.whl`
- Size: 3,451,286 bytes
- SHA-256: `2d3b1ccb31df11684317d7dcc64dadeec2bc315119a5bf8fda57205bbbf350e1`
- An anonymous download returned the same bytes.
- Two separate fresh Windows Python 3.12 environments installed the wheel: one from the downloaded local file, one from the public URL. Each:
  - reported `archive 0.4.42` from a new process
  - passed `pip check`
  - verified all 175 packaged resources with zero hash mismatches
- The URL install's PEP 610 hash matched the public wheel, and its bootstrap check reported `exact_public_release_wheel_verified`.
- The installed `archive imap-mailbox-message-fetch --help` printed its usage.

## Automated opt-in beta

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36089752780) completed successfully for the same main merge before the stable release was published. It generated and published prerelease `v0.4.43b12` from generated commit `129c76d70226c2601d33b83964f2cb4823db1af0`, with wheel size 3,450,059 bytes and SHA-256 `d9de0c48d5e199e51dd80a9810666c00922ead3cc91f3e3643dc17015a08b5bd`. Its evidence records the reused full-PR-CI proof from attempt 2 (`identical_tree_including_workflows_and_dependency_locks`) and a passed installed-wheel check. The beta remains opt-in and does not replace the stable latest release.

## Boundaries

No client workspace or real mailbox was used for development tests. Product implementation, public package verification and customer acceptance are separate states. The customer must confirm their own update and task result; no such confirmation is claimed here.
