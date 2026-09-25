# v0.4.45 public release evidence

This release was tracked in product PR #148. It condenses the helper-AI runtime skill:
- `SKILL.md` now opens with twelve core rules, followed by an intent-to-command table whose every command is checked against the CLI.
- Rarely needed detail moved into four focused references: credentials and sessions, long operations and updates, developer letters, and models and reasoning.
- Two contradictions in the guidance are fixed.
- A document with eighteen scenarios drawn from beta letters 150 to 173 lets a person check an AI or a guidance change by hand.

The model and reasoning guidance is a recommendation, not a benchmark. Development validation checked the packaged guidance text and resources. It does not show that any AI model follows the rules on a customer's machine.

## Source and product checks

- [PR #148](https://github.com/mow-coding/zettel-kasten/pull/148) candidate: `228cf0761fdd3d27aad3f6d6d78a8b1e18278cbe`.
- [Full PR CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36135602515) passed every required job on attempt 1, with no rerun.
- Squash merge and annotated `v0.4.45` tag target: `9f61629049eba4dae1ae9b5e2fae8fb487a61aea`.
- Candidate and merge have the identical complete tree `c5a14aae03aeb4446d819a94b4923906da77c8ad`.
- Annotated tag object: `b8df512cd9434b43ebf939c617044505306efc44`.
- [Post-merge main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36145860966) succeeded for that merge.

## Stable package and public verification

[Stable v0.4.45](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.45) was published at 2026-09-25T14:30:57Z and marked Latest. The published file is the retained wheel from the attempt-1 installed-wheel artifact; it was not rebuilt for release.

The release artifact verifier returned `basis: same_full_tree_and_same_verified_wheel_bytes`, `ci_attempt` 1. The draft asset was downloaded and compared byte for byte before publication.

- File: `wom_kit-0.4.45-py3-none-any.whl`
- Size: 3,447,774 bytes
- SHA-256: `fc5e24e385482e0e1e154be2d49cfda46165efe9e2060d380084b6b34d70a080`

Public checks:
- An anonymous download returned the same bytes.
- Two separate fresh Windows Python 3.12 environments installed the wheel, one from the downloaded local file and one from the public URL.
- Each reported `archive 0.4.45` from a new process and passed `pip check`.
- Each verified all 179 packaged resources with zero hash mismatches.

## Automated opt-in beta

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36145992077) completed successfully for the same main merge before the stable release was published.

- Published prerelease `v0.4.46b16` from generated commit `1a7870a15e82b2adbf4fcfbc44526f1c2916adc1`.
- Wheel size: 3,446,568 bytes.
- SHA-256: `0eae776f191023ced9364a8c0ae76424fa1572708af4a4edaf0bd697bf82288c`.
- Its evidence records the reused full-PR-CI proof (`identical_tree_including_workflows_and_dependency_locks`, attempt 1).
- The beta remains opt-in and does not replace the stable latest release.

## Boundaries

No client workspace was used for development tests. A customer project receives the new skill only through the reviewed `project-version-update` flow or `runtime-skill-install`. Whether helper AIs follow the condensed rules better in practice has not been confirmed.
