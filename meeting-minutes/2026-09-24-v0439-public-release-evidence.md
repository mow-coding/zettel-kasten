# v0.4.39 public release evidence

This release answers beta letter 173 (A, B, C) and the one-deliverable-letter request, tracked in product PR #139. Development validation used synthetic archives. Publication and clean installations do not establish success on a customer's machine.

## Source and product checks

- [PR #139](https://github.com/mow-coding/zettel-kasten/pull/139) candidate: `9d0b9c7912ecb4a20fc668b49e43a333f0b7fdee`.
- [Full PR CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35965653221), attempt 1: all required product/readiness jobs and Required CI succeeded. The earlier run on `7b238000` failed on Windows shard 4/4 because a test module imported a sibling fixture that its shard had not put on the path; the final candidate made the shard runner add the tests directory to `PYTHONPATH`. Runs superseded by later pushes were cancelled and are not pass evidence.
- Squash merge and annotated `v0.4.39` tag target: `43d9099026ee836f0eba4d67e7e3fcea40421b0d`. Candidate and merge have the identical complete tree `54f865eaf1c1f14bb8dc5baed83649823e013684`. Annotated tag object: `ab633e7e1cf57815e55124685e9e33fca25e60a2`.
- [Post-merge main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35976754484) succeeded for that merge.

## Stable package and public verification

[Stable v0.4.39](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.39) was published at 2026-09-24T08:57:50Z. The published file is the retained wheel from the full PR CI installed-wheel artifact; it was not rebuilt for release. The release artifact verifier checked PR head, CI attempt/jobs, merge/tag/tree, package metadata, actual wheel bytes, and installed-wheel proof before publication (`basis: same_full_tree_and_same_verified_wheel_bytes`). The draft asset was downloaded and compared before publication.

- File: `wom_kit-0.4.39-py3-none-any.whl`
- Size: 3,384,460 bytes
- SHA-256: `37c63c06626f0673cfe62bc3de5aab14455e95080a6f09cb7883f71b54026a45`
- An anonymous download returned the same bytes. Two separate fresh Windows Python 3.12 environments installed from the downloaded local file and the public URL. Each reported `archive 0.4.39` from a new process and passed `pip check`; the URL install's PEP 610 hash matched the public wheel.

## Automated opt-in beta

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/35976873110) completed successfully for the same main merge before the stable tag was created. It generated and published prerelease `v0.4.40b7` from generated commit `16b8973da1e056e0950ada905d7fb52545ee966e`, with wheel size 3,382,710 bytes and SHA-256 `8cb23795062c5080a1b5549fd69e47086784eb53c4bb6257e2b61878247f9abc`. The publisher reported the anonymous download and fresh public installation checks. The beta remains opt-in and does not replace the stable latest release.

## Boundaries

No client workspace was used for development tests. Product implementation, public package verification and customer acceptance are separate states. The customer must confirm their own update and task result; no such confirmation is claimed here.
