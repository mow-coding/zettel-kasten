# v0.4.38 public release evidence

This release combines the activity-completion improvements tracked in product PR #137. Development validation used synthetic archives. Publication and clean installations do not establish success on a customer's machine.

## Source and product checks

- [PR #137](https://github.com/mow-coding/zettel-kasten/pull/137) candidate: `77e2407cb9785bb844b02db4935c4c275f8a2434`.
- [Full PR CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35872218288), attempt 1: all required product/readiness jobs and Required CI succeeded. Earlier candidates with failed Windows checks remain failures; the final candidate corrected the synthetic update-wheel fixture and passed the affected installed flows.
- Squash merge and annotated `v0.4.38` tag target: `93669662e288da52dd9c176b6565deac6a55bb58`. Candidate and merge have the identical complete tree `4afc341588b8b35d8b962a4e688f1abc98beecc8`. Annotated tag object: `1ef6832ef4a8efe90352b354516826d16524bd98`.
- [Post-merge main CI](https://github.com/mow-coding/zettel-kasten/actions/runs/35884822407) succeeded for that merge.

## Stable package and public verification

[Stable v0.4.38](https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.38) was published at 2026-09-23T16:17:45Z. The published file is the retained wheel from the full PR CI installed-wheel artifact; it was not rebuilt for release. The release artifact verifier checked PR head, CI attempt/jobs, merge/tag/tree, package metadata, actual wheel bytes, and installed-wheel proof before publication. The draft asset was downloaded and compared before publication.

- File: `wom_kit-0.4.38-py3-none-any.whl`
- Size: 3,380,636 bytes
- SHA-256: `5e529ea094f6d81ee1b07f241eb2d49e6e7711585f801b80f6d723bc1d27166c`
- Public release API reports the same size and digest. An anonymous download returned the same bytes. Two separate fresh Windows Python 3.12 environments installed from the downloaded local file and the public URL. Each reported `archive 0.4.38` from a new process and passed `pip check`; the URL install's PEP 610 hash matched the public wheel.

## Automated opt-in beta

[Automatic beta delivery](https://github.com/mow-coding/zettel-kasten/actions/runs/35884976800) completed successfully for the same main merge before the stable release began. Its source proof reused the passed PR's identical complete tree. It generated and published prerelease `v0.4.39b5` from generated commit `237b3402000b5d854346f566973c4e7bb98d1eb5`, with wheel size 3,378,693 bytes and SHA-256 `6ea09211fa3d671e9fdc4d427602037902cc70892b4c28cefd00efd5a5cf5194`. The publisher reported installed-wheel, anonymous download and fresh public installation checks passed. The beta remains opt-in and does not replace the stable latest release.

## Boundaries

No client workspace was used for development tests. Product implementation, public package verification and customer acceptance are separate states. Individual customers must confirm their own update and task result; no such confirmation is claimed here.
