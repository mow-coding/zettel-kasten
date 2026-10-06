# v0.4.66 public release evidence

This WOM-kit release is the second part of the answer to beta letter 184: a session-scoped Git backup selects the session's own zettel-objet link outputs (producer `session_claimed_zettel_objet_link_output`, scope schema v5): the link receipt, the before-snapshot, the MAC'd session-object-usage record, and the changed zettel when Git's HEAD is the recorded preimage, the worktree is exactly that session's chain of links and the parsed difference is only the appended assets and `updated_at`. The approval claim, its session and the usage record are authenticated with the archive receipt key; the unsigned link receipt is accepted only as the single receipt naming that approval with the same context, plan and target digests (a delegated deviation recorded in the decision log). The objet ledger stays archive-wide; objet registration receipts are not selected yet. It does not establish the customer's own run.

## Source and checks

- [Product PR #185](https://github.com/mow-coding/zettel-kasten/pull/185): candidate `3dfe488f`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37389264795) passed on attempt 1 and Required CI passed.
- Squash merge and annotated `v0.4.66` target: `c0c23fe6` (tag object `92a16e98766933550e72709808976a441e3c4a96`). Candidate and merge complete tree: `13697a80deb8faf1d727b252a82b2dfb83760a96`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37397692863) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37397908796) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.66](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.66) became Latest at **2026-10-06T01:13:11Z**:

- `wom_kit-0.4.66-py3-none-any.whl`
- **3,700,848 bytes**
- SHA-256 `07f697585a041d3ef28e3c61701c5c216ea292113db6252f6e414fff1ae136ef`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-06-v0466-public-install.md).

## How the conditions were reproduced

Through the real CLI in a temporary Git repository with a real registry, grant and claims: a conversation with an `allow_all` grant wrote zettel-objet links without a window; the session-scoped preview selected the changed zettels, link receipts, before-snapshots and usage records; the approved write committed exactly those files and pushed them to a local bare remote; resume reported the completed original. Also covered: a chain of two links on one zettel, edits before and after a link, another conversation's link, two conversations linking one zettel, a window-approved link, a rewritten and a duplicated receipt, a tampered usage record, and a claim-time audit that refuses attribution (nothing is committed). Windows: 301 session Git regression tests; Linux (container): 82; bump-sensitive: 658. Executing model: Claude Fable 5.1. The design was decided under the owner's 2026-09-25 design delegation.

## What this release does not prove

The customer's 43 links and 21 registrations, their run, and the cause of their 634-second preview are not confirmed. Objet registration receipts and the shared objet ledger are not part of a session-scoped backup.
