# Decision Log: v0.3.283 Activity-Group Retained-Journal Isolation

Date: 2026-07-29

## Context

v0.3.281 introduced the approved membership-add transaction and explicit
recovery. v0.3.282 added a separate read-only removal plan while deferring its
writer. The existing add writer checked only the journal derived from its own
request digest. A retained journal for another add request, or evidence in the
private root reserved for future removals, could therefore coexist with a new
add attempt.

Completion verification also proved a receipt and transaction evidence mostly
along separate paths. A receipt could be structurally valid and point at
currently applied memberships without proving that every shared field and
ordered participant matched the retained journal or lock about to be cleaned.
The recovery-plan digest did not bind the receipt's raw bytes.

## Decision

1. Scan the direct children of both private activity-group request roots before
   an approved add attempts the shared writer lock.
2. Repeat that scan under the shared lock before snapshots or canonical
   mutation.
3. Recognize both the current add-journal suffix and the reserved
   future-removal journal suffix in either root.
4. Bound the combined scan to 5,000 entries, never recurse, never read journal
   content for discovery, and fail closed on unsafe roots or incomplete scans.
5. Use one content-free unresolved-evidence blocker for retained/reserved
   journals and one fixed scan-failure blocker for an untrustworthy scan.
6. Compare receipt and journal shared transaction fields plus every ordered
   participant and before-snapshot field exactly.
7. Advance the private write-lock shape to v0.2 and commit the SHA-256 of the
   full receipt/journal semantic projection. Keep v0.1 compatible when a full
   journal is present, but send v0.1 lock-only completion to forensic hold.
8. Bind both the raw receipt SHA-256 and the exact transaction-binding SHA-256
   into the recovery plan.
9. Re-read and verify receipt, journal, and lock evidence immediately before
   cleanup. Retain evidence if it changed after review.
10. Classify foreign, malformed, mismatched, or otherwise unknown evidence as
    non-executable `manual_forensic_hold`.
11. Keep all public activity-group request, plan, write, receipt, journal,
    recovery-plan, and recovery-result schemas at v0.1; keep the current CLI
    and aliases and AI command-path routing at v0.5.
12. Add no schema file, CLI command, MCP method, route version, or removal
    mutation in this release.
13. Defer the separately approved removal writer and its recovery path to
    v0.3.284.
14. Bind every directory component from the resolved archive root to each
    private evidence parent. Use descriptor-relative child operations on POSIX
    and held non-delete-shared ancestor handles on Windows.
15. Create writer locks, prepared journals, and receipts only beneath the
    corresponding held parent binding.
16. Delete evidence only after matching its expected raw SHA-256. On Windows
    delete through the verified READ+DELETE handle. On POSIX first atomically
    capture the current pathname in a quarantine under the separately bound,
    globally scanned private activity-group root, then verify and delete only
    that captured entry.
17. Use state-specific terminal cleanup for approved recovery. When a journal
    exists, remove the exact lock, revalidate the reviewed receipt,
    participants, and journal with the lock absent, remove and verify absence
    of the exact recovery guard, revalidate that the reviewed journal is the
    sole retained transaction, and remove that journal last. When no journal
    exists, remove and verify absence of the exact guard first, revalidate the
    journal-free state while the exact lock remains, and remove that lock
    last. The final verification sequence requires guard, lock, and journal
    absence. If guard cleanup fails, retain the journal or lock that still
    carries the transaction semantics.
18. Replace canonical participant bytes only through an OS-level
    compare-and-swap: POSIX atomic sibling exchange or Windows `ReplaceFileW`
    with backup. Verify the captured expected bytes and installed replacement;
    restore or retain unknown bytes instead of overwriting them.
19. Give each transaction/participant a deterministic content-free swap
    residue name so a hard interruption can be classified and cleaned only
    when it forms a known complementary before/after pair.
20. Create the recovery guard and any missing-writer-lock claim under one held
    root-to-private-leaf binding, and delete them through that same binding.
    Consume guard-cleanup authority before the exact delete attempt so a
    same-name replacement is never deleted by a retry in `finally`.
21. Immediately before deleting its journal, require the writer inventory to
    contain exactly that journal; after deletion require an empty inventory.
    Report `applied_evidence_conflict` if committed data is valid but foreign
    evidence, exact lock/journal deletion failure, or cleanup revalidation
    prevents a clean completion claim.
22. On POSIX, double-read/hash and compare size, mtime, ctime, and identity
    while the captured evidence descriptor remains open. State the remaining
    limitation: no portable primitive can revoke an uncooperative already-open
    writable descriptor after the final check.
23. Automatically clean a verified completed v0.2 lock-only residue on Windows
    only. POSIX retains this journal-free state for manual forensic review
    because a read descriptor cannot freeze the receipt pathname while the
    sole semantic lock is deleted.
24. Put every POSIX exact-delete quarantine under the bounded, globally scanned
    private activity-group root and give its direct-child directory the
    retained-journal suffix. A hard exit after capture then blocks the next
    writer/recovery instead of hiding residue under `zettels/` or `receipts/`.
    A cross-filesystem rename fails before source movement.

## Rationale

A lock serializes cooperating writers only while it is held. Durable journals
describe unfinished or incompletely cleaned work that can outlive a process.
Treating those journals as a shared namespace prevents a later transaction
from interpreting the same canonical files while earlier evidence remains
unresolved.

The journal filename is sufficient to stop a new writer; reading its private
body would add exposure and denial-of-service risk without granting more
authority. Exact receipt-to-transaction binding is required only when recovery
must classify or clean one known transaction.

Binding raw receipt bytes closes the final cleanup race. A plan that reviewed
one receipt must not delete evidence after a different receipt occupies the
same deterministic location, even when both documents parse.

Path containment is not the same as filesystem-object identity. A safe lexical
path can be redirected later through a replaced ancestor, junction, or
symlink. Holding each ancestor and addressing the final entry through that
binding makes the checked object, not just its spelling, part of the authority.

Deleting by pathname after verification repeats the same ambiguity at the end
of a transaction. POSIX therefore captures the name first and verifies the
captured entry, while Windows deletes through the verified open handle. A
replacement remains at the public name or in retained quarantine evidence.
For journal-bearing states, keeping the journal until the last verified step
preserves the durable explanation whenever lock, guard, or state revalidation
fails. For journal-free states, the lock remains the semantic evidence until
guard cleanup and state revalidation have succeeded.

A check followed by `os.replace()` is not a compare-and-swap: another actor can
change the file between those operations and be overwritten. Atomic sibling
exchange or replacement-with-backup preserves the exact occupant of the name
at commit time so WOM can compare after capture and restore on mismatch.
Rollback and recovery therefore use the same primitive instead of granting a
stale classification authority to overwrite later bytes.

The lock-only case cannot derive receipt truth from an opaque write-plan digest
alone. The v0.2 lock carries a commitment to the complete semantic projection;
v0.1 remains usable only beside the journal that supplies those semantics.
When the journal is absent, Windows can keep the exact receipt path stable with
share-mode exclusion while deleting the v0.2 lock. POSIX cannot atomically
bind those two names, so retaining both is safer than an automatic cleanup that
could irreversibly remove the only semantic commitment.

## Consequences

- A retained add journal or reserved removal journal stops a new add before
  and under the shared lock.
- A large, malformed, or private foreign journal need not be opened or echoed
  to block safely.
- Completed cleanup requires one receipt to describe the exact journal or lock
  being removed, not merely the same request digest.
- Receipt or evidence drift after the reviewed plan preserves the forensic
  record instead of cleaning it.
- A private-root or receipt-parent substitution is refused before it can
  redirect a write.
- A same-name receipt, journal, or lock replacement is retained instead of
  being deleted by stale authority.
- A concurrent canonical edit is restored or retained rather than overwritten
  by forward commit, runtime rollback, or approved recovery.
- A known hard-exit swap residue is recoverable; an ambiguous or unknown
  residue is a forensic hold.
- Recovery guard/claim writes cannot escape through a replaced private-root
  ancestor.
- A writer cannot report a clean success while foreign transaction evidence
  is present at its final inventory boundary.
- POSIX same-name replacements are preserved and observed in-place mutation
  blocks deletion; an uncooperative already-open writable descriptor after the
  final check remains an explicit quiescence boundary.
- POSIX hard-exit quarantine is globally discoverable as unresolved
  transaction evidence; no canonical/receipt-parent random directory can be
  silently omitted from the final inventory.
- Verified v0.2 completed lock-only cleanup is automatic on Windows and a
  manual forensic hold on POSIX.
- Journal-free cleanup removes and verifies the guard, revalidates while the
  lock remains, removes the lock last, and then runs the final common
  verification.
- Healthy v0.1 requests, plans, receipts, journals, and recovery commands
  remain compatible. v0.1 locks remain compatible beside a journal; v0.1
  lock-only completion requires manual review.
- No removal is executed in v0.3.283; the read-only removal plan remains the
  only official removal route until v0.3.284.

## Standards Basis

The shared-lock and prepare-before-mutate model continues to follow ordinary
write-ahead transaction principles: durable intent must be reconciled before
another writer acts on the same logical participants. WOM still does not claim
that multiple Markdown replacements are one filesystem-level atomic commit.

- https://www.sqlite.org/atomiccommit.html
- https://docs.python.org/3/library/os.html#os.scandir

The filesystem binding follows the standard rationale for POSIX directory-fd
APIs: `openat()` avoids path-prefix replacement races, `O_NOFOLLOW` refuses a
symbolic-link final component, and Linux `renameat2(RENAME_EXCHANGE)` swaps two
bound sibling names without dropping either occupant. Apple
`renameatx_np(RENAME_SWAP)` supplies the corresponding operation.

- https://man7.org/linux/man-pages/man2/open.2.html
- https://man7.org/linux/man-pages/man2/rename.2.html
- https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/renameatx_np.2.html

On Windows, the implementation follows documented `CreateFileW` share-mode and
`FILE_FLAG_OPEN_REPARSE_POINT` behavior, uses `ReplaceFileW` to preserve the
prior canonical bytes in a backup, then uses
`SetFileInformationByHandle(FileDispositionInfo)` with DELETE access so the
verified handle is the deletion target.

- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_disposition_info
