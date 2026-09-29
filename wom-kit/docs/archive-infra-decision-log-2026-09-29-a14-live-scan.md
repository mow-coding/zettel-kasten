# Decision log: the live zet scan stops opening every file (A14, 2026-09-29)

## Context

Beta letters 174 and 176 asked that registering, reviewing and checking a large
activity finish in realistic time (request A14). Codex's 2026-09-28 measurements
on a 23,000-object, 8,616-zet synthetic archive showed that the installed
`zettel-edge --dry-run`, `zettel-objet-link --dry-run` and
`exact-approval-claims --status all` each finish under 5 s but, after the claims
listing and startup-cache corrections, still missed the 50 % reduction target
against public v0.4.47 (9.60 %, 22.10 %, 48.79 %). The owner delegated the
remaining design on 2026-09-25; this is Claude's recommendation, implemented and
measured in the same release.

## Facts

- Profiling the installed edge command (candidate with the startup cache) put
  4.2 s of a 4.7 s instrumented run in `strict_live_zettel_stat_snapshot`: the
  two scans of the zet tree that bind the index to the live files. Only 1.1 s of
  that was the per-file `os.lstat`; the rest was pathlib bookkeeping per entry
  (`Path`, `relative_to`, `PurePosixPath`).
- On Windows the `os.lstat` of one file opens a handle; 8,616 files twice cost
  0.5-0.8 s even after the bookkeeping was removed.
- A directory listing read with `GetFileInformationByHandleEx(FileIdBothDirectoryInfo)`
  returns, per entry, the same size, creation time, last-write time,
  attributes and the 64-bit file id that `os.lstat` reports (`st_ino` on NTFS),
  from one handle per directory. On this Windows 11 NTFS volume the listing
  reflected a write from another process immediately (write + flush, handle
  still open), so the listing and the handle metadata agreed.

## Decisions

1. **String bookkeeping.** The scan loop works on `DirEntry.path`/`name`
   strings and builds the archive-relative POSIX key from the parent key and the
   entry name. Same lstat per entry, same five generation fields, same keys,
   same failure codes. Results were byte-identical on the fixture.
2. **Directory file ids on Windows.** Size, times and attributes come from
   `DirEntry.stat(follow_symlinks=False)` (the listing) and the file id from one
   `FileIdBothDirectoryInfo` read per directory; the volume serial is the
   folder's `st_dev`. No zet file is opened during the scan.
3. **Sample cross-check with fallback.** Eight evenly spaced listed files per
   directory (always the first and the last) are re-observed with `os.lstat`
   and must equal the listing-derived generation exactly. Any mismatch, any
   listing API failure, or a non-Windows host runs the original per-file path
   for the whole scan. The opening and closing scans, the authority watcher
   fence and the per-target exact byte checks are unchanged.
4. **Measured on the official launcher.** The benchmark tool gained the
   `candidate-stat-scan` label and the `stat-scan` measurement id so earlier
   evidence stays; the table below is that run (see
   `meeting-minutes/2026-09-28-feedback-implementation/a14-stat-scan/`).

| Command | Baseline repeat p95 (v0.4.47) | Candidate repeat p95 | Reduction | >= 50 % |
|---|---:|---:|---:|---|
| zettel-edge --dry-run | 2.524 s | 0.881 s | 65.12 % | met |
| zettel-objet-link --dry-run | 2.717 s | 1.212 s | 55.39 % | met |
| exact-approval-claims --status all | 2.335 s | 0.891 s | 61.84 % | met |

Each cell is a separate installed fresh process on the same 9,619-file synthetic
input (first observation plus ten repeats per label, alternating order); the
first process is not a cold-OS number and no sample is discarded.

## Boundaries

- The listing-derived generation is trusted only where the sampled entries
  agree with `os.lstat`; a file system whose directory entries lag behind
  handle metadata for unsampled files would not be detected by the sample.
  The change-detection window is still closed by the second scan and the
  watcher fence, and every write target is re-read and hashed exactly before
  it is touched.
- Approval waiting, actual writer execution, remote transfer and request
  deduplication were not measured (read-only cases only), and no customer PC
  was timed.
- The claims listing was not changed again in this release; its number above
  comes from the same run for completeness.
