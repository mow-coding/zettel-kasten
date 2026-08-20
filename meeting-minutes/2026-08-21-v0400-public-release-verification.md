# WOM-kit v0.4.0 public release verification

Date: 2026-08-21 KST

## Purpose and boundary

This record closes the public-release boundary for WOM-kit v0.4.0. It records
only public, content-free release evidence. No protected archive, credential,
provider account, native approval popup, or private source value was opened or
mutated during release verification.

Historical Notion typed-property loss detection and repair remain the urgent
Letter 138 follow-on. They are not part of v0.4.0, and the current page-body or
location recovery surfaces are not evidence of a complete source mirror.

## Implementation merge

- Implementation pull request:
  <https://github.com/mow-coding/zettel-kasten/pull/71>
- Final pull-request head:
  `3e9c28a6856d091d92f1d4e5a13d862b23f0b297`
- Final Required CI run:
  <https://github.com/mow-coding/zettel-kasten/actions/runs/32398409853>
- Final CI result: release-readiness gate, eight platform/version test shards,
  and the aggregate `Required CI` job all completed successfully.
- Merge time: `2026-08-20T18:14:16Z`
- Two-parent merge commit:
  `8e411a570e32031d230030a0640c951291a0b7f0`
- First parent: `45a7d15449a10746f3d5b12387bcda64bcf9b512`
- Second parent: `3e9c28a6856d091d92f1d4e5a13d862b23f0b297`
- Main-push readiness run:
  <https://github.com/mow-coding/zettel-kasten/actions/runs/32402075011>
- Main-push result: success. Matrix tests and aggregate PR-only gate were
  skipped by workflow design.

## Annotated tag and public Release

- Tag: `v0.4.0`
- Annotated tag object:
  `cfb6456e5619a56df1834a1be30b23cc5ba33816`
- Peeled commit:
  `8e411a570e32031d230030a0640c951291a0b7f0`
- Tag-push readiness run:
  <https://github.com/mow-coding/zettel-kasten/actions/runs/32402152548>
- Tag-push result: success.
- Public Release:
  <https://github.com/mow-coding/zettel-kasten/releases/tag/v0.4.0>
- Release id: `373938177`
- Published at: `2026-08-20T18:15:55Z`
- State: stable, non-draft, non-prerelease, and Latest.
- Release body exactly matched the committed v0.4.0 release note.

The Release contains exactly one asset:

- Name: `wom_kit-0.4.0-py3-none-any.whl`
- Asset id: `522613227`
- Size: `2,025,809` bytes
- GitHub digest:
  `sha256:9b7432ce3ac9e9d62497ce3f5bf4e9e9a91a1088da73c611df2cfda6e92fcd76`
- Public download:
  <https://github.com/mow-coding/zettel-kasten/releases/download/v0.4.0/wom_kit-0.4.0-py3-none-any.whl>

The committed source and packaged v0.4.0 release notes were byte-identical
before publication, with SHA-256
`511f86ee2ca48b84916d719974445e4e7f58272ed654a50d21722e28a2478579`.
The packaged resource manifest used by the verified wheel had SHA-256
`b0442f0dd6d8606970f0e86cab3545896ac42167b837cca453982f25dc8df5d9`.

## Anonymous public installation

The wheel was downloaded from the public Release URL with client
configuration disabled and empty Authorization and Cookie headers. The
response was HTTP `200`. The downloaded file was `2,025,809` bytes and its
SHA-256 exactly matched the GitHub asset digest.

A new Python `3.12.10` virtual environment then installed WOM-kit directly
from that public URL without using GitHub CLI authentication.

- Installed package version: `0.4.0`
- Import resolved from the new virtual environment's `site-packages`.
- `pip check`: `No broken requirements found.`
- `archive --version`: `archive 0.4.0`
- `wom --version`: `archive 0.4.0`
- `archive --help`: exit `0`
- Installed entrypoints: `archive`, `wom`, `archive-mcp`, and `wom-mcp`
- Strict Doctor on the checked-in synthetic fake archive: `ok: true`, zero
  errors, zero warnings

This validates public packaging and synthetic operation only. It is not a
claim that a real credential was enrolled, a provider was contacted, or a
protected archive was repaired.

## Cleanup checkpoint

The first closeout commit,
`1a27b6df81cd878447d174e6a69ce93aeed5b206`, was stored on the remote branch
before cleanup. The exact authoritative wheel-candidate directory and the exact
anonymous-install verification directory were then verified as ordinary
directories below the operating-system temporary root and moved to the Windows
Recycle Bin. Both are absent from their original locations and remain
recoverable from the Recycle Bin. The public Release asset and annotated tag
remain published. Older non-authoritative temporary evidence was outside this
cleanup scope and was not touched. The implementation and closeout worktrees
and branches remain until the closeout pull request is merged.
