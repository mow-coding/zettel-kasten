# v0.4.44 public release evidence

This release was tracked in product PR #147 and contains three changes:
- It removes the IMAP header-scan and manifest-writer command chain. That chain was already superseded by the approved mailbox message fetch shipped in v0.4.42: 18 commands, 33 aliases and 7 MCP tools are retired, and their docs are kept as tombstones.
- It revives `notion-recover` as an exact-approved, read-only recovery of Notion parent locations. No other command provides this, so it was restored rather than removed. It uses the new `notion_ancestor_recovery_read` capability and a spawned worker that holds the live token.
- It makes a session permission grant last until it is released, following the owner decision of 2026-09-25. A grant without `--grant-hours` has no expiry.

Development validation used synthetic data and simulated approvals. Publication and clean installations do not establish success on a customer's machine.

## Source and product checks

- [PR #147](https://github.com/mow-coding/zettel-kasten/pull/147) candidate: `a4d3eeb534eaecc07c425a67bf16671eab8bc11c`.
- [Full PR CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36110759203) passed every required job on attempt 3:
  - Attempt 1 failed with a known timeout flake, the two-process operator-feedback create test on Windows shard 1.
  - Attempt 2 failed with the known git-backup flake on Windows shard 4.
  - Both reruns were full reruns, so the verifier binds a single complete attempt.
- Squash merge and annotated `v0.4.44` tag target: `f636a79f6ecf781af2d25f2a8b58f9cf5c847c92`.
- Candidate and merge have the identical complete tree `e849280755df07de9d0ebe5c843c6a6263319fe9`.
- Annotated tag object: `c793f60204d51638076f6462b127efe5d3af828c`.
- [Post-merge main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36135299751) succeeded for that merge.

## Stable package and public verification

[Stable v0.4.44](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.44) was published at 2026-09-25T12:47:12Z and marked Latest. The published file is the retained wheel from the attempt-3 installed-wheel artifact; it was not rebuilt for release.

The release artifact verifier returned `basis: same_full_tree_and_same_verified_wheel_bytes`, `ci_attempt` 3. The draft asset was downloaded and compared byte for byte before publication.

- File: `wom_kit-0.4.44-py3-none-any.whl`
- Size: 3,442,711 bytes
- SHA-256: `1b7c53901f519cbb115a6bb0afcb938cb6248c7973768d6b6073cecd2d7c6b21`

Public checks:
- An anonymous download returned the same bytes.
- Two separate fresh Windows Python 3.12 environments installed the wheel, one from the downloaded local file and one from the public URL. Each reported `archive 0.4.44` from a new process, passed `pip check`, and verified all packaged resources with zero hash mismatches.
- Both verification environments were removed afterwards.

## Automated opt-in beta

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36135412960) completed successfully for the same main merge before the stable release was published.

- Published prerelease `v0.4.45b15` from generated commit `cd9dd7514c2857a993a71099876042e98e89836c`.
- Wheel size: 3,441,058 bytes.
- SHA-256: `f9c2c3cb6abca0ad651a8799ecfa0871cc76f56e51d7611bd3e66841271a9ffb`.
- Its evidence records the reused full-PR-CI proof (`identical_tree_including_workflows_and_dependency_locks`, attempt 3).
- The beta remains opt-in and does not replace the stable latest release.

## Boundaries

No client workspace was used for development tests. Live Notion access by the revived recovery was not exercised against a real workspace. That behaviour, and a grant held until release on a customer's machine, are not confirmed here.
