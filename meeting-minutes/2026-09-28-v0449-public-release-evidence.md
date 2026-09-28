# v0.4.49 public release evidence

This partial WOM-kit release adds exact-key remote temporary-object cleanup and
short-lived private object opening. It does not automatically classify legacy
remote junk or complete the remaining customer requests. Customer archives and
buckets were not used as development fixtures, and customer acceptance is open.

## Source and required checks

- [Product PR #158](https://github.com/mow-coding/zettel-kasten/pull/158): candidate `4e11ffe5d90e2e0dfa80ad7e26d9c2f7ac43835a`.
- [Full product CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36410847390): attempt 1 failed Windows shard 4 before product tests during PyPI dependency retrieval; Windows shard 1 had two subprocess-timeout errors. Only failed jobs and Required CI reran in attempt 2, which passed. Earlier failed candidate runs remain failed/cancelled evidence. Focused and delivery-tools lanes were skipped under the product-change definition and are not counted as executed tests.
- Squash merge and annotated `v0.4.49` target: `244567f9cf54037f4917e7131d07dd45db180830`. Candidate and merge complete tree: `6b7abfd652b0e794cfcb6472ccbaa460793e62bf`. Annotated tag object: `a7613d5be0a3aa35a4b00caa9bb147595d0dd48e`.
- [Main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/36424931130): Required CI passed.

## Stable artifact and public installation

[Stable v0.4.49](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.49)
was published at **2026-09-28T13:17:06Z**.

- File: `wom_kit-0.4.49-py3-none-any.whl`
- Size: **3,525,355 bytes**
- SHA-256: `825ce66b3dfa370feb78aff6b6d0fa67e7ddc49b4f85fb6cc0a94851446115ef`

The installed-wheel artifact was produced by the passed installation gate in
attempt 1 of the same CI run. A failed-jobs-only attempt 2 passed all required
checks. A private verifier checked both attempts, PR head, identical candidate
and merge tree, annotated tag target, the actual wheel bytes, size and SHA-256.
The wheel was reused without rebuilding. The draft release asset was downloaded
and compared with the retained wheel before publication.

After publication, anonymous download matched the same size and SHA-256. Two
fresh Windows environments installed from the downloaded file and the public
URL. Both returned `archive 0.4.49`, passed `pip check`, recorded the expected
PEP 610 hash and verified all **180** packaged resources without mismatch.
See the [sanitized machine result](2026-09-28-v0449-public-install.md).

## Automatic beta and limits

[Automatic Beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/36425066369)
finished before stable publication. Its source proof matched PR #158, CI
attempt 2, merge and complete tree. Generated commit
`ee643f8c6db07837382c51e8cb03c9f516055886` published opt-in
`v0.4.50b26`, wheel size 3,524,250 bytes and SHA-256
`d9a6ffe3554b7412de20ad18d2817c918b9ae9c6624c54748b9d86a2ffd65486`.
Generated-wheel installation, anonymous download and a fresh public install
passed. The beta is separate from the stable Latest release.

Development R2 and synthetic tests covered selected exact-key deletion, lost
response and resume, refusal to re-upload a disposed key, and signed GET with
expiry. They do not prove automatic AI classification of already-uploaded
legacy content, a physical browser-opening flow, customer-bucket behavior, or
customer acceptance. A01/A02 and other open requests remain tracked by their
individual criteria; this release is not an all-feedback completion claim.
