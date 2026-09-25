# v0.4.41 public release evidence

This release reopens the new-user entry (`onboard`, `init --approve`, runtime-skill install), makes Notion page recovery work with an adopted credential, adds Notion trash cleanup, and reopens relation accept, external import, credential lifecycle and five more writers under exact approval. It is tracked in product PR #142. Development validation used synthetic archives. Publication and clean installations do not establish success on a customer's machine.

## Source and product checks

- [PR #142](https://github.com/mow-coding/zettel-kasten/pull/142) candidate: `ddcb1252f65795f17f5cfb1fc1114461e13a9e81`.
- Before the candidate, two corrections were made. At `daf67b92` the release note's still-closed list was corrected: it had listed five commands that this release reopens and had omitted `operation-control`. The first full CI run on that commit then failed on all Ubuntu shards. The legacy-coordination retire approve path opened the dialog on Linux and reported a lock failure, although the bound moves are Windows-only; the retire's git child processes did not name the common hidden-window policy; and one inventory test still pinned old counts. The candidate fixes all three: it refuses an unsupported platform before any dialog.
- [Full PR CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36058658816) for the candidate:
  - Attempt 1 failed only on Windows shard 4/4, at the recurring flake `test_git_backup_writer.test_pre_staged_later_group_is_preserved_by_first_exact_commit` (`git_backup_exact_add_failed`). That test passed three times in a row locally.
  - Attempt 2 reran the failed jobs and succeeded.
  - The release artifact verifier binds the installed-wheel proof to the run attempt, so the attempt-1 wheel could not be used with an attempt-2 run. The whole run was therefore rerun at the same commit.
  - Attempt 3 passed every required job and produced the released wheel.
  - Runs superseded by later pushes were cancelled and are not pass evidence.
- Squash merge and annotated `v0.4.41` tag target: `9c0240fb3c1307efed5e20a852a23164e1b2349a`. Candidate and merge have the identical complete tree `3b28b36aaec8277cb8583d9028dbac101c69da04`. Annotated tag object: `204120a2ac83c0c09dafd62f549d98a3a80a38ba`.
- [Post-merge main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36074854494) succeeded for that merge.

## Stable package and public verification

[Stable v0.4.41](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.41) was published at 2026-09-25T01:59:51Z.

- The published file is the retained wheel from the attempt-3 installed-wheel artifact. It was not rebuilt for release.
- Before publication, the release artifact verifier checked:
  - the PR head and the CI attempt and jobs
  - merge, tag and tree
  - package metadata, actual wheel bytes and installed-wheel proof
- The verifier's basis was `same_full_tree_and_same_verified_wheel_bytes`, with `ci_attempt` 3.
- The draft asset was downloaded and compared byte for byte before publication.

Wheel details:
- File: `wom_kit-0.4.41-py3-none-any.whl`
- Size: 3,445,618 bytes
- SHA-256: `ec9abfa83a762bcd52b0bb9b7656f813d4b93f5293739a22bf2a281910718112`

Install checks:
- An anonymous download returned the same bytes.
- Two separate fresh Windows Python 3.12 environments installed the wheel, one from the downloaded local file and one from the public URL. Each environment:
  - reported `archive 0.4.41` from a new process
  - passed `pip check`
  - verified all 175 packaged resources with zero hash mismatches
- The URL install's PEP 610 hash matched the public wheel, and its bootstrap check reported `exact_public_release_wheel_verified`.

## Automated opt-in beta

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36074961380) completed successfully for the same main merge before the stable release was published.

- It generated and published prerelease `v0.4.42b11` from generated commit `6a60b7857b340aa76a9fb074ecd6d15ee085ab8b`.
- Wheel size: 3,443,788 bytes. SHA-256: `38260e4202a819068971725f5a4773003b90052fc731a99cb155a1b77c6fc4a0`.
- Its evidence records the reused full-PR-CI proof from attempt 2 (`identical_tree_including_workflows_and_dependency_locks`) and a passed installed-wheel check.
- The beta remains opt-in and does not replace the stable latest release.

## Boundaries

No client workspace was used for development tests. Product implementation, public package verification and customer acceptance are separate states. The customer must confirm their own update and task result; no such confirmation is claimed here. The recurring git-backup CI flake is tracked for a separate fix.
