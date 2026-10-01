# v0.4.55 public release evidence

This WOM-kit release answers the owner's 2026-10-01 request: WOM's own byproducts (not the person's or their AI's archive content) are deleted instead of piling up on the operator's PC. A successful, delivered update prunes superseded runtimes and old update records itself, and `system-cleanup` previews and, under one approval, deletes bootstrap environments, WOM temporary files, abandoned restore downloads and old operation results. Receipts, approval claims, credentials, manifests, ledgers and locks are never deleted. It does not establish what a customer's PC holds.

## Source and checks

- [Product PR #169](https://github.com/mow-coding/zettel-kasten/pull/169): candidate `83be4e11aa0cc114f4d0811cb85bfbe405bbe5ae`; [full CI attempt 2](https://github.com/mow-coding/zettel-kasten/actions/runs/36816255988) and Required CI passed. Attempt 1 failed only in a Windows timing-sensitive two-process test that also fails on v0.4.54 under load; an earlier run stopped at the release readiness gate on a reference line budget, fixed in the candidate.
- Squash merge and annotated `v0.4.55` target: `6eb19ba6f5204c0a9db51a4f4f7129b1be23e6d3` (tag object `581892f01a5d27f61f78770918dde1af1b3b90ce`). Candidate and merge complete tree: `f5ef99b3df07b24119e927c2e27084f6bfcf28dd`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36832997231) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36833872291) passed.
- The retained CI artifact from attempt 2 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.55](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.55) became Latest at **2026-10-01T08:04:04Z**:

- `wom_kit-0.4.55-py3-none-any.whl`
- **3,641,378 bytes**
- SHA-256 `31c4c250591c37ed236628d60fc1292a247ef3b160cbc4fe3f92bd62f1192dce`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-01-v0455-public-install.md).

## How it was checked

A synthetic project holding every kind of byproduct (runtimes with and without a WOM receipt, bootstrap environments older and newer than the pin, finished and pending update records, journals including an unreadable one, temporary files and restore partials), the CLI with an injected window, the update journeys with the automatic pruning, and a read-only plan against the developer PC's real `%LOCALAPPDATA%\WOM` (22 bootstrap environments, about 1 GB, found). The design is in `wom-kit/docs/archive-infra-decision-log-2026-10-01-system-cleanup.md`.

## What this release does not prove

Validation used synthetic projects and an injected approval window. What a customer's PC holds and the customer's own run are not confirmed.
