# v0.4.52 public release evidence

This WOM-kit release finishes the implementable work that beta letters 174-176 left open after v0.4.51: index-bound commands on large archives no longer open every zet file (A14), a registered objet is found by its original filename (A17), the installed-wheel gate checks the packaged helper-AI guidance against the installed commands (A13), and the 25 additional-verification items have synthetic tests with their gaps recorded. It does not establish that a customer's own archive, real provider accounts or the physical Windows dialog behave as the synthetic checks did.

## Source and checks

- [Product PR #163](https://github.com/mow-coding/zettel-kasten/pull/163): candidate `65bbd9ce22e07dad514754d5059bf539773396e1` (rebased onto the v0.4.51 merge); [full CI attempt 1](https://github.com/mow-coding/zettel-kasten/actions/runs/36582032731) and Required CI passed. Earlier runs on this branch failed on a mixed-case product term, a dropped word in the capture reference, the third Windows shard's 75-minute budget (now 90), the sharding contract for that budget, and twice on the git-backup index-file hold on shared Windows runners (`git_backup_exact_add_failed`); the last was fixed in the product by a longer retry ladder that also covers the isolated-index read-tree and write-tree steps.
- Squash merge and annotated `v0.4.52` target: `ed33f6ae149005f8c618bfb5f75b6e02a9949834` (tag object `b0cb28da855fac1bf14a3f51c0a634f26108ec67`). Candidate and merge complete tree: `2df4c915cbd96aca50104d40da588f3320de2ec5`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36594034896) and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36596577594) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Automatic beta and stable publication

[Automatic Beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36594171672) passed before stable publication. Its source proof matched PR #163, CI attempt 1, the merge and complete tree. Generated commit `c0deba79b51551d13d328ab9ebc569eaa8bb2412`, beta tag `v0.4.53b31`, wheel 3,616,030 bytes, SHA-256 `ded223779b117e6f3c135fd6891e37110d5c6feee6748e36ff2c9a01597e9b5b`; installed wheel passed, customer not verified.

[Stable v0.4.52](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.52) became Latest at **2026-09-29T16:19:43Z**:

- `wom_kit-0.4.52-py3-none-any.whl`
- **3,617,798 bytes**
- SHA-256 `6d6818713742a697be2c72917e1911be62cc7dd24bb94db86ab47222b96add8f`

After publication, anonymous download matched the same size and SHA-256. Two fresh Windows environments installed from the downloaded file and the public URL. Both returned `archive 0.4.52`, passed `pip check`, recorded the expected PEP 610 hash and verified all 180 packaged resources; the public-URL installation's bootstrap decision reported `exact_public_release_wheel_verified`. See [the sanitized install result](2026-09-29-v0452-public-install.md).

## Performance evidence (A14)

The official installed-launcher measurement compared public v0.4.47 with the unreleased candidate wheel that carried the same live-scan change (66 fresh processes on the same 9,619-file synthetic input: 23,000 objects, 8,616 zets, 1,000 authenticated claims). Repeat p95: `zettel-edge --dry-run` 2.524 s to 0.881 s (65.12 %), `zettel-objet-link --dry-run` 2.717 s to 1.212 s (55.39 %), `exact-approval-claims --status all` 2.335 s to 0.891 s (61.84 %). Approval waiting, actual writes, remote transfer and customer PCs were not measured. The design and boundaries are in `wom-kit/docs/archive-infra-decision-log-2026-09-29-a14-live-scan.md`.

## What this release does not prove

Validation used synthetic data, the example archive and an injected approval window. Real Notion, mailbox, Tiro and R2 accounts, the physical Windows dialog and customers' own runs are not confirmed. No canonical hold command exists yet (S2-U24, recommendation recorded); letter 176 items 9, 11 and 12 need the customer's own environment.
