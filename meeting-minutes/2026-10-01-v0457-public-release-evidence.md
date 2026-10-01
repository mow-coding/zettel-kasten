# v0.4.57 public release evidence

This WOM-kit release implements the owner's idea of 2026-10-01: archived mail can be read as threads per mailbox account. `mail-threads --build` rebuilds the `.eml` mail objets into one Markdown record per thread under `db/mail-threads/<generation>/`. The snapshot is derived: it never changes the objets, and the zet flow is unchanged. It does not establish any customer's run.

## Source and checks

- [Product PR #171](https://github.com/mow-coding/zettel-kasten/pull/171): candidate `a28b1f7c4de3a8ca8fce86cf6e4edba597b99857`. [Full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36858046636) passed on attempt 2, a full rerun after a Windows shard failure in attempt 1. Required CI passed.
- Squash merge and annotated `v0.4.57` target: `72c57141`. The tag object is `1cba8263cc6d2b506b5126e76acc38b0de7d58e7`. Candidate and merge complete tree: `339d79764ea7bc0073fca009ec72587cac3e4636`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36886025117) passed before the tag was pushed. The [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36886328552) passed after it.
- The retained CI artifact from attempt 2 was checked with `wom-kit/release-artifact-reuse/v1` (`same_full_tree_and_same_verified_wheel_bytes`). The check covered the PR, CI run, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size. The artifact was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.57](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.57) became Latest at **2026-10-01T15:44:11Z**:

- `wom_kit-0.4.57-py3-none-any.whl`
- **3,655,417 bytes**
- SHA-256 `e42248e9f598480d1edbadf9991fda4aa71a53a253c57f8579aca174786df396`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-01-v0457-public-install.md).

## What this release does not prove

It used synthetic mail only: reply chains, a duplicate fetch, mail without threading headers, HTML-only mail, two accounts and an offloaded mail. Real mailboxes from different providers are not yet tested.
