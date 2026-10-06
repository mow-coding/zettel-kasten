# v0.4.67 public release evidence

This WOM-kit release answers beta letter 185: an `object-storage-upload --dry-run` that ends `writer_unavailable` carries `writer_unavailable_explained` (one of four store-label categories, what it is not, that scope and manifest were not evaluated, plain sentences) and `preservation_relation` (a Git backup never holds objet bytes); `object-storage-scope-list --approval-id` adds the objets captured under exactly those approvals, also when the approval was given through a window and carries no session mark; a `--this-session` refusal counts the unmarked captures and gives that route. It does not establish the customer's own run.

## Source and checks

- [Product PR #188](https://github.com/mow-coding/zettel-kasten/pull/188): candidate `8e71fe27`; [full CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37431516400) passed on attempt 1 and Required CI passed.
- Squash merge and annotated `v0.4.67` target: `c87affc6` (tag object `ff4b74a18a57a361521aca0bbccb2fccd529d2a0`). Candidate and merge complete tree: `f43432346ba0e052ba90478eb22a1a744122f64c`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37442161318) passed before the tag was pushed, and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/37442435889) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Stable publication

[Stable v0.4.67](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.67) became Latest at **2026-10-06T09:23:20Z**:

- `wom_kit-0.4.67-py3-none-any.whl`
- **3,704,041 bytes**
- SHA-256 `0987bc67b131f4807403c997b0686adbe8ef044ef6cdd207f6c5ad220d9ee76a`

The anonymous download and the two fresh Windows installations are recorded in [the sanitized install result](2026-10-06-v0467-public-install.md).

## How the conditions were reproduced

With a synthetic archive, capture receipts and claims (the claim store boundary substituted) and the real CLI: an unregistered store label, an unsupported provider kind and an unsafe label each produce their category with the registered labels listed; a session whose only captures were approved through a window is refused with counts and the approval route; `--approval-id` builds a list bound to the named approvals' verified receipts, refuses malformed ids, and selects nothing for failed, non-capture or unknown approvals; the resulting upload plan never widens. Windows: 191 related tests and 3 MCP upload tests (the 4 MCP stdio cold-start tests fail on the developer's machine with or without this change). Executing model: Claude Fable 5.1. The design was decided under the owner's 2026-09-25 design delegation.

## What this release does not prove

The customer's store labels, their registration state and their run are not confirmed.
