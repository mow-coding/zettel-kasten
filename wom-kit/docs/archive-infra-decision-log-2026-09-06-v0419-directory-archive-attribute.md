# Directory backup bookkeeping is not runtime content identity

## Context

A native Windows synthetic reproduction changed only a directory's ARCHIVE
attribute during enumeration. Runtime validation rejected it although file
identity, members and bytes were unchanged. CI has independently demonstrated
attributes-only directory drift, but its exact bit remains unconfirmed.

## Decision

Normalize only directory ARCHIVE (`0x20`) in the existing runtime stat identity.
Retain file attributes and all other directory bits, including unknown bits,
reparse points and offline/recall/storage indicators. Retain device/inode/type,
mtime, exact member comparison, descriptor checks, file sizes and hashes.

The observer may name fixed changed bits from its original comparison without
copying numeric identity/mask values. It does not add reads or retries. Existing
approvals, transaction state rules and release deadlines remain unchanged.

## Evidence and limits

Native and portable tests cover root/intermediate enumeration and ancestor
reads. Negative tests preserve identity, metadata, member and byte drift checks.
The exact CI cause and final installed success still require candidate evidence.
Do not generalize a demonstrated ARCHIVE-only false positive into permission to
ignore all metadata changes or to claim a client installation succeeded.

[Microsoft file attribute definitions](https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants)
and [native attribute setter](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileattributesw)
document the distinct backup marker and path/storage attributes.

See [reassessment minutes](../../meeting-minutes/2026-09-05-recovery-train-reassessment.md)
for the failure sequence and validation status.
