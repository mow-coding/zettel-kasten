# v0.4.53 public release evidence

This WOM-kit release answers beta letter 177, sent from public v0.4.52. Following the owner's direction, it models session approvals and credentials on the Codex and Claude desktop apps: a session grant survives restarts, the session Git backup proves only this session's receipts, rebuildable index snapshots stay out of Git, object-storage keys can be stored in the Windows Credential Manager through WOM's masked window, and remaining activity-cleanup items can be finished after a restart without reprocessing completed ones. It does not establish that a customer's own archive, real R2 keys or the physical Windows windows behave as the synthetic checks did.

## Source and checks

- [Product PR #165](https://github.com/mow-coding/zettel-kasten/pull/165): candidate `6e6ef44f349e07afd7bb402744af857f33e78c2e`; [full CI attempt 1](https://github.com/mow-coding/zettel-kasten/actions/runs/36672981132) and Required CI passed. The previous head's run failed on Ubuntu only, in two new tests that assumed Windows-only behaviour (fixed in the candidate) and in a known temporary-directory cleanup flake.
- Squash merge and annotated `v0.4.53` target: `ac1cf7624e2e2ee8beda63e6e9ad148dee47c1fe` (tag object `d6a9764f94cc5b0ac33e925d5b0628d2f35b83e8`). Candidate and merge complete tree: `ed82dc4db55977eb81459d30c88ee8009e82c50c`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36681943568) and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36690076018) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Automatic beta and stable publication

[Automatic Beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36682056028) passed before stable publication. Its source proof matched PR #165, CI attempt 1, the merge and complete tree. Generated commit `7fba072c48eda9b73b5a4f937e15eaa919b95bd4`, beta tag `v0.4.54b33`, wheel 3,624,484 bytes, SHA-256 `76b66041fa53f623ebf0e8703519d755d7cdad48ecd8b075e5c04e6585a5c05b`; installed wheel passed, customer not verified.

[Stable v0.4.53](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.53) became Latest at **2026-09-30T08:31:39Z**:

- `wom_kit-0.4.53-py3-none-any.whl`
- **3,626,102 bytes**
- SHA-256 `a5d1b20bbb69225a0a76a00376e67ac4e748b6643f324b244f062ddf4e519ee1`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-09-30-v0453-public-install.md).

## How the letter's conditions were reproduced

Each gap was reproduced by a synthetic test that failed before its fix: a grant used by a new process after the approving process ended (`work_session_presenter_missing` before), another session's receipt counted against the session Git budget (`work_session_git_receipt_limit` before), a fresh example archive showing snapshot and lock paths as Git changes after one index run, and a 1,070-item activity with 1,017 completed and 53 pending whose env: credential refs were rebound to Credential Manager refs. The design and boundaries are in `wom-kit/docs/archive-infra-decision-log-2026-09-30-letter-177.md`.

## What this release does not prove

Validation used synthetic archives, an injected approval window and a credential-store double. Real R2 keys, the physical Windows windows and the customer's own run are not confirmed. The general Git backup's remote reference observation in the letter was not reproduced.
