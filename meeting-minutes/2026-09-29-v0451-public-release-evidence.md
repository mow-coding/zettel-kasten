# v0.4.51 public release evidence

This WOM-kit release lands the feedback-completion integration for beta letters 174-176 (requests A03-A19) after the v0.4.47-v0.4.50 partial releases. It does not establish that a customer's own run, real provider accounts or the physical Windows dialog behave as the synthetic checks did. Customer acceptance and the requests that need the customer's environment remain open.

## Source and checks

- [Product PR #162](https://github.com/mow-coding/zettel-kasten/pull/162): candidate `f4ba8b9089dc2bbbacf33c49d9272052003c2dc3`; [full CI attempt 1](https://github.com/mow-coding/zettel-kasten/actions/runs/36544701075) and Required CI passed. Three earlier runs on this branch failed on Windows-only Doctor snapshot staleness (fixed by rename publication), a Ubuntu-only cancellation expectation, and twice on the Doctor first-status timing under runner load; the last is now re-measured only under CI when it is the sole failed check.
- Squash merge and annotated `v0.4.51` target: `58dbbdb4b8477fb6a7a34f352f6e123e4e94e361` (tag object `db63349194ba80a9634561d112dc419fb6939ebc`). Candidate and merge complete tree: `35cf985be549f1b701b6ccfb86c77e8cba98cbe3`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36555415990) and the [tag CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36557678030) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size (`wom-kit/release-artifact-reuse/v1`, `same_full_tree_and_same_verified_wheel_bytes`). It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Automatic beta and stable publication

[Automatic Beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36555671489) passed before stable publication. Its source proof matched PR #162, CI attempt 1, the merge and complete tree (`identical_tree_including_workflows_and_dependency_locks`). Generated commit `4adf99106cdcd004de92b4d05f521929f1ead036`, beta tag `v0.4.52b30`, wheel 3,608,225 bytes, SHA-256 `93e63f15ea0dfaae75ec2959f720df765a99d2fa12b85a7ea65c7c85ff19be8a`; installed wheel passed, customer not verified.

[Stable v0.4.51](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.51) became Latest at **2026-09-29T10:48:59Z**:

- `wom_kit-0.4.51-py3-none-any.whl`
- **3,609,541 bytes**
- SHA-256 `45e0d8ac614d9849bc7528796ce101445e0eeabcbb70e60fe914e991e7867824`

After publication, anonymous download matched the same size and SHA-256. Two fresh Windows environments installed from the downloaded file and the public URL. Both returned `archive 0.4.51`, passed `pip check`, recorded the expected PEP 610 hash and verified all 180 packaged resources; the public-URL installation's bootstrap decision reported `exact_public_release_wheel_verified`. See [the sanitized install result](2026-09-29-v0451-public-install.md).

## What this release does not prove

Validation used synthetic data, simulated providers and an injected approval window. Real Notion, mailbox, Tiro and R2 accounts, the physical Windows dialog and customers' own runs are not confirmed. The A14 performance target, A17 original-filename discovery, the A13 installed-guidance gate and the 25 additional-verification items follow in v0.4.52.
