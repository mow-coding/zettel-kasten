# v0.4.50 public release evidence

This partial WOM-kit release adds private, content-backed inventory for exact-key remote cleanup. It does not establish that a customer's helper AI classified an actual customer bucket correctly. Customer acceptance and other outstanding requests remain open. Development used synthetic files in a separate development R2 bucket.

## Source and checks

- [Product PR #160](https://github.com/mow-coding/zettel-kasten/pull/160): candidate `29039f41aeeb18c242fd02eb2c0b75ce6cfe2f04`; [full CI attempt 1](https://github.com/mow-coding/zettel-kasten/actions/runs/36436002489) and Required CI passed.
- Squash merge and annotated `v0.4.50` target: `4d8c344410a68ae3affc6fb8665d392418458806`. Candidate and merge complete tree: `ae03a379ef79550f932ea9f0e60d554a132b1dd6`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36446526099) passed.
- The retained CI artifact from attempt 1 was checked against the PR, CI, merge, annotated tag, complete tree, wheel bytes, SHA-256 and size. It was reused without rebuilding. The draft asset was downloaded and matched byte for byte before publication.

## Automatic beta and stable publication

[Automatic Beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36446686219) passed before stable publication. Its source proof matched PR #160, CI attempt 1, the merge and complete tree. Generated commit `e81cdc31d36ad15d21feddb944e6d57321611668` published opt-in `v0.4.51b28`. Its wheel was 3,526,062 bytes with SHA-256 `a9d22e66becb83d6090ae24a6838c06727885f6113c8f06bbf36ad3f67941539`. The generated-wheel installation, anonymous download and fresh public install passed.

[Stable v0.4.50](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.50) became Latest at **2026-09-28T16:10:31Z**:

- `wom_kit-0.4.50-py3-none-any.whl`
- **3,527,223 bytes**
- SHA-256 `a1710bb79f03bb399284e1a03185436a0d4bc386d31cad28b2197ddb827b86da`

After publication, anonymous download matched the same size and SHA-256. Two fresh Windows environments installed from the downloaded file and the public URL. Both returned `archive 0.4.50`, passed `pip check`, recorded the expected PEP 610 hash and verified all **180** packaged resources without mismatch. See the [sanitized machine result](2026-09-28-v0450-public-install.md).

The first public check accidentally requested the previous version's filename and received HTTP 404 before any download or installation. The check script was corrected to the published filename; the subsequent full check passed. This first attempt is retained as a test-tool error, not counted as a product success or an asset failure.

The developer R2 synthetic installed-CLI flow inspected two remote objects by verified content, removed only the confirmed temporary object and preserved the other during cleanup; all test-owned keys were removed afterward. The actual customer helper-AI conversation and customer bucket were not inspected, so this release is not an all-feedback completion claim.
