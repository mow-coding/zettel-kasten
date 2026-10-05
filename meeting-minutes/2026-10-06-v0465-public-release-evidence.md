# v0.4.65 public release evidence

This WOM-kit release is the first part of the answer to beta letter 184: a session-scoped `git-backup-reconcile-plan --dry-run` carries `session_backup_coverage` (selected outputs by kind, roles of all Git-changed paths as fixed labels, this session's succeeded approvals by operation with whether their Git changes are provable as session-owned, the shared-by-design objet ledger and the archive-wide route, objet bytes never in Git) and `long_run_guidance`; the `git_output_scope_discovery` and `git_receipt_provenance` progress lines carry `current`/`total`; one fresh preview or write authenticates each source-intake original and local-recovery control once. It does not establish the customer's own run.

## Source and checks

- [Product PR #184](https://github.com/mow-coding/zettel-kasten/pull/184): candidate `fa002a8e`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37370375394) passed on attempt 3 and Required CI passed. Attempts 1 and 2 were cancelled before any test ran during a GitHub Actions outage (2026-10-05, "Partial System Outage").
- Squash merge and annotated `v0.4.65` target: `73f99649` (tag object `dd4ebf82cbe18779f68b63b7ab8e40f0922a1e00`). Candidate and merge complete tree: `c07df591e3c425147ad4cbd434f98d1cff710e76`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37388439399) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37388792399) passed.
- The retained CI artifact from attempt 3 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.65](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.65) became Latest at **2026-10-05T23:32:04Z**:

- `wom_kit-0.4.65-py3-none-any.whl`
- **3,691,115 bytes**
- SHA-256 `91bcfdc8afd619dfcf5f2287581013ef8996a6b12190a588641b8b3a26c359c4`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-06-v0465-public-install.md).

## How the conditions were reproduced

The customer's shape was built in a temporary Git repository with a real registry, grant and claims: a conversation with an `allow_all` grant wrote a zettel-objet link through the CLI without a window; the session-scoped preview then selected only the session's two decision receipts, and the new coverage block reported the link approval as outside the selection with the changed-path roles (zettel document, link receipts, objet ledger, usage record). Windows: 203 session Git tests (one local-only cold-start failure of the MCP stdio test, unrelated) and 12 new tests. Executing model: Claude Fable 5.1. The design was decided under the owner's 2026-09-25 design delegation.

## What this release does not prove

The customer's archive and the cause of their 634-second second preview are not confirmed. Session-owned proof for zettel-objet link changes follows in v0.4.66.
