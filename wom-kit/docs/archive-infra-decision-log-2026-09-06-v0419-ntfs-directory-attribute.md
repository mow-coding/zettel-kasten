# Runtime directory identity: redundant NTFS directory bit

Status: implemented and independently reviewed with focused tests;
exact-candidate acceptance remains required. No release or client update yet.

## Evidence

Candidate `1b8febe7`, installed Windows job `101342624029` in run `33979694945`,
failed during initial update. The original same-frame directory comparison
recorded only attribute bit 28 being cleared. Device, inode, kind, size and
mtime did not differ at that predicate. No named Win32 attribute changed.

[CPython issue 126253](https://github.com/python/cpython/issues/126253) reports
the same `0x10` versus `0x10000010` representations for an ordinary NTFS
directory. Its maintainers reproduced this on Windows build 26100. This
supports treating this exact redundant bit separately; it does not establish
which native API or filesystem component produced WOM's particular transition.
The proposed upstream test mask is not a precedent for ignoring all unknown
bits in a production integrity check.

## Decision

In `_stat_identity`, normalize `0x10000000` only when both the independent
mode is a directory and the original Win32 `DIRECTORY` attribute `0x10` is set.
Keep the existing directory-only size/ARCHIVE normalization. Do not alter raw
filesystem attributes, persisted bytes, native query results, or file stats.

Keep bit 28 on regular files and contradictory directory representations.
Keep every other unknown or known attribute, especially reparse/storage flags.
Original reparse refusal, descriptor byte checks, device/inode/kind/mtime
comparisons and exact tree-member/hash verification are unchanged.

## Consequences and validation

This is a comparison-model correction for a demonstrated equivalent directory
representation, not a retry or an unknown-attribute fallback. Windows and
portable fixtures must cover both transition directions, contradictory kinds,
other flag changes, identity/member changes and same-size content drift.
The full installed workflow and all required CI still determine release
eligibility. Local injected-stat cases are not claimed as native reproduction
of the CI filesystem's behavior.

Chronology: [reassessment minutes](../../meeting-minutes/2026-09-05-recovery-train-reassessment.md).
