# v0.4.68 public release evidence

This WOM-kit release answers beta letter 186: a real objet-capture receipt keeps its approval reference inside the operation approval receipt (`exact_human_approval.exact_human_approval`); the selector read one level too high, so the v0.4.67 `--approval-id` route attributed none of the customer's 21 captures and the session selector had never attributed a capture by its receipt. The nested reference is now read, and every receipt or item that is not attributed is counted by a fixed reason. Nothing in an archive is rewritten. It does not establish the customer's own run.

## Source and checks

- [Product PR #190](https://github.com/mow-coding/zettel-kasten/pull/190): candidate `f2e0c319`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37567259562) passed on attempt 1 and Required CI passed.
- Squash merge and annotated `v0.4.68` target: `fff7763b` (tag object `2b200fb370aee3d979ebec4b1fbc9977dceb548c`). Candidate and merge complete tree: `2c978ec02b5a2446bc3d116a1e8c10504395bc2b`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37575364101) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37575581685) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.68](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.68) became Latest at **2026-10-07T05:18:55Z**:

- `wom_kit-0.4.68-py3-none-any.whl`
- **3,704,705 bytes**
- SHA-256 `2b1662679f7ffcb4e996abd0cb4213e4693293b6f338fe7a7cdda6be05772ce2`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-07-v0468-public-install.md).

## How the conditions were reproduced

Receipts and claims were produced by the real `objet-capture-batch` writer under a window approval in a temporary archive: the outer approval block has no `approval_id` and the nested reference does; `object-storage-scope-list --approval-id` attributes every captured objet of that approval, the session diagnosis counts them as unmarked, the CLI route writes the list, and a receipt whose reference names a context the claim does not have is rejected as `claim_context_mismatch`. The scope fixture's synthetic receipt was corrected to the real nested shape. Windows: 155 related tests and 656 bump-sensitive tests; Linux through CI (Docker was unavailable after a reboot). Executing model: Claude Fable 5.1. The v0.4.67 change had been verified only against the flat synthetic fixture; that verification gap is recorded in the decision log.

## What this release does not prove

The customer's 21 captures and their run are not confirmed.
